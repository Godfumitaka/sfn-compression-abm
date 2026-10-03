"""指紋呼出し3箇所だけの差分と、関連の検査を保存する。"""
from pathlib import Path
import ast, json, subprocess

root=Path(__file__).resolve().parent
source=root/'source';ev=root/'evidence'
old=subprocess.check_output(['git','show','769263c:tools/v311c.py'],cwd=source,text=True)
new=(source/'tools/v311c.py').read_text()

class RestoreAudit(ast.NodeTransformer):
    context=None
    def visit_FunctionDef(self,node):
        previous=self.context;self.context=node.name
        self.generic_visit(node)
        self.context=previous
        return node
    def visit_ImportFrom(self,node):
        return None if node.module=='v311c_fingerprint' else node
    def visit_Call(self,node):
        if isinstance(node.func,ast.Name) and node.func.id=='fingerprint':
            assert len(node.args)==1 and isinstance(node.args[0],ast.Name) and node.args[0].id=='state'
            if self.context=='probe':return ast.parse('repr(state)',mode='eval').body
            assert self.context=='apply'
            return ast.parse('sha256(repr(state).encode()).hexdigest()',mode='eval').body
        return self.generic_visit(node)

proof={'comparison_commit':'769263cd250d5ce15735ead3eee7c44bfe0adf1d',
       'v311c_only_audit_calls_and_import_changed':ast.dump(ast.parse(old),include_attributes=False)==
           ast.dump(RestoreAudit().visit(ast.parse(new)),include_attributes=False),
       'other_model_files_unchanged':not subprocess.check_output(['git','diff','769263c','--',
           'abm/','config/','tools/v3_run.py','tools/v39.py','tools/v310be.py',
           'tools/v311c_lineage.py'],cwd=source)}
(ev/'canonical-model-unchanged-proof.json').write_text(json.dumps(proof,indent=1)+'\n')
assert proof['v311c_only_audit_calls_and_import_changed'] and proof['other_model_files_unchanged']
(ev/'canonical-code.diff').write_bytes(subprocess.check_output(['git','diff','769263c','--',
    'tools/v311c.py'],cwd=source))
files=[r['file'] for r in json.loads((ev/'terminal-fix-unit-suite.json').read_text())]
files+=['test_v311c_fingerprint.py']
results=[]
for file in files:
    argv=['/opt/homebrew/bin/uv','run','--offline','--no-project','--python',
          '/opt/homebrew/opt/python@3.12/bin/python3.12','--with','pytest==9.1.1',
          'python','-m','pytest','-q','tests/'+file]
    p=subprocess.run(argv,cwd=source,text=True,capture_output=True)
    results.append({'file':file,'argv':argv,'returncode':p.returncode,'output':p.stdout+p.stderr})
    (ev/'canonical-unit-suite.json').write_text(json.dumps(results,ensure_ascii=False,indent=1)+'\n')
    print(file,p.returncode,p.stdout.strip().splitlines()[-1],flush=True)
    assert p.returncode==0
