"""開示だけで学べるか（2026-10-03 の依頼。記録を読むだけ、走行なし）。使い方：disclosure_only.py → 標準出力に markdown。
腕は「支持で見分けられるか」（separability.py）と同じ。材料は answers.csv（答えた試行ごと：trial・hit・disclosed・support_ratio）だけ。
手順（種ごと、試行の順に）：
  1 試行 t の答えについて、t より前の試行で、答えて、開示を受けた（disclosed＝1）ものだけを集める。
    支持の割合の区間ごとに外れの率（外れ ÷ 件数）を数える。
  2 試行 t の答えの「外れる確率」＝その区間の率。その区間にまだ開示が無ければ、それまでの開示全部の率。
    開示がまだ一つも無ければ 0（仮の決定。同じ値になるので、AUC では同点として扱われる）。
  3 全部の種の、全部の答えた試行で、「外れる確率」が実際の外れをどれだけ分けるか（AUC：外れの方が確率が高い確からしさ、同点は 0.5）。
区間（依頼の例で固定、結果を見て変えない）：1.0、0.9〜1.0 未満、0.8〜0.9 未満、…、0.1〜0.2 未満、0.1 未満（0.1 刻み）。
比べ：世界の中の全部の記録を使った AUC（separability.py の「支持の割合」の AUC。向きは同じ：外れを分ける力）。
使うのは本人の答えの記録だけで、世界の番号・未来の開示・研究者の側の量は使わない（正誤は、開示を受けた試行の分だけを推定に使う）。"""
import bisect
import csv
import glob
import os
import sys
from collections import defaultdict

H = os.path.expanduser("~")


# 腕の組と AUC は separability.py と同じ（写し）
def arms():
    out = []
    for wd in (2, 1):
        for r in ("A_L50", "A_L90", "C_L50", "C_L90", "D_t04"):
            n3 = (f"n3_w{wd}_{r}", f"{H}/n3prod/{f'n3_w{wd}_{r}'}", f"{H}/n3prod/tables/n3_w{wd}_{r}")
            if r == "D_t04":
                now = (f"uf_w{wd}_t0.4", f"{H}/ufprod/full/uf_w{wd}_t0.4", f"{H}/ufprod/full/tables/uf_w{wd}_t0.4")
            elif wd == 2:
                now = (f"fg_f050_{r}", f"{H}/fgrid/fg_f050_{r}", f"{H}/fgrid/tables/fg_f050_{r}")
            else:
                now = (f"now_w1_{r}", f"{H}/n3prod/now_w1_{r}", f"{H}/n3prod/tables/now_w1_{r}")
            out.append((wd, r, "N3", *n3))
            out.append((wd, r, "今の規則", *now))
    return out


def auc(pos, neg):
    if not pos or not neg:
        return None
    s = sorted(neg)
    tot = 0.0
    for x in pos:
        lo = bisect.bisect_left(s, x)
        hi = bisect.bisect_right(s, x)
        tot += lo + 0.5 * (hi - lo)
    return tot / (len(pos) * len(neg))




def bin_of(r):
    if r >= 1 - 1e-12:
        return 10
    return max(0, min(9, int((r + 1e-12) * 10)))


rows = []
for wd, rule, how, name, side, _tab in arms():
    pairs = []          # (外れる確率, 外れか)
    n_cold = n_fb = 0
    full_pos, full_neg = [], []
    for ap in sorted(glob.glob(f"{side}/side/*/seed*.answers.csv")):
        recs = []
        for a in csv.DictReader(open(ap, encoding="utf-8")):
            if a["support_ratio"] in ("", None):
                continue
            recs.append((int(a["trial"]), float(a["support_ratio"]), a["hit"] == "1", a["disclosed"] == "1"))
        recs.sort()
        cnt = defaultdict(lambda: [0, 0])     # 区間 → [件数, 外れ]
        tot = [0, 0]
        for t, r, hit, disc in recs:
            b = bin_of(r)
            if cnt[b][0]:
                p = cnt[b][1] / cnt[b][0]
            elif tot[0]:
                p = tot[1] / tot[0]
                n_fb += 1
            else:
                p = 0.0
                n_cold += 1
            pairs.append((p, not hit))
            (full_neg if hit else full_pos).append(r)
            if disc:                           # この試行の開示は、この試行の答えのあとに届く（次の試行から使う）
                cnt[b][0] += 1
                cnt[b][1] += int(not hit)
                tot[0] += 1
                tot[1] += int(not hit)
    wrong = [p for p, w in pairs if w]
    right = [p for p, w in pairs if not w]
    a_disc = auc(wrong, right)
    a_full = auc(full_neg, full_pos)           # 支持の割合が高い方を正解と見る（separability と同じ値）
    rows.append(f"| {wd} | {rule} | {how} | {name} | {len(right):,} | {len(wrong):,} | {'—' if a_disc is None else f'{a_disc:.3f}'} | "
                f"{'—' if a_full is None else f'{a_full:.3f}'} | {n_fb:,} | {n_cold:,} |")

print("| 世界 | 規則 | 選び方 | 走行 | 正解 | 外れ | AUC（開示だけ・その時点まで） | AUC（全部の記録：支持の割合） | 区間に開示が無く全体の率で代えた答え | 開示がまだ無かった答え |")
print("|---:|---|---|---|---:|---:|---:|---:|---:|---:|")
print("\n".join(rows))
