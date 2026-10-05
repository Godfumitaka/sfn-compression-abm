"""新関門の試行表・差分指紋と、旧関門の保存を構造で確認する。"""
import gzip,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import seal_memory_rebuild as rebuild

class MacGateTests(unittest.TestCase):
    def make(self,root,corrupt=False,table_difference=False):
        from abm.loop import _json_bytes
        cell='test';side=root/'side'/cell;led=root/'ledgers/cells'/cell
        side.mkdir(parents=True);led.mkdir(parents=True)
        (side/'seed001.jsonl').write_text(''.join(json.dumps({'kind':'v39','trial':t,'bits_after':12,'defs':1})+'\n' for t in range(2)))
        rows=[]
        for t in range(2):
            rows.append({'prediction_order':t,'state_snapshot':{'kind':'full','value':{'number':1}} if t==0 else {'kind':'delta','changes':{'number':{'set':2}}},
                         'agent_state_snapshot_hash':hashlib.sha256(_json_bytes({'number':t+1})).hexdigest(),
                         'prediction_kind':'EdgePrediction','hit':1,'f_fired':True,'held_out_is_door':True,
                         'shop_type':'甲','shop_cue':'n','door_pred':'X'})
        if corrupt:rows[1]['agent_state_snapshot_hash']='bad'
        with gzip.open(led/'seed001.jsonl.gz','wt') as stream:
            stream.write(json.dumps({'run_seed':1,'code_commit':rebuild.BASE})+'\n')
            stream.writelines(json.dumps(r)+'\n' for r in rows)
        expected=[f'1\t{t}\t1\tc\t\t1\t甲\tn\tX\t12\t1\n'.encode() for t in range(2)]
        if table_difference:expected[1]=expected[1].replace(b'\tc\t',b'\tw\t')
        return {'cell':cell,'body_sha256':'original-different'},b'header\n',expected

    def verify(self,corrupt=False,table_difference=False):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);ref,header,rows=self.make(root,corrupt,table_difference)
            with patch.object(rebuild,'reference_hash',return_value=ref),patch.object(rebuild,'table_rows',return_value=(header,rows)):
                return rebuild.verify(root,1,root,internal=True)

    def test_all_delta_states_are_checked(self):
        result=self.verify();self.assertTrue(result['internal_state_match']);self.assertEqual(result['internal_state_trials'],2)
        self.assertTrue(rebuild.gate_passed(result,True));self.assertFalse(rebuild.gate_passed(result,False))

    def test_corrupted_trial_stops(self):
        with self.assertRaisesRegex(RuntimeError,'試行1'):self.verify(corrupt=True)

    def test_table_mismatch_is_not_exempted(self):
        result=self.verify(table_difference=True)
        self.assertTrue(result['internal_state_match']);self.assertFalse(rebuild.gate_passed(result,True))

    def test_seed_bound_is_checked_before_reading(self):
        with self.assertRaises(ValueError):rebuild.one(rebuild.ARMS[0],21,Path('/unused'),mac_rebuild=True)

if __name__=='__main__':unittest.main()
