"""既存のAPIの送信形で、小さな要求を一回だけ送り、鍵を出さずに接続を記録する。"""
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import hashlib, json, os, sys, urllib.request, urllib.error

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'source/llm_trial'))
import api

def now(): return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
def save(name,value): (ROOT/name).write_text(json.dumps(value,ensure_ascii=False,indent=1)+'\n')

ledger=Path('/Users/tatsu-admin/llm_trial_out/費用.jsonl')
raw=ledger.read_bytes()
snapshot={'time':now(),'path':str(ledger),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
          'rows':len(raw.splitlines()),'cost':sum(json.loads(l)['cost'] for l in raw.splitlines()),'task_limit_dollars':10.0}
save('ledger_before.json',snapshot)
record={'started':now(),'key_available':bool(os.environ.get('ANTHROPIC_API_KEY')),'HTTP_attempts':0}
def single_post(url,body,headers,timeout=60):
    record['HTTP_attempts']+=1
    req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={**headers,'User-Agent':api.UA,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as response:
        record['HTTP_status']=response.status
        return json.load(response)
api._post=single_post
api.set_ledger(str(ledger))
api.LIMIT=snapshot['cost']+10.0
try:
    if not record['key_available']: raise KeyError('ANTHROPIC_API_KEY')
    response,usage,cost=api.claude_chat('claude-sonnet-5-5',[{'role':'user','content':'Reply only OK.'}],
        max_tokens=64,what='Codex ドア割合 2026-10-03 接続',effort='medium',display='summarized')
    save('preflight_response.json',response)
    after=ledger.read_bytes()
    assert after[:len(raw)]==raw,'既存の帳簿の前半が変わった'
    record.update(ok=True,usage=usage,cost=cost,response_meta=api.response_meta(response,usage),
                  ledger_prefix_unchanged=True,finished=now())
except Exception as error:
    record.update(ok=False,error_type=type(error).__name__,finished=now())
    if isinstance(error,urllib.error.HTTPError):
        record['HTTP_status']=error.code
        reason=error.read(1500).decode('utf-8','replace')
    elif isinstance(error,KeyError): reason='ANTHROPIC_API_KEY が環境にない'
    else: reason=str(error)
    for name in ('ANTHROPIC_API_KEY','TOGETHER_API_KEY'):
        key=os.environ.get(name)
        if key: reason=reason.replace(key,'[redacted]')
    record['reason']=reason
save('preflight.json',record)
print(json.dumps(record,ensure_ascii=False))
raise SystemExit(0 if record['ok'] else 1)
