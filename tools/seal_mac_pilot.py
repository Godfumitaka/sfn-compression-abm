"""既存のlg種1で新関門と全ドア介入を接続確認する。"""
from pathlib import Path
import json
import seal_memory_rebuild as rebuild
import seal_mac_intervention as diag

ROOT=Path(__file__).resolve().parents[2]
arm='lambda_grid/lg_w2_A_lam0.065'
material=ROOT/'memory_rebuild_2026-10-05/lg_w2_A_lam0.065'
dest=ROOT/'mac_rebuild_approved_2026-10-05/interventions/lg_w2_A_lam0.065'
rebuild.one(arm,1,material,mac_rebuild=True)
result=diag.one(material,dest,1)
print(json.dumps(result,ensure_ascii=False),flush=True)
