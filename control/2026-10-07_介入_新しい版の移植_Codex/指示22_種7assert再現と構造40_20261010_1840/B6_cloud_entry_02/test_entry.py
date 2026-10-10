"""受付入口の停止条件の小例。模型・クラウドの実関門ではない。"""
from pathlib import Path
from unittest.mock import patch
import copy, gzip, json, unittest
import run_B6 as run

FIXTURES=Path(__file__).resolve().parent/'structural_fixtures_01'
FIXTURES.mkdir(exist_ok=False)
SPEC=run.read(run.HERE/'spec.json')

class EntryTests(unittest.TestCase):
    def gate_root(self,name,wrong=None,missing=None):
        root=FIXTURES/name; (root/'gates').mkdir(parents=True,exist_ok=False)
        mapping=run.read(run.HERE/'gate_mapping.json')
        names=set(mapping['additional_original_prerequisite'])
        for values in mapping['mapping'].values():names.update(values)
        for name in names:
            if name==missing:continue
            g=dict(passed=True,candidate=run.BASE,host='synthetic-only')
            if wrong is not None:g.update(wrong)
            run.save(root/'gates'/name,g)
        return root

    def test_fixed_spec_and_phase(self):
        run.validate(copy.deepcopy(SPEC))
        for key,value in [('phase','production'),('models',1),('seeds',[2]),('commit',run.BASE),('production_started',True)]:
            changed=copy.deepcopy(SPEC);changed[key]=value
            with self.assertRaises(AssertionError):run.validate(changed)
        changed=copy.deepcopy(SPEC);changed['model_argv'][changed['model_argv'].index('--trial-count')+1]='1740'
        with self.assertRaises(AssertionError):run.validate(changed)

    def test_all_legacy_conditions_expand(self):
        root=self.gate_root('all_conditions')
        with patch.object(run,'host',return_value='synthetic-only'):
            self.assertEqual(len(run.gates(SPEC,root)),8)

    def test_each_missing_gate_refuses(self):
        mapping=run.read(run.HERE/'gate_mapping.json')
        names=set(mapping['additional_original_prerequisite'])
        for values in mapping['mapping'].values():names.update(values)
        with patch.object(run,'host',return_value='synthetic-only'):
            for i,name in enumerate(sorted(names)):
                root=self.gate_root(f'missing_{i}',missing=name)
                with self.assertRaises(FileNotFoundError):run.gates(SPEC,root)

    def test_failed_wrong_version_or_other_boot_refuses(self):
        with patch.object(run,'host',return_value='synthetic-only'):
            for i,wrong in enumerate([dict(passed=False),dict(candidate=run.C),dict(host='other-boot')]):
                root=self.gate_root(f'wrong_{i}',wrong=wrong)
                with self.assertRaises(AssertionError):run.gates(SPEC,root)

    def test_old_stop_refuses(self):
        root=self.gate_root('stopped');run.save(root/'STOP.json',dict(reason='synthetic-only'))
        with self.assertRaises(AssertionError):run.gates(SPEC,root)

    def test_real_candidate_is_only_the_named_audit_patch(self):
        source=run.HERE.parents[1]/'source_coll_D_instruction20'
        run.source_check(source)

    def case(self,name,fault=None):
        e=FIXTURES/name/'evidence';o=FIXTURES/name/'output';e.mkdir(parents=True,exist_ok=False)
        run.save(e/'resource.json',dict(exitcode=0,warnings=[],protected_unchanged=True))
        run.save(e/'protected-before.json',{});run.save(e/'protected-after.json',{})
        manifest=[];agents=[]
        for i in range(8):
            seed=1+1000*i;cell='synthetic_cell'
            folder=o/'ledgers/cells'/cell;folder.mkdir(parents=True,exist_ok=True)
            path=folder/f'seed{seed:03d}.jsonl.gz'
            with gzip.open(path,'wt') as f:
                f.write(json.dumps(dict(code_commit=run.C,trial_count=20,f_setting=0.1))+'\n')
                for t in range(20):f.write(json.dumps(dict(prediction_order=t,f_realized=0.1))+'\n')
            d=dict(code_commit=run.C,trial_count=20,cell=cell,seed=seed,ledger_bytes=path.stat().st_size)
            run.save(folder/f'seed{seed:03d}.done',d)
            manifest.append(d);agents.append(dict(d,v39=dict(not_in_dictionary=0),v311c=dict(dictionary_checks=40)))
            for suffix in ('rng.jsonl','model-rng.jsonl','performance.jsonl'):
                if fault=='missing_rng' and i==7 and suffix=='rng.jsonl':continue
                with (e/f'agent{i}.{suffix}').open('x') as f:
                    for t in range(20):f.write(json.dumps(dict(trial=t,python_global_unchanged=True))+'\n')
            run.save(e/f'agent{i}.cstar-final.json',dict(synthetic=True))
            with gzip.open(e/f'agent{i}.final-sme.jsonl.gz','wt') as f:f.write('synthetic state\n')
            with (e/f'agent{i}.validation.jsonl').open('x') as f:
                for phase in ('begin','end'):f.write(json.dumps(dict(phase=phase))+'\n')
            for category in ('side','attention','retention','evictions'):
                folder=o/category/cell;folder.mkdir(parents=True,exist_ok=True)
                run.save(folder/f'seed{seed:03d}.summary.json',dict(tombstone_enabled=True,tombstone_hits=0,last_trial=19))
            if not (fault=='missing_D' and i==7):
                with (o/'side'/cell/f'seed{seed:03d}.useforget.jsonl').open('x') as f:
                    for trial in range(20):f.write(json.dumps(dict(trial=trial))+'\n')
            with (o/'retention'/cell/f'seed{seed:03d}.jsonl').open('x') as f:
                for trial in range(20):f.write(json.dumps(dict(trial=trial,tau=0.4))+'\n')
            if fault=='changed_D_probe' and i==7:
                run.save(o/'retention'/cell/f'seed{seed:03d}.jsonl.probe_checks.json',
                         [dict(unchanged=False,before_sha256='before',after_sha256='after')])
        if fault=='wrong_manifest_bytes':manifest[7]=dict(manifest[7],ledger_bytes=0)
        with (o/'manifest.jsonl').open('x') as f:
            for m in manifest:f.write(json.dumps(m)+'\n')
        if fault=='agent_error':agents[7]=dict(type='error',error='synthetic-only')
        (o/'comm').mkdir();run.save(o/'comm/run001.summary.json',dict(trials=20,errors=[],agents=agents))
        return e,o

    def test_all_eight_completion_records(self):
        e,o=self.case('complete_eight')
        run.verify_completed(dict(host='synthetic-only'),e,o)
        self.assertTrue(run.read(e/'verification_01.json')['passed'])

    def test_outer_zero_is_insufficient(self):
        for fault in ('agent_error','missing_rng','wrong_manifest_bytes','missing_D','changed_D_probe'):
            e,o=self.case(fault,fault)
            with self.assertRaises(SystemExit):run.verify_completed(dict(host='synthetic-only'),e,o)
            result=run.read(e/'verification_01.json')
            self.assertFalse(result['passed']);self.assertIn('first_error',result)

    def test_D_and_serial_refuses(self):
        changed=copy.deepcopy(SPEC);changed['model_argv'].append('--v311c-serial')
        with self.assertRaises(AssertionError):run.validate(changed)

    def test_missing_intervention_prerequisite_refuses(self):
        path=FIXTURES/'empty_envelope.json';run.save(path,{})
        with self.assertRaises(KeyError):run.intervention_gates(path)

    def test_unchanged_twenty_does_not_claim_actual_collective_probe(self):
        e,o=self.case('no_actual_collective_probe')
        run.verify_completed(dict(host='synthetic-only'),e,o)
        proof=run.read(e/'verification_01.json')
        self.assertFalse(proof['actual_collective_probe_executed'])
        self.assertTrue(proof['actual_probe_invariance_not_claimed'])

if __name__=='__main__':unittest.main(verbosity=2)
