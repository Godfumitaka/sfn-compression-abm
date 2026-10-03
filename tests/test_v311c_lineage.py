"""研究者用の系譜は元通信を書き換えず、別の定義へ親を混ぜない。"""
import json
from hashlib import sha256
from v311c_lineage import write_lineage


def test_lineage_dag_and_read_only(tmp_path):
    src=tmp_path/'comm.jsonl';out=tmp_path/'lineage.jsonl'
    def bundle(agent,t,R,born,b):
        return {'kind':'bundle','agent':agent,'t':t,'R':R,'R_born':born,'bundle':b,'pred':['r','p',['x','y']],
                'send':True,'relations':[['r','p',['x','y']]]}
    rows=[bundle(0,3,'low',0,'b0'),
          {'kind':'recv','agent':4,'t':3,'R':'high','R_born':3,'bundle':'b0','result':'誕生'},
          bundle(4,4,'high',3,'b1'),bundle(4,5,'different',5,'b2'),
          {'kind':'recv','agent':5,'t':4,'R':'other','R_born':4,'bundle':'b1','result':'同化'},
          bundle(5,6,'other',4,'b3')]
    src.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    before=sha256(src.read_bytes()).hexdigest()
    write_lineage(src,out,[0]*4+[1]*4)
    assert before==sha256(src.read_bytes()).hexdigest()
    emitted={r['bundle']:r for r in map(json.loads,out.read_text().splitlines()) if r['kind']=='utterance'}
    assert emitted['b1']['parents']==['b0'] and emitted['b3']['parents']==['b1']
    assert emitted['b2']['parents']==[] and emitted['b0']['group']==0 and emitted['b1']['group']==1
