"""既存の段階を呼ぶ実行側。既存帳簿へ足し、要求ごとの最大費用を先に確保する。"""
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
from pathlib import Path
import hashlib, json, os, sys, urllib.error, urllib.request

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'source/llm_trial'))
import api
import fullhist_stages as stages

fraction=float(sys.argv[1]);assert fraction in (0.75,0.25)
label=f'f{round(fraction*100):03d}'
OUT=ROOT/'outputs'/label;OUT.mkdir(parents=True,exist_ok=True)
PREFIX='Codex ドア割合 2026-10-03'
LEDGER=Path('/Users/tatsu-admin/llm_trial_out/費用.jsonl')
CAP=Decimal('10')
reservations=[]

def now(): return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
def save(name,value): (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=1)+'\n')
def event(value):
    with (OUT/'budget_events.jsonl').open('a') as stream:
        stream.write(json.dumps({'time':now(),**value},ensure_ascii=False)+'\n')
def known_spent():
    return sum((Decimal(str(json.loads(line)['cost'])) for line in LEDGER.read_text().splitlines()
                if line and json.loads(line)['what'].startswith(PREFIX)),Decimal(0))
def reserved():
    return sum((Decimal(r['maximum_dollars']) for r in reservations if r['status'] in ('pending','response_received','uncertain')),Decimal(0))
def spent(): return float(known_spent()+reserved())

set_original=api.set_ledger
api.set_ledger=lambda ignored:set_original(str(LEDGER))
api.set_ledger(None)
api.spent=spent
api.LIMIT=10.0
book_original=api._book
def book(model,usage_in,usage_out,price,what):
    pending=[r for r in reservations if r['status']=='response_received']
    assert len(pending)==1,pending
    cost=(usage_in*price['input']+usage_out*price['output'])/1e6
    assert Decimal(str(cost))<=Decimal(pending[0]['maximum_dollars'])
    value=book_original(model,usage_in,usage_out,price,f'{PREFIX} {label} {what}')
    pending[0].update(status='booked',actual_dollars=str(value))
    event({'event':'booked','reservation':pending[0],'known_dollars':str(known_spent()),'reserved_dollars':str(reserved())})
    assert known_spent()+reserved()<=CAP
    return value
api._book=book

open_original=urllib.request.urlopen
def guarded_open(request,*args,**kwargs):
    url=request.full_url
    body=json.loads(request.data)
    reservation=None
    if url.endswith('/messages'):
        price=api.CLAUDE_PRICE[body['model']]
        # 入力は要求全体のバイト数の4倍＋4096、出力は既存の最大トークン数で上側に確保。
        maximum=(Decimal(len(request.data)*4+4096)*Decimal(str(price['input']))
                 +Decimal(body['max_tokens'])*Decimal(str(price['output'])))/Decimal(1000000)
        if known_spent()+reserved()+maximum>CAP:
            raise api.Budget('次の要求の最大費用を確保すると今回の10ドルを超える')
        reservation={'request_number':len(reservations)+1,'maximum_dollars':str(maximum),'status':'pending'}
        reservations.append(reservation)
        event({'event':'reserve','reservation':reservation,'known_dollars':str(known_spent()),'reserved_dollars':str(reserved())})
    with (OUT/'requests.jsonl').open('a') as stream:
        stream.write(json.dumps({'time':now(),'url':url,'body_utf8':request.data.decode(),
                                'body_sha256':hashlib.sha256(request.data).hexdigest()},ensure_ascii=False)+'\n')
    try:
        response=open_original(request,*args,**kwargs)
    except urllib.error.HTTPError as error:
        if reservation:
            reservation.update(status='rejected' if 400<=error.code<500 else 'uncertain',http_status=error.code)
            event({'event':'HTTP_error','reservation':reservation})
        raise
    except Exception as error:
        if reservation:
            reservation.update(status='uncertain',error_type=type(error).__name__)
            event({'event':'connection_error','reservation':reservation})
        raise
    if reservation:
        reservation.update(status='response_received',http_status=response.status)
    return response
urllib.request.urlopen=guarded_open

try:
    sys.argv=['fullhist_stages.py',str(OUT),'2','S基準','1','--door-fraction',str(fraction)]
    save('run.json',{'start':now(),'argv':sys.argv,'ledger':str(LEDGER),'task_limit_dollars':10,
                     'known_dollars_before':str(known_spent()),'transport_retries':'既存のAPIのまま。未確定の要求は最大費用を確保したまま。'})
    stages.main()
    assert reserved()==0,'費用が未確定の要求があるため、次の段階には進まない'
    save('finished.json',{'time':now(),'complete':True,'known_task_dollars':str(known_spent()),'reserved_dollars':str(reserved())})
except Exception as error:
    reason=str(error)
    for name in ('ANTHROPIC_API_KEY','TOGETHER_API_KEY'):
        key=os.environ.get(name)
        if key:reason=reason.replace(key,'[redacted]')
    result={'time':now(),'error_type':type(error).__name__,'reason':reason,
            'known_task_dollars':str(known_spent()),'reserved_dollars':str(reserved())}
    save('stopped.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    raise SystemExit(1)
