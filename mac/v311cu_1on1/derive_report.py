"""午後の一対一走行の記録を読むだけの集計。元の台帳を消さず結果を保存する。"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

# 結果側へ写した台本を使う場合は、専用作業ルートを第1引数に渡す。
ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
SOURCE = ROOT / "source"
OUT = ROOT / "outputs"
RESULTS = ROOT.parents[1] / "codex_v310ans_2026-09-30/results"
TARGET = RESULTS / "mac/v311cu_1on1"
CONTROL = RESULTS / "control"
sys.path.insert(0, str(SOURCE / "tools"))
import v311c_report as original

CONDITIONS = {arm+"_"+c: f"λ={price}・{label}" for arm,price in [("L50","L50"),("lam020","0.2")] for c,label in [("recvA","受信A"),("recvB","受信B"),("no_comm","通信なし")]}
NAME_ROWS = []
WRONG_ROWS = []


def write_new(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"既存の結果がある：{path}")
    path.write_text(content, encoding="utf-8")


def I(n):
    return 2 * (n + 1).bit_length() - 1


def lengths(bundles):
    out = Counter(束=len(bundles))
    for b in bundles:
        out["関係本数"] += b.get("n_rel", 0)
        out["ビット"] += b.get("bits", 0)
        out["参照先追加"] += b.get("added", 0)
        out["初期束除外"] += b.get("excluded", 0)
        out["予測除外"] += bool(b.get("pred_excluded"))
        out["場面本数"] += b.get("scene_n", 0)
        out["場面から保持"] += b.get("bundle_from_scene", 0)
        out["場面から除外"] += b.get("scene_n", 0) - b.get("bundle_from_scene", 0)
        out["場面になかった予測"] += b.get("bundle_not_in_scene", 0)
        assert b["final"] == b["initial"] - b["excluded"] + b["added"]
        assert b["final"] == b["n_rel"] == len(b["relations"])
        out["参照先追加のある束"] += b.get("added", 0) > 0
        out["初期束除外のある束"] += b.get("excluded", 0) > 0
    return dict(out)


def population(condition, run):
    root = OUT / condition
    cp = root / "comm" / f"run{run:03d}.jsonl"
    events = [json.loads(l) for l in cp.open()]
    summary = events[-1]
    assert summary["kind"] == "summary" and summary["trials"] == 1740 and not summary["errors"]
    # 大きい状態の差分を二度解かない。集計に使う欄だけを控える（元の台帳は変更しない）。
    cached_rows = {}
    real_reader = original.ledger_rows
    def collect_rows(path):
        rows = []
        for row in real_reader(path):
            minimal = {k: row.get(k) for k in ["prediction_order", "coverage", "hit", "predicted_edge", "R_used",
                       "instance_id", "world_hash", "held_out_content", "coin_t", "f_fired", "feedback_content"]}
            minimal["reg_del_events"] = [{k: e.get(k) for k in ["kind", "R", "trial", "was_extension"]}
                                          for e in row.get("reg_del_events") or []]
            rows.append(minimal)
            yield minimal
        cached_rows[str(path)] = rows
    original.ledger_rows = collect_rows
    try:
        p = original.one_population(str(root), str(cp))
    finally:
        original.ledger_rows = real_reader
    assert p["個体"] == 2 and p["試行"] == 1740 and p["失敗"] == 0
    s, chk = p["数"], p["突き合わせ"]
    assert s["課題"] == 3480 and s.get("誤答_?", 0) == 0
    assert chk["個体の課題の和"] == chk["誤答の出どころの和"] == 2
    assert chk["一致の四分類の和"] == p["probes"] == 17
    assert all(chk[k] == 1 for k in ["送信＝配達", "配達＝受け取りの記録", "束のある試行は実際に答えた試行",
                                   "一個体一試行に束は一つまで", "受け取りで束を送らない"])
    assert all(s.get("STATS_"+k, 0) == 0 for k in ["recv_score_changed", "recv_merit_changed", "dC_mismatch"])
    births = [defaultdict(list), defaultdict(list)]
    removed = [defaultdict(list), defaultdict(list)]
    used = [[], []]
    world_inputs = []
    tag_summaries = []
    defs_removed = 0
    for i, agent in enumerate(summary["agents"]):
        seed = run + 1000*i
        assert agent["seed"] == seed and agent["v310be"]["cfg"]["score_role"]
        assert agent["v311c"]["cfg"]["b"] == 12
        assert agent["histrole"]["m1_calls"] > 0
        assert agent["relearninit"]["relearn_init_multi_obs"] == 0
        ledger = root / "ledgers/cells" / agent["cell"] / f"seed{seed:03d}.jsonl.gz"
        input_hash = hashlib.sha256()
        count = 0
        for row in cached_rows[str(ledger)]:
            count += 1
            t = row["prediction_order"]
            input_hash.update(json.dumps({k: row.get(k) for k in ["instance_id", "world_hash", "held_out_content", "coin_t", "f_fired", "feedback_content"]}, sort_keys=True).encode())
            for e in row.get("reg_del_events") or []:
                if e.get("kind") == "registration" and not e.get("was_extension"):
                    births[i][e["R"]].append(e["trial"])
                if e.get("kind") == "definition_removed":
                    removed[i][e["R"]].append(e["trial"])
                    defs_removed += 1
            if row.get("R_used") is not None:
                used[i].append((t, row["R_used"]))
        assert count == 1740
        world_inputs.append(input_hash.hexdigest())
        tables = agent["v311c"]["name_tables_end"]
        tags = set()
        entries = counts = cost = 0
        for R, d in sorted(tables.items()):
            assert d["tags"]
            cost += I(len(d["tags"])) + sum(12 + I(n) for n in d["tags"].values())
            for tag, n in sorted(d["tags"].items()):
                assert n >= 1
                NAME_ROWS.append({"condition": condition, "run": run, "agent": i, "world_seed": seed,
                                  "definition": R, "born": d["born"], "tag": tag, "count": n})
                tags.add(tag)
                entries += 1
                counts += n
        tag_summaries.append({"agent": i, "seed": seed, "definitions": len(tables), "entries": entries,
                              "distinct_tags": len(tags), "counts": counts, "bits": cost})
    bundles = [e for e in events if e["kind"] == "bundle"]
    nonempty = [b for b in bundles if not b.get("empty")]
    sent = [b for b in nonempty if b.get("send")]
    recvs = [e for e in events if e["kind"] == "recv"]
    learned = [r for r in recvs if r["result"] in ("同化", "誕生")]
    for r in learned:
        if r["result"] == "誕生":
            births[r["agent"]][r["R"]].append(r["R_born"])
    for bb in births:
        for dates in bb.values():
            dates.sort()
    # 受信は世界回答の後なので、同じ試行の受信をその回答の由来に数えない。
    received_first = {}
    for r in learned:
        key = (r['agent'], r['R'], r['R_born'])
        received_first[key] = min(received_first.get(key, r['t']), r['t'])
    wrong_counts = Counter()
    wrong_rows = []
    for i, agent in enumerate(summary['agents']):
        seed = run + 1000*i
        ledger = root / 'ledgers/cells' / agent['cell'] / f'seed{seed:03d}.jsonl.gz'
        side = original.side_v39(str(root / 'side' / agent['cell'] / f'seed{seed:03d}.jsonl'))
        for row in cached_rows[str(ledger)]:
            if row.get('coverage') != 1 or row.get('hit') == 1:
                continue
            t, R = row['prediction_order'], row['R_used']
            dates = [b for b in births[i][R] if b < t]
            assert dates, (condition, run, i, t, R, births[i][R])
            born = max(dates)
            first = received_first.get((i, R, born))
            provenance = 'received' if first is not None and first < t else 'other'
            rid = (row.get('predicted_edge') or {}).get('relation_id') or ''
            if rid.startswith('sme_projection__'):
                source = 'F'
            else:
                source = dict((x[0], x[1]) for x in side.get(t, {}).get('fill', [])).get(rid)
            assert source in ('F', 'H', 'U'), (condition, run, i, t, rid, source)
            wrong_counts[source+'_'+provenance] += 1
            wrong_rows.append(dict(condition=condition, run=run, agent=i, world_seed=seed,
                                   trial=t, definition=R, born=born, source=source,
                                   provenance=provenance, first_received_trial=first,
                                   predicted_predicate=(row.get('predicted_edge') or {}).get('predicate'),
                                   predicted_arguments=json.dumps((row.get('predicted_edge') or {}).get('arguments'),ensure_ascii=False)))
    assert sum(wrong_counts.values()) == s.get('誤答', 0)
    for source in ['F', 'H', 'U']:
        assert wrong_counts[source+'_received'] + wrong_counts[source+'_other'] == s.get('誤答_'+source, 0)
    def identity(i, R, t):
        dates = [b for b in births[i][R] if b <= t]
        return max(dates) if dates else None
    future_sent = [[], []]
    for b in sent:
        future_sent[b["agent"]].append((b["t"], b["R"], b["R_born"]))
    flow = Counter(world=s["課題"], opportunities=s["発話の機会"], bundles=len(nonempty), empty=len(bundles)-len(nonempty),
                   sent=len(sent), received=len(recvs), learned=len(learned))
    for r in learned:
        i, R, born, t = r["agent"], r["R"], r["R_born"], r["t"]
        eligible = t < 1739
        alive_next = eligible and identity(i, R, t+1) == born and not any(t < g <= t+1 for g in removed[i][R])
        end = summary["agents"][i]["v311c"]["name_tables_end"].get(R)
        alive_end = end is not None and end["born"] == born
        later_use = any(tt > t and rr == R and identity(i, rr, tt) == born for tt, rr in used[i])
        retold = any(tt > t and rr == R and bb == born for tt, rr, bb in future_sent[i])
        flow["next_eligible"] += eligible
        flow["alive_next"] += alive_next
        flow["alive_end"] += alive_end
        flow["used_later"] += later_use
        flow["retold"] += retold
        flow["alive_end_used_later"] += alive_end and later_use
        flow["alive_end_retold"] += alive_end and retold
    flow["definition_removed"] = defs_removed
    flow["label_extinct"] = s.get("集団から消えた名札", 0)
    assert flow["alive_end"] == s.get("取り込んだ定義が走行の終わりに残る", 0)
    assert flow["used_later"] == s.get("そのあと世界で使われた", 0)
    assert flow["retold"] == s.get("そのあとまた語られた", 0)
    p.update(condition=condition, run=run, flow=dict(flow), lengths_all=lengths(nonempty), lengths_sent=lengths(sent),
             names=tag_summaries, world_input_sha256=world_inputs,
             wrong_provenance=dict(wrong_counts), wrong_rows=wrong_rows)
    return p


def table(lines, headers, rows):
    lines += ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"]*len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    lines.append("")


def cached_population(condition, run):
    cache = OUT / "report_cache" / f"{condition}_{run}.json"
    if cache.exists():
        p = json.loads(cache.read_text())
        NAME_ROWS.extend(p["name_rows"])
    else:
        start = len(NAME_ROWS)
        p = population(condition, run)
        p["name_rows"] = NAME_ROWS[start:]
        write_new(cache, json.dumps(p,ensure_ascii=False,indent=2)+"\n")
    WRONG_ROWS.extend(p['wrong_rows'])
    print(f"集計確認：{condition} 種{run}",flush=True)
    return p


def sum_counts(rows, key):
    c = Counter()
    for p in rows:
        c.update(p[key])
    return c


def report(pops):
    commit = subprocess.check_output(["git", "rev-parse", "v3.11cu-main^{commit}"], cwd=SOURCE, text=True).strip()
    lines = ["# 集団化・一対一の動作確認（2026-09-30、Codex）", "",
             f"コードは v3.11cu-main（{commit}）、ブランチ codex-collective-urta。基準 v3.10urta-main（74b60da）へ v3.11ch-main（eeb524c）の集団化を載せ直した。", "",
             "仕様：sfn_collective_spec_2026-09-29_v2.md。受信Aは名札を使わず比較相手を選ぶ。受信Bは同じ名札の過去の束を優先し、なければAへ戻る。", "",
             "λは記憶1ビットの値段。ビットは情報の量を数える単位。同化は既存の定義へ束を取り込む処理、誕生は新しい定義を作る処理。", "",
             "2体、どちらも開示確率f=0.5、互いが通信相手。受信A/Bは発話時の送信確率q=0.2、通信なしはq=0。λ=0.01873710622997919（L50）と0.2。名札の固定長は全条件12ビット。履歴・採点は --hist-role --score-role。--u-struct --relearn-init --tie-struct --amb-local を付けた。", "",
             "各条件の集団の種は1・2・3。各個体1,740世界試行、合計18集団・36個体走行・62,640世界課題。個体iの世界の種は元の実装どおり「集団の種＋1000×i」。二体目は1001・1002・1003。種21〜40と8体の走行は使用していない。", "",
             "回答の一致の試験は100試行ごと、各型5件で計20件。問題を作る種は900001・900002・900003。各集団17回、18集団で306回・6,120組問題。世界の課題数には加えていない。", "",
             "## 世界の成績", "",
             "Fは定義の固定名からの答え、Hはその席の履歴からの答え、Uは全体の既定値からの答え。受信自体は世界課題に加えていない。", ""]
    world_rows = []
    for p in pops:
        s = p["数"]
        world_rows.append([CONDITIONS[p["condition"]], p["run"], s["課題"], s.get("正解", 0), s.get("誤答", 0), s.get("棄権", 0), s.get("誤答_F", 0), s.get("誤答_H", 0), s.get("誤答_U", 0)])
    table(lines, ["条件", "集団の種", "全課題（分母）", "正解", "誤答", "棄権", "誤答F", "誤答H", "誤答U"], world_rows)
    totals = []
    for name in CONDITIONS:
        s = sum_counts([p for p in pops if p["condition"] == name], "数")
        totals.append([CONDITIONS[name], s["課題"], s["正解"], s["誤答"], s["棄権"], s["誤答_F"], s["誤答_H"], s["誤答_U"]])
    table(lines, ["条件・3集団の和", "全課題（分母）", "正解", "誤答", "棄権", "誤答F", "誤答H", "誤答U"], totals)
    lines += ["## 誤答と受信した定義", "",
              "受信由来は、受け取った束から生まれた定義、又はその束を同化した定義が、それより後の世界試行で答えた誤答。定義番号と誕生試行を一組にして数える。同じ世界試行の回答後の受信は、その回答の由来には含めない。名札の有無だけでは判定しない。", "",
              "その他は、上の受信をまだ受けていない定義による誤答。各行の六欄の和が誤答に一致。各誤答の試行・定義・誕生試行・最初の受信時刻は wrong_provenance.csv.gz に保存。", ""]
    keys = [source+'_'+origin for source in ['F','H','U'] for origin in ['received','other']]
    table(lines, ['条件', '種', '誤答（分母）', 'F受信由来', 'Fその他', 'H受信由来', 'Hその他', 'U受信由来', 'Uその他'],
          [[CONDITIONS[p['condition']], p['run'], p['数'].get('誤答',0), *[p['wrong_provenance'].get(k,0) for k in keys]] for p in pops])
    table(lines, ['条件・3集団の和', '誤答（分母）', 'F受信由来', 'Fその他', 'H受信由来', 'Hその他', 'U受信由来', 'Uその他'],
          [[CONDITIONS[name], sum(p['数'].get('誤答',0) for p in pops if p['condition']==name),
            *[sum_counts([p for p in pops if p['condition']==name], 'wrong_provenance').get(k,0) for k in keys]] for name in CONDITIONS])
    lines += ["## 伝わる過程", "",
              "件数は受信一件を単位に数える。同じ定義への複数の取り込みも受信ごとに数える。定義の番号と誕生試行を一組にして、消えた後の同名の定義を区別する。発話の機会は台帳で実際に答えた世界課題。", "",
              "R_usedは、その世界試行で使う定義の番号を記録した欄。世界での使用は、元の集計と同じく後の世界試行にその定義がR_usedとして記録された受信件数。再伝達は後の試行にその定義から実際に送信された束がある受信件数。最終試行の受信には次の試行がないため、次試行の残存の分母から除く。", ""]
    flow_specs = [("発話の機会", "opportunities", "world"), ("空でない束", "bundles", "opportunities"),
                  ("参照を整えると空の束", "empty", "opportunities"),
                  ("送信", "sent", "bundles"), ("受信", "received", "sent"), ("取り込み（同化＋誕生）", "learned", "received"),
                  ("次の世界試行の終わりに残る", "alive_next", "next_eligible"), ("走行の終わりに残る", "alive_end", "learned"),
                  ("その後に世界で使われる", "used_later", "learned"), ("その後に再伝達される", "retold", "learned"),
                  ("終わりに残り、その後の世界使用もある", "alive_end_used_later", "alive_end"),
                  ("終わりに残り、その後の再伝達もある", "alive_end_retold", "alive_end")]
    for name in CONDITIONS:
        subset = [p for p in pops if p["condition"] == name]
        lines += [f"### {CONDITIONS[name]}", ""]
        cells = []
        for label, n, d in flow_specs:
            cells.append([label, *[f"{p['flow'].get(n,0)} / {p['flow'].get(d,0)}" for p in subset]])
        table(lines, ["段階（件数 / 分母）", "種1", "種2", "種3"], cells)
    table(lines, ["条件", "種", "同化", "誕生", "不成立", "記憶が空", "同名札候補あり", "Bを使用", "土台が報告"],
          [[CONDITIONS[p["condition"]], p["run"], p["数"].get("受け取り_同化",0), p["数"].get("受け取り_誕生",0),
            p["数"].get("受け取り_不成立",0), p["数"].get("受け取り_記憶が空（個体版の初めの扱い：登録しない）",0),
            p["数"].get("受信B_同じ名札の候補あり",0), p["数"].get("受信B_使った",0), p["数"].get("土台が報告の束",0)] for p in pops])
    lines += ["## 話の長さと場面との差", "",
              "ビットは名札を含む記述の長さ。場面と束の差は識別子の付け直しを除き、元の関係の対応で数える。参照先追加と初期束除外はそれぞれ一関係一回。送信表と全生成表を分ける。", ""]
    for key, title in [("lengths_sent", "実際に送信した束"), ("lengths_all", "生成した空でない束")]:
        lines += [f"### {title}", ""]
        data = []
        for p in pops:
            x = p[key]; n = x.get("束",0)
            data.append([CONDITIONS[p["condition"]], p["run"], n, x.get("関係本数",0),
                         f"{x.get('関係本数',0)/n:.4f}" if n else "—", f"{x.get('ビット',0):.6f}",
                         f"{x.get('ビット',0)/n:.6f}" if n else "—", x.get("参照先追加",0), x.get("初期束除外",0), x.get("予測除外",0)])
        table(lines, ["条件", "種", "束（平均の分母）", "関係本数の和", "平均本数", "ビットの和", "平均ビット", "追加した参照先", "外した初期関係", "予測自体の除外"], data)
    table(lines, ["条件", "種", "送信束", "送信前の場面本数", "束に残った場面関係", "場面から外れた関係", "場面に無い予測関係", "参照追加のある束", "初期除外のある束"],
          [[CONDITIONS[p["condition"]], p["run"], *[p["lengths_sent"].get(k,0) for k in ["束", "場面本数", "場面から保持", "場面から除外", "場面になかった予測", "参照先追加のある束", "初期束除外のある束"]]] for p in pops])
    lines += ["## 名札の回数表と消失", "",
              "名札は公開の名前。回数は今回の束を取り込んだときだけ増える。全件の最終回数表は [name_tables.csv.gz](../mac/v311cu_1on1/name_tables.csv.gz) に、条件・集団の種・個体・世界の種・定義番号・誕生試行・名札・回数を一行ずつ保存した。", "",
              "名札だけを忘れる処理は元の仕様どおり無い。席を薄くしても名札費用は減らず、定義全体の消失時に名札表も解放される。", ""]
    table(lines, ["条件", "種", "個体", "世界の種", "最終定義", "名札の項目", "異なる名札", "回数の和", "名札表のビット"],
          [[CONDITIONS[p["condition"]],p["run"],n["agent"],n["seed"],n["definitions"],n["entries"],n["distinct_tags"],n["counts"],n["bits"]] for p in pops for n in p["names"]])
    table(lines, ["条件", "種", "世界からの誕生", "報告からの誕生", "報告同化", "個体の定義消失", "集団の名札消失"],
          [[CONDITIONS[p["condition"]], p["run"], p["数"].get("STATS_birth_world",0), p["数"].get("STATS_birth_report",0),
            p["数"].get("STATS_assim_report",0), p["flow"].get("definition_removed",0), p["flow"].get("label_extinct",0)] for p in pops])
    lines += ["## 回答の一致と検査", ""]
    table(lines, ["条件", "種", "組問題（分母）", "双方正解", "同じ誤答", "双方棄権", "その他"],
          [[CONDITIONS[p["condition"]],p["run"],340,*[p["回答の一致"].get(k,0) for k in ["双方正解","同じ誤答","双方棄権","その他"]]] for p in pops])
    table(lines, ['条件・3集団の和', '組問題（分母）', '双方正解', '同じ誤答', '双方棄権', 'その他'],
          [[CONDITIONS[name], 1020, *[sum_counts([p for p in pops if p['condition']==name], '回答の一致').get(k,0)
                                   for k in ['双方正解','同じ誤答','双方棄権','その他']]] for name in CONDITIONS])
    lines += ["18集団すべてで、正解＋誤答＋棄権＝3,480、誤答F＋H＋U＝誤答、四分類の和＝340、送信＝配達＝受信を確認した。既存の席への通常受信採点、功績の変更、費用の見込みと実額の食い違いは各0件。", "",
              "誤答9,005件すべてで、台帳から復元した回答前の状態の定義番号・誕生試行が集計と一致。受信由来792件では受け取った名札がその状態に存在し、残る8,213件では回答前の取り込みが無いことを通信記録で確認。18集団・36個体の最終定義と名札回数表も状態と一致。", "",
              "条件間で、同じ個体の世界の番号・伏せた正解・開示の抽選・開示内容の記録の指紋が、両価格を合わせた12組すべて一致した。", "",
              "受入検査は [2026-09-30_集団化_urta_受入検査_Codex.md](2026-09-30_集団化_urta_受入検査_Codex.md)。U側との重複箇所は [2026-09-30_集団化_urta_重複箇所_Codex.md](2026-09-30_集団化_urta_重複箇所_Codex.md)。指定タグ後のU側の変更は取り込んでいない。", "",
              "台帳36本と通信・補助記録を mac/v311cu_1on1/ に保存。元の専用出力も全件保持。最終の空き容量は metadata.json に記録。集団の種を一つの独立走行単位として、種ごとの件数を示した。", ""]
    return "\n".join(lines)


def save_files():
    for condition in CONDITIONS:
        source = OUT / condition
        dest = TARGET / condition
        for p in sorted(source.rglob("*")):
            if not p.is_file():
                continue
            relative = p.relative_to(source)
            if relative.parts[0] == "side" or (relative.parts[0] == "comm" and p.suffix == ".jsonl"):
                q = dest / (str(relative) + ".gz")
                q.parent.mkdir(parents=True, exist_ok=True)
                if q.exists():
                    raise RuntimeError(f"既存の結果がある：{q}")
                with p.open("rb") as inp, q.open("wb") as raw, gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as out:
                    shutil.copyfileobj(inp, out)
            else:
                q = dest / relative
                q.parent.mkdir(parents=True, exist_ok=True)
                if q.exists():
                    raise RuntimeError(f"既存の結果がある：{q}")
                __import__("os").link(p,q)
    shutil.copy2(__file__, TARGET / "derive_report.py")
    audit = TARGET / "acceptance"
    audit.mkdir()
    for name in ["checks_hashes.json","checks_counts.json","pytest_results.json","pytest_results_v2.json","main_L50_driver.log","main_020_driver.log","executed_code_sha256.json"]:
        shutil.copy2(OUT / name, audit / name)
    for name in ["off_base","off_port","notags","short_ind","solo_notags","q0","solo_q0","repeat1","repeat2","noprobe","recvA_check"]:
        for p in sorted((OUT / name).rglob("*")):
            if not p.is_file():
                continue
            q = audit / name / p.relative_to(OUT / name)
            relative = p.relative_to(OUT / name)
            if relative.parts[0] == "side" or (relative.parts[0] == "comm" and p.suffix == ".jsonl"):
                q = Path(str(q)+'.gz')
            q.parent.mkdir(parents=True,exist_ok=True)
            if q.suffix == '.gz' and p.suffix != '.gz':
                with p.open('rb') as inp, q.open('xb') as raw, gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as gz:
                    shutil.copyfileobj(inp,gz)
            else:
                __import__("os").link(p,q)
        __import__('os').link(OUT/(name+'.log'), audit/(name+'.log'))
    for p in sorted(OUT.glob('pytest_*.log')):
        __import__('os').link(p, audit/p.name)
    shutil.copy2(ROOT/'verify_provenance_snapshots.py', TARGET/'verify_provenance_snapshots.py')
    shutil.copytree(OUT/'provenance_checks', TARGET/'provenance_checks')


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "cache":
        for name in CONDITIONS:
            for run in [1,2,3]:
                if (OUT / name / "comm" / f"run{run:03d}.summary.json").exists():
                    cached_population(name,run)
        sys.exit(0)
    pops = [cached_population(name, run) for name in CONDITIONS for run in [1,2,3]]
    assert sum(n["entries"] for p in pops for n in p["names"]) == len(NAME_ROWS)
    for arm in ["L50", "lam020"]:
        for run in [1,2,3]:
            pp = [p for p in pops if p["run"] == run and p["condition"].startswith(arm+"_")]
            assert pp[0]["world_input_sha256"] == pp[1]["world_input_sha256"] == pp[2]["world_input_sha256"]
    write_new(CONTROL / "2026-09-30_集団化_一対一_urta_Codex.md", report(pops))
    write_new(CONTROL / "2026-09-30_集団化_一対一_urta_Codex.json", json.dumps(pops,ensure_ascii=False,indent=2)+"\n")
    TARGET.mkdir(parents=True,exist_ok=True)
    with gzip.open(TARGET / "name_tables.csv.gz","xt",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=["condition","run","agent","world_seed","definition","born","tag","count"])
        writer.writeheader()
        writer.writerows(NAME_ROWS)
    assert len(WRONG_ROWS) == sum(p['数'].get('誤答',0) for p in pops)
    with gzip.open(TARGET / 'wrong_provenance.csv.gz','xt',encoding='utf-8',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=['condition','run','agent','world_seed','trial','definition','born','source','provenance',
                                            'first_received_trial','predicted_predicate','predicted_arguments'])
        writer.writeheader()
        writer.writerows(WRONG_ROWS)
    save_files()
    print(f"集計保存：18集団、36個体、名札表{len(NAME_ROWS)}行")
