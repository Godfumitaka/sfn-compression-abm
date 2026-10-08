"""指示9の先にそろった同機械の組を確認。模型を開始しない。"""
def first_pair_check(decision,v,gate):
    """両機械の確認済み記録から、先にそろった組の判定を受け取る。"""
    assert decision['model_commit']==v['model_commit'] and decision['observer_sha256']==v['observer_sha256']
    candidates=decision['pairs'];assert set(candidates)=={'Mac','cloud'}
    finished=[]
    for name,p in candidates.items():
        assert p['checked_epoch']>=gate['finished_epoch'], '片側の進み具合を推測しない'
        if p['state']=='waiting':continue
        assert p['state']=='completed'
        finished.append((p['finished_epoch'],name,p['comparison']))
    assert finished
    _,name,proof=min(finished,key=lambda x:x[:2])
    assert name==decision['selected_pair'] and proof['passed'] and proof['mismatching_files']==0
    assert proof['file_count']>0 and len(proof['files'])==proof['file_count']
    assert all(r['equal'] and r['left_exists'] and r['right_exists'] and
               r['left_sha256']==r['right_sha256'] and r['mismatching_bytes']==0 for r in proof['files'])
    if name=='cloud':assert proof==gate, '現在のクラウドの組の原比較を使う'

