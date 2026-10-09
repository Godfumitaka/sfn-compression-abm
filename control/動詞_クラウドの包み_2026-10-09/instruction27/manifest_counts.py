"""既存指示22のmanifest辞書比較の同一関数。"""
from tools.instruction11_io import without_time, byte_row
import json

def manifest_counts(left, right):
    def fields(path):
        text=path.read_text();decoder=json.JSONDecoder();i=0;rows={}
        assert text.lstrip().startswith('{')
        i=text.index('{')+1
        while True:
            while text[i].isspace() or text[i]==',':i+=1
            if text[i]=='}':break
            key,end=decoder.raw_decode(text,i);i=end
            while text[i].isspace():i+=1
            assert text[i]==':';i+=1
            while text[i].isspace():i+=1
            value,end=decoder.raw_decode(text,i)
            # 部品の研究者辞書は設定・名前・順も含め、そのままの値の字節を比べる。
            if isinstance(value,dict):rows[key]=text[i:end].encode('utf-8')
            i=end
        assert 'strictpc' in rows and 'v39' in rows and 'stage2' in rows
        return rows
    a,b=fields(left/'manifest.jsonl'),fields(right/'manifest.jsonl');rows=[]
    for key in dict.fromkeys([*a,*b]):
        if key not in a or key not in b:
            rows.append(dict(path='manifest:'+key,equal=False,left_exists=key in a,right_exists=key in b));continue
        x,y=a[key],b[key]
        if key=='stage2':x,y=without_time(x),without_time(y)
        if key=='verbtiming':
            # 模型の欄ではない原実時間だけ。checkpointsなどの数えは保つ。
            import re
            pattern=rb'("elapsed_seconds"\s*:\s*)(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)'
            x,y=(re.sub(pattern,rb'\g<1>0',data) for data in (x,y))
        rows.append(byte_row('manifest:'+key,x,y))
    return dict(passed=all(row['equal'] for row in rows),file_count=len(rows),
                mismatching_files=sum(not row['equal'] for row in rows),files=rows,
                policy='全ての部品の研究者辞書を原字節で比較。stage2の既定TIMEと非模型verbtimingの原実時間値だけ。原manifestを保持。')
