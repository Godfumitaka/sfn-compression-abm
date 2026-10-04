"""同じ表の集計・一問ずつの要約・記号一致・費用照合を保存する。"""
from common import *
from collections import Counter
import csv
import re
import shutil
import subprocess
import fullhist_report as existing

CASES = existing.CASES
NAMES = {'baseline': '既存 medium', 'A': 'A：一文変更・medium', 'B': 'B：元の指示・max'}
stimuli = json.loads((DEST / 'stimuli.json').read_text())
vocab = stimuli['vocab']
truth = {c: stimuli['tests'][i*4]['answer'] for i,c in enumerate(CASES)}
seal = {'n': vocab['sig_n'], 'e': vocab['sig_e']}

def symbol_matches(symbol, text):
    return len(re.findall(r'(?<![A-Za-z0-9_])'+re.escape(symbol)+r'(?![A-Za-z0-9_])', text))

def costs(rows):
    tries = [t for r in rows for t in r['試み']]
    thinking = [(t['使用量'].get('output_tokens_details') or {}).get('thinking_tokens') for t in tries]
    known = [n for n in thinking if n is not None]
    return {'calls': len(tries), 'input': sum(t['使用量']['input_tokens'] for t in tries),
            'output': sum(t['使用量']['output_tokens'] for t in tries), 'thinking': sum(known),
            'thinking_missing': len(thinking)-len(known), 'thinking_zero': sum(n == 0 for n in known),
            'thinking_mean': sum(known)/len(known) if known else None, 'thinking_max': max(known, default=None),
            'dollars': str(sum((Decimal(str(t['費用'])) for t in tries), Decimal(0)))}

def main():
    stats = []
    hits = []
    for label in ('baseline', 'A', 'B'):
        if label != 'baseline':
            assert json.loads((DEST / label / 'finished.json').read_text())['complete']
        rows = [r for r in read_rows(DEST / label / 'trials.jsonl') if r['段'] == '最後の試験']
        assert len(rows) == 16 and [r['i'] for r in rows] == list(range(16))
        per = {c: [r for r in rows if r['場合'] == c] for c in CASES}
        assert all(len(rs) == 4 for rs in per.values())
        modal = {c: sorted(Counter(r.get('answer') for r in rs if r.get('answer')).items(), key=lambda x:(-x[1],x[0]))[0][0] for c, rs in per.items()}
        errors = Counter()
        for r in rows:
            assert r['正解'] == truth[r['場合']]
            if r['判定'] == '誤答':
                typ, cue = r['場合'].split('・')
                if cue == 'e' and r.get('answer') == truth[typ+'・n']:
                    errors['例外で通常の答え'] += 1
                elif cue == 'n' and r.get('answer') == truth[typ+'・e']:
                    errors['通常で例外の答え'] += 1
                else:
                    errors['その他の記号'] += 1
            q = r['i']
            t = r['試み'][-1]
            text = t.get('推論の中身') or ''
            assert t['応答の model'] == MODEL
            expected_word = seal[r['場合'].split('・')[1]]
            scene = stimuli['tests'][q]['text']
            seal_lines = [line for line in scene.splitlines() if re.search(r': '+expected_word+r'\(o\d+\)', line)]
            assert len(seal_lines) == 1
            summary_file = DEST / label / 'summaries' / f'q{q:02d}.txt'
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            # APIから返ったsummarized文字列を全文保存。推論なしは空ファイルにする。
            summary_file.write_text(text)
            counts = {word: symbol_matches(word, text) for word in seal.values()}
            h = {'condition': label, 'q': q, 'case': r['場合'], 'answer': r.get('answer'),
                 'confidence': r.get('confidence'), 'best_correct': r.get('最もありそうな答えが正しい', False),
                 'summary_nonempty': bool(text), 'thinking_block_status': t['推論の中身の返り方'],
                 'thinking_tokens': (t['使用量'].get('output_tokens_details') or {}).get('thinking_tokens'),
                 'current_seal_word': expected_word, 'current_seal_line': seal_lines[0],
                 'current_seal_count': counts[expected_word], 'any_seal_count': sum(counts.values()),
                 'pilu_count': counts[seal['n']], 'vadi_count': counts[seal['e']],
                 'summary_path': str(summary_file.relative_to(DEST)), 'summary_sha256': sha(text.encode()),
                 'attempt': len(r['試み'])}
            hits.append(h)
            save(summary_file.with_suffix('.json'), h)
        wrong = [r.get('confidence') for r in rows if r['判定'] == '誤答']
        groups = {name: [r for r in rows if r['場合'].endswith(cue)] for name,cue in [('通常','n'),('例外','e')]}
        own_hits = [h for h in hits if h['condition'] == label]
        ex_hits = [h for h in own_hits if h['case'].endswith('e')]
        stat = {'condition': label, 'name': NAMES[label], 'pattern': existing.pattern(modal,truth), 'modal':modal,
                'best_correct':sum(r.get('最もありそうな答えが正しい',False) for r in rows),
                'best_correct_by_day':{k:sum(r.get('最もありそうな答えが正しい',False) for r in rs) for k,rs in groups.items()},
                'best_correct_by_case':{c:sum(r.get('最もありそうな答えが正しい',False) for r in rs) for c,rs in per.items()},
                'actual_by_day':{c:dict(Counter(r['判定'] for r in rs)) for c,rs in groups.items()},
                'errors':dict(errors), 'wrong_confidence':wrong, 'high_confidence_wrong':sum(v>=0.9 for v in wrong),
                'answers_by_case':{c:[r.get('answer') for r in rs] for c,rs in per.items()},
                'confidence_by_case':{c:[r.get('confidence') for r in rs] for c,rs in per.items()},
                'costs':costs(rows), 'exception_summary_matching':{'questions':8,
                    'summary_nonempty':sum(h['summary_nonempty'] for h in ex_hits),
                    'current_seal_questions':sum(h['current_seal_count']>0 for h in ex_hits),
                    'any_seal_questions':sum(h['any_seal_count']>0 for h in ex_hits),
                    'current_seal_occurrences':sum(h['current_seal_count'] for h in ex_hits),
                    'any_seal_occurrences':sum(h['any_seal_count'] for h in ex_hits)}}
        stats.append(stat)
    raw = LEDGER.read_bytes()
    before = json.loads((DEST / 'ledger_before.json').read_text())
    assert sha(raw[:before['bytes']]) == before['sha256'], '既存帳簿の前半が変わった'
    ledger_rows = [json.loads(x) for x in raw.splitlines()]
    own = [r for r in ledger_rows if r['what'].startswith(PREFIX)]
    total = sum((Decimal(str(r['cost'])) for r in own), Decimal(0))
    assert total <= CAP
    audits = []
    for label in ('A','B'):
        stat = next(s for s in stats if s['condition'] == label)
        reqs = read_rows(DEST / label / 'requests.jsonl')
        planned = read_rows(DEST / label / 'planned_requests.jsonl')
        booked = [r for r in own if r['what'].startswith(PREFIX+' '+label+' ')]
        assert booked == read_rows(DEST / label / 'ledger_rows.jsonl')
        assert len(reqs) == len(booked) == stat['costs']['calls']
        assert sum(r['in'] for r in booked) == stat['costs']['input']
        assert sum(r['out'] for r in booked) == stat['costs']['output']
        assert sum((Decimal(str(r['cost'])) for r in booked), Decimal(0)) == Decimal(stat['costs']['dollars'])
        for req in reqs:
            body = json.loads(req['body_utf8'])
            expected = json.loads(json.dumps(planned[req['q']]['body']))
            if req['attempt']>1:
                import stage4
                expected['messages'][0]['content'] += '\n'+stage4.STRICT
            assert body == expected and sha(req['body_utf8'].encode()) == req['body_sha256']
            r = json.loads((DEST / label / 'responses' / f"q{req['q']:02d}_try{req['attempt']}.json").read_text())
            assert r['model'] == MODEL
        assert not (DEST / label / 'stopped.json').exists()
        audits.append({'condition':label,'calls':len(reqs),'all_requests_match_planned':True,
                       'ledger_matches_trials':True,'response_model':MODEL,'unresolved_requests':0})
    offline = json.loads((DEST / 'offline_checks.json').read_text())
    assert all(sha((SOURCE / name).read_bytes()) == fingerprint for name,fingerprint in offline['source_files'].items())
    save(DEST / 'execution_audit.json', {'time':now(),'checks':audits,'training_calls':0,'new_messages_calls':len(own),
         'ledger_prefix_unchanged':True,'source_files_unchanged':True,'known_task_dollars':str(total),
         'task_limit_dollars':4,'baseline_cost_in_task_budget':False})
    save(DEST / 'aggregate.json', {'time':now(),'conditions':stats,'known_task_dollars':str(total)})
    (DEST / '費用_今回.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in own)+'\n')
    with (DEST / 'seal_summary_matching.tsv').open('w') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(hits[0]),delimiter='\t')
        writer.writeheader();writer.writerows(hits)
    save(DEST / 'seal_summary_matching.json', {'method':json.loads((DEST/'scope.json').read_text())['summary_matching'],
         'seal_words':seal,'questions':hits})
    scripts = DEST / 'scripts';scripts.mkdir(exist_ok=True)
    for name in ('common.py','prepare.py','run_condition.py','design_estimates.py','report.py'):
        shutil.copyfile(ROOT / name,scripts / name)
    write_report(stats,total,hits)
    print(json.dumps({'complete':True,'task_dollars':str(total),
          'report':str(ROOT/'results/control/2026-10-04_LLMの確かめ_考える量_Codex.md')},ensure_ascii=False))

def write_report(stats,total,hits):
    lines = ['# LLMの考える量と指示の一文（Codex、2026-10-04）','',
             f'集計時刻：{now()}。Sonnet 5.5（{MODEL}）だけを使用。世界2・組1・ドア割合0.5。条件A・Bの最後の試験16問ずつを実行した。新しい学習の問い合わせは0回。今回の費用は{total:.6f}ドル、上限4ドル。','',
             '引き継ぎ：`control/2026-10-03_LLMのドアの割合_Codex.md`、`mac/llm_door_20261003/`。コードの土台は`codex/llm-door-fraction-2026-10-03`の`73876dc2f020a70da02419c76bea0a3067164593`。そのコードは変更していない。今回の報告の枝は`codex/llm-effort-instruction-2026-10-04`、土台は結果の枝`results-2026-09-27`の`2ef70c93`。','',
             '40場面の履歴・場面と正解・順番・伏せ方・番号・16問の文字列は既存の条件と同じ。保存済みの要求本体56件のうち最後の16件を使い、再生成した既存の履歴・問いと全件照合した。試験の答えや推論を次の問いへ持ち越さない。','',
             '| 条件 | 最後の指示 | effort |','|---|---|---|',
             f'| 既存 medium | `{OLD}` | medium |',f'| A | `{NEW}` | medium |',f'| B | `{OLD}` | max |','',
             'Aはこの一文だけ、Bは`output_config.effort`だけを変更。模型・adaptive・summarized・JSON schema・出力上限32000は同じ。何が重要かを示す文は足していない。形の崩れの扱いは既存と同じ初回＋最大2回、上限切れは再試行しない。通信失敗では費用が未確定の要求を再送せず停止する設定とした。今回、形の再試行・通信失敗はいずれも0回。','',
             '最有力が正しい数は、黙った場合の最有力も数える既存の基準。実際の正解・外れ・黙りは別表。答え方の型は、四つの場合の最頻の記号の並びによる既存の分類（同数なら記号名の順）。','',
             '| 条件 | 記録 | 最有力が正しい/16 | 通常/8 | 例外/8 | 答え方の型 |','|---|---|---:|---:|---:|---|']
    for s in stats:
        lines.append(f"| {s['name']} | {'既存' if s['condition']=='baseline' else '今回'} | {s['best_correct']} | {s['best_correct_by_day']['通常']} | {s['best_correct_by_day']['例外']} | {s['pattern']} |")
    lines += ['', '| 条件 | 甲・通常/4 | 甲・例外/4 | 乙・通常/4 | 乙・例外/4 |','|---|---:|---:|---:|---:|']
    for s in stats:
        lines.append('| '+s['name']+' | '+' | '.join(str(s['best_correct_by_case'][c]) for c in CASES)+' |')
    lines += ['', '| 条件 | 日 | 実際の正解 | 外れ | 黙り | 形の崩れ | 上限で切れた |','|---|---|---:|---:|---:|---:|---:|']
    for s in stats:
        for day in ('通常','例外'):
            lines.append('| '+s['name']+' | '+day+' | '+' | '.join(str(s['actual_by_day'][day].get(k,0)) for k in ('正解','誤答','黙り','形の崩れ','上限で切れた'))+' |')
    lines += ['', '外れの型と確信：','',
              '| 条件 | 例外で通常の答え | 通常で例外の答え | その他の記号 | 外れの確信（全件） | 確信0.9以上の外れ |','|---|---:|---:|---:|---|---:|']
    for s in stats:
        lines.append('| '+s['name']+' | '+' | '.join(str(s['errors'].get(k,0)) for k in ('例外で通常の答え','通常で例外の答え','その他の記号'))+' | '+('・'.join(str(v) for v in s['wrong_confidence']) or '対象なし')+' | '+str(s['high_confidence_wrong'])+' |')
    lines += ['', '| 条件 | 場合 | 答え（4問） | 確信（4問） |','|---|---|---|---|']
    for s in stats:
        for c in CASES:
            lines.append(f"| {s['name']} | {c.replace('n','通常').replace('e','例外')} | {'・'.join(str(v) for v in s['answers_by_case'][c])} | {'・'.join(str(v) for v in s['confidence_by_case'][c])} |")
    lines += ['', '推論トークンは応答の`usage.output_tokens_details.thinking_tokens`。出力トークンに含まれるので、費用に二重加算しない。summaryの文字数とは別の量。','',
              '| 条件 | 部分 | 問い合わせ | 入力 | 出力 | 推論 | 推論0の問い | 推論の平均 | 推論の最大 | 費用（ドル） |','|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for s in stats:
        c = s['costs']
        assert c['thinking_missing'] == 0
        lines.append(f"| {s['name']} | 最後の試験 | {c['calls']} | {c['input']} | {c['output']} | {c['thinking']} | {c['thinking_zero']} | {c['thinking_mean']:.2f} | {c['thinking_max']} | {Decimal(c['dollars']):.6f} |")
    lines += ['', '単価は入力100万トークンあたり2ドル、出力10ドルで、既存の費用帳簿と同じ。2026-10-04に[公式料金表](https://platform.claude.com/docs/en/about-claude/pricing)を照合した。[effortの公式文書](https://platform.claude.com/docs/en/build-with-claude/effort)はSonnet 5.5のmaxをサポートしている。[推論の公式文書](https://platform.claude.com/docs/en/build-with-claude/thinking-steering-and-cost)では、summarizedの表示と実際の課金対象の推論トークンは別だと記されている。','',
              f'既存mediumの費用は当時の最後の試験の費用で、今回の4ドルには足さない。今回のA・B合計は{total:.6f}ドル。接続確認用の生成や新しいトークン数APIの要求は送っていない。鍵は前担当と同じ環境変数`ANTHROPIC_API_KEY`から読み、記録に保存していない。既存帳簿`既存の費用.jsonl`へ同じ欄で追記し、開始前の全バイトが残っていることと、今回32要求の使用量・費用が記録と一致することを確認した。','',
              'シールの語の機械集計：通常の語は`pilu`、例外の語は`vadi`。各問の最終試みのsummarized文字列だけを対象とし、大文字小文字を区別、記号の前後にASCII英数字・下線がない完全な語の一致で数える。研究者の問い・答え・シールの行や最終JSONは検索対象に入れない。今のシールの語（例外8問ではvadi）と、pilu/vadiいずれかの語を別々に数える。','',
              '| 条件 | 例外の問い | 要約が非空 | vadiに一致した問い | pilu/vadiのどちらかに一致した問い | vadiの出現数 | pilu/vadiの出現数 |','|---|---:|---:|---:|---:|---:|---:|']
    for s in stats:
        h = s['exception_summary_matching']
        lines.append(f"| {s['name']} | 8 | {h['summary_nonempty']} | {h['current_seal_questions']} | {h['any_seal_questions']} | {h['current_seal_occurrences']} | {h['any_seal_occurrences']} |")
    lines += ['', '要約が空の場合は一致0と数えるが、「推論の塊なし」等の返り方と推論トークンも別欄で残す。この集計は返された要約の文字列の出現を数えたもの。要約への非出現から、模型内部でその語を扱わなかったとは判定しない。','',
              '| 条件 | 問（0始まり） | 場合 | 要約が非空 | vadi出現数 | pilu出現数 |','|---|---:|---|---|---:|---:|']
    for h in hits:
        if h['case'].endswith('e'):
            lines.append(f"| {NAMES[h['condition']]} | {h['q']} | {h['case'].replace('e','例外')} | {'有' if h['summary_nonempty'] else '空'} | {h['vadi_count']} | {h['pilu_count']} |")
    lines += ['', '既存・A・Bの48問すべての要約全文は`mac/llm_effort_instruction_20261004/{baseline,A,B}/summaries/q00.txt`〜`q15.txt`。空の要約も空ファイルとして保存。問いごとのシールの行・一致数・要約の指紋は`seal_summary_matching.tsv`と`.json`、A・Bの要求本体と応答全文は各条件の`requests.jsonl`と`responses/`。基準の原記録・指紋、変更前後の要求の照合、今回の費用行、実行と集計の道具も同じ記録場所に保存した。','']
    lines += ['## 今回の費用帳簿の行','',
              '既存の`既存の費用.jsonl`に追記した32行の写し。Aは0.375334ドル、Bは0.536860ドル、合計0.912194ドル。既存mediumの当時の費用行は今回の追記に含めない。','',
              '```jsonl', (DEST / '費用_今回.jsonl').read_text().rstrip(), '```','',
              '作業の枝（結果の記録）：[codex/llm-effort-instruction-2026-10-04](https://github.com/Godfumitaka/sfn-compression-abm/tree/codex/llm-effort-instruction-2026-10-04)。最初の結果保存コミットは`511bd04b7c8593b64d8d10ddd4b753b321559e9d`。指定の報告ファイルと費用行を同じ作業の枝へ追加した上で、結果の枝`results-2026-09-27`へも保存する。','']
    lines += design_text()
    path = ROOT / 'results/control/2026-10-04_LLMの確かめ_考える量_Codex.md'
    path.parent.mkdir(exist_ok=True)
    path.write_text('\n'.join(lines)+'\n')

def design_text():
    d = json.loads((DEST / 'design_estimates.json').read_text())
    cal = d['calibration']
    lines = ['## 未実行の三案：設計と費用の見積もり','',
             '以下の生成は走らせていない。設計と費用計算に使ったAPI呼び出しは0回。共通の予定はSonnet 5.5だけ・effort medium・adaptive・summarized・元の最後の指示・出力上限32000。A・Bの結果を見て条件を選び直すことはしていない。','',
             f"入力の見積もりは、既存mediumの56要求で較正した式「入力トークン ≈ {cal['slope']:.6f} × 指示本文の文字数 − {abs(cal['intercept']):.2f}」。この56要求内の最大残差は{cal['max_absolute_residual']:.2f}トークン。新しい語彙や模型が書くメモの実測はしていないので、以下は設計値であり請求の保証ではない。出力はJSONの包み25トークン、全問い合わせの推論を1件100又は2000トークンとした二つの仮定。メモ更新では上限分のメモを毎回出すとして足した。再試行は含めず、別に25%の予備費を置く。",'',
             '### (1) 一場面ずつ予測し、自分のメモを書き直す版','',
             '仕様v2の3〜6節を、全40場面でドアを伏せる条件の上で再開する。世界1・2、組1、各世界で全履歴・長いメモ・短いメモを同じ順番・同じ伏せ方で比較する。甲通常16・甲例外4・乙通常16・乙例外4の場面数は維持する。','',
             '各場面で、前のメモと今の場面から予測 → 正解を開示 → 前のメモと今の場面・正解だけでメモ更新、の順。予測と更新は別の問い合わせで、自分の予測は更新に渡さない。会話の履歴も推論要約も持ち越さず、保存したメモだけを次へ渡す。更新指示は仕様v2の「今後の予測に使う記録を上限以内に更新する」だけで、後の格子版が足した三文や、研究者が書いた診断メモは使わない。','',
             '長いメモ1000・短いメモ150トークンは見積もり用の仮置き。正式走行前にSonnet 5.5のcount_tokensで、一場面・甲乙の骨組み全体と四場合の表・短い規則を計測し、仕様v2の条件を満たす上限を固定する。Haikuで測った上限をそのまま確定値として使わない。超過は黙って切らず、長さと上限を知らせて最大2回書き直し、それでも超過なら系列を超過として停止。予測の形の崩れは最大2回再試行、上限切れは再試行なし。更新の形の崩れ・空・切れも初回＋最大2回で停止。元メモ、更新全文、保存メモ、各長さ、再試行をすべて保存する。','',
             '10・20・30・40場面後の固定メモから、ドア四場合4問と共有部分2問を一問ずつ独立に出す。試験の正解は知らせず、メモを更新しない。短いメモだけは、事前に固定した乙の通常と例外の最後の一例ずつを書き戻し、対照には乙の通常の最後の二例を付ける。上限を試験時だけ緩め、元メモ・書き戻し・対照の各ドア4問を別々に測る。両世界で同じ選び方と書式を使い、正式走行前にトークン長を照合する。','',
             '組1では乙の通常・例外が各チェック時点までに揃うことを刺激だけから確認した。各条件の40場面の学習予測と試験を記録し、通常・例外、答え方の型、確信、メモの区別の記載・矛盾・非明示を、回答を見せないメモ判定と対応づけて出す。','',
             '| 世界 | 条件 | 予測 | 更新 | 計 | 推論100/件の費用 | 推論2000/件の費用 |','|---:|---|---:|---:|---:|---:|---:|']
    for r in d['memo']:
        lines.append(f"| {r['world']} | {r['condition']} | {r['prediction_calls']} | {r['update_calls']} | {r['calls']} | ${r['reasoning_100_per_call_dollars']:.3f} | ${r['reasoning_2000_per_call_dollars']:.3f} |")
    low = sum(r['reasoning_100_per_call_dollars'] for r in d['memo'])
    high = sum(r['reasoning_2000_per_call_dollars'] for r in d['memo'])
    worst = sum(r['output_limit_32000_per_call_dollars'] for r in d['memo'])
    lines += ['', f'一組・二世界は計608要求。学習予測240、更新160、通常の試験144、書き戻し・対照64。費用は上の二仮定で${low:.3f}／${high:.3f}、25%の予備を含めると${low*1.25:.3f}／${high*1.25:.3f}。三組なら要求1824・この一組の見積もりの約3倍。全要求が32000出力トークンを使う場合の設計上の計算値は約${worst:.2f}（入力は上記の推定、再試行なし）。正式な予算は実測した入力と要求ごとの出力上限で確保し、別途固定する。','',
              '### (2) 関係の無い行の数を0・今のまま・増やす版','',
              'この案では「追加行」を、ドアを含む階層とシールの接続を参照しない、親の無いroleの一行と定義する。現行では甲に`roti(oN)`、乙に`reso(oN)`の一行がある。0行はこれだけを取り除き、今のままは残し、増やすはさらに16行を足して計17行とする。問いの場面の総行数は16・17・33。ドアへ至る階層、甲乙を示すもう一方の枝、シールとその接続は全条件で保持し、ぶら下がる関係番号や新しい`?`を作らない。','',
              '増やす16行は主の場面の物・関係から切り離した物を引数とする一引数の行。新しい無意味語は元の語彙と重ならない四文字で、甲乙・通常例外・正解と独立に事前固定する。元の行の相対順・番号は維持し、追加行の番号と挿入位置は答えを見ずに専用の乱数で固定。全40場面の履歴と試験16問の両方へ同じ操作を行い、ドア割合0.5・元の指示・mediumで一項目ずつ比較する。番号・対象行・語の出現数の照合も保存する。','',
              '現行のroleの語は甲乙と対応するため、これは答えの手掛かりを全く持たない行だけの増減ではない。厳密に無関係な行の負荷だけを比較する追加設計なら、roleを全条件で残し、独立な新規行を0・16・32行にする。その場合「0行」は現行と同一になり、0と今のままは別条件にならない。この区別を走行前に固定する。','',
              '| 追加行 | 試験の場面の総行数 | 最後の16問：推論100/件 | 最後の16問：推論2000/件 | 学習40＋試験16：推論100/件 | 学習40＋試験16：推論2000/件 |','|---|---:|---:|---:|---:|---:|']
    for r in d['distractor_rows']:
        f,allr = r['final16_only'],r['training40_plus_final16']
        lines.append(f"| {r['condition']}（{r['independent_root_lines']}行） | {r['scene_lines']} | ${f['reasoning_100_per_call_dollars']:.3f} | ${f['reasoning_2000_per_call_dollars']:.3f} | ${allr['reasoning_100_per_call_dollars']:.3f} | ${allr['reasoning_2000_per_call_dollars']:.3f} |")
    rowlow = sum(r['final16_only']['reasoning_100_per_call_dollars'] for r in d['distractor_rows'])
    rowhigh = sum(r['final16_only']['reasoning_2000_per_call_dollars'] for r in d['distractor_rows'])
    lines += ['',f'保存済みの履歴を変換して最後の16問だけを出す設計なら3条件計48要求、${rowlow:.3f}／${rowhigh:.3f}、25%の予備を含め${rowlow*1.25:.3f}／${rowhigh*1.25:.3f}。学習中の答えも新規に記録する設計なら3条件計168要求で、表の右二列を合計する。現在の0.5の最後の16問は再利用できるが、時期差を含むので新規反復と同じ扱いにはしない。','',
              '### (3) 記号を意味のある言葉へ置き換える版','',
              '同じ40場面・同じ16問の構造、順番、伏せ方、r/o番号を維持し、述語だけを一対一で固定置換する。例：`govern→store`、`attach→has_sticker`、`sig_n→round_sticker`、`sig_e→square_sticker`、`hold→red_door`、`hold_b→blue_door`。他の述語は`push`・`carry`・`cause`など元の意味を持つ英語へ置き換える。通常・例外を示す名称や「逆になる」という規則の説明は足さない。二つのドアとシールの名前は組ごとに事前に入れ替えて名称との対応を固定する。','',
              '置換は場面、学習の正解、返す答えの語すべてに同じ辞書で適用する。JSON schema・指示・adaptive・medium・summarizedは維持する。意味語は四文字の無意味語とトークン長が異なるため、正式走行前に両条件の入力トークンを数えて並記する。この操作は意味とトークン長を同時に変えるので、意味だけの操作とは記載しない。','',
              '| 実行範囲 | 要求 | 推論100/件の費用 | 推論2000/件の費用 |','|---|---:|---:|---:|']
    m = d['meaning_words']
    for key,label in [('final16_only','履歴を置換し、最後の16問だけ'),('training40_plus_final16','学習40＋最後の16問')]:
        r = m[key]
        lines.append(f"| {label} | {r['calls']} | ${r['reasoning_100_per_call_dollars']:.3f} | ${r['reasoning_2000_per_call_dollars']:.3f} |")
    f = m['final16_only']
    lines += ['',f"意味語の最後の16問だけは25%の予備込みで${f['reasoning_100_per_call_dollars']*1.25:.3f}／${f['reasoning_2000_per_call_dollars']*1.25:.3f}。無意味語の同時対照16問も新規に出す場合は計32要求で、その条件の費用を別に足す。辞書の全文、費用の仮定、較正値と計算結果は`design_estimates.json`に保存した。三案の費用は今回支出した費用には含めない。",'']
    return lines

if __name__ == '__main__':
    main()
