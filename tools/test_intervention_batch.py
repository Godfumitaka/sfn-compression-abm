"""CSVの識別子と、本体hash・試行表を混同しない厳密な関門を検査する。"""
import gzip,hashlib,json,tempfile,unittest
from pathlib import Path
import seal_intervention_batch as batch,seal_memory_rebuild as rebuild


class Gates(unittest.TestCase):
    def test_csv_keeps_ids_selection_and_no_material_distinct(self):
        rec={'world':2,'seed':1,'trial':5,'day':'e','shop':'甲','selector':'N3','classification':'distinction_loss',
             'original_R':'old','original':{'outcome':'外れ','predicate':'p','arguments':['a','b']},
             'restored':[],'unrestored':[],'i':{'outcome':'黙り'},'ii':None,'iii_a':{'outcome':'正解'},
             'iii_b':{'outcome':'外れ','selected_R':'old','added_selected':False},
             'iii_c':{'status':'材料なし','material_trials':[2]}}
        row=batch.flatten(rec)
        self.assertEqual((row['world'],row['seed'],row['trial']),(2,1,5))
        self.assertFalse(row['iii_b_added_selected'])
        self.assertEqual(row['iii_c_status'],'材料なし');self.assertEqual(row['iii_c_outcome'],'')
        self.assertEqual(row['baseline_arguments'],'["a", "b"]')

    def test_reference_table_stops_at_the_next_seed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with gzip.open(root/'trials.tsv.gz','wb') as f:
                f.write(b'\t'.join([b'column']*11)+b'\n1\tfirst\n2\tsecond\n99\tdo_not_use\n')
            header,rows=rebuild.table_rows(root,1)
            self.assertEqual(rows,[b'1\tfirst\n'])

    def test_same_trial_table_does_not_override_different_body_hash(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'run';ref=Path(td)/'reference';cell='cell';ref.mkdir()
            side=root/'side'/cell;side.mkdir(parents=True)
            (side/'seed001.jsonl').write_text(json.dumps({'kind':'v39','trial':0,'bits_after':1.0,'defs':0})+'\n')
            path=root/'ledgers/cells'/cell;path.mkdir(parents=True)
            record={'prediction_order':0,'prediction_kind':'Abstain','hit':0,'f_fired':False,
                    'state_snapshot':{'kind':'full'},'abstain_reason':'no_prototype'}
            original=(json.dumps(record)+'\n').encode();changed=(json.dumps(record,indent=None,separators=(', ',':  '))+'\n').encode()
            with gzip.open(path/'seed001.jsonl.gz','wb') as f:
                f.write((json.dumps({'run_seed':1,'code_commit':rebuild.BASE})+'\n').encode());f.write(changed)
            (ref/'sha256.jsonl').write_text(json.dumps({'seed':1,'cell':cell,'body_sha256':hashlib.sha256(original).hexdigest()})+'\n')
            with gzip.open(ref/'trials.tsv.gz','wb') as f:
                f.write(b'\t'.join([b'column']*11)+b'\n1\t0\t0\ta\tno_prototype\t0\t\t\t\t1.0\t0\n')
            result=rebuild.verify(root,1,ref)
            self.assertTrue(result['table_match']);self.assertEqual(result['different_table_rows'],0)
            self.assertFalse(result['body_hash_match'])


if __name__=='__main__':unittest.main()
