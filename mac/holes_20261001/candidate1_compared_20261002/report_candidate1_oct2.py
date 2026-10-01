"""届いた種1の台帳の比較を報告する。模型は動かさない。"""
from datetime import datetime
from zoneinfo import ZoneInfo
import gzip
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT.parent/'codex_worldv4_2026-10-01/results'
DEST = RESULTS/'mac/holes_20261001/candidate1_compared_20261002'
REPORT = RESULTS/'control/2026-10-01_穴出しと集団化_Codex.md'
MARKER = '### 候補1：台帳到着後の比較（2026-10-02）'
assert not DEST.exists() and MARKER not in REPORT.read_text()
DEST.mkdir()
names = ('candidate1_compare_20261002.json', 'candidate1_primitive_case_20261002.json', 'candidate1_exact_power_20261002.json')
comparison, case, exact = [json.loads((ROOT/'analysis'/n).read_text()) for n in names]
assert comparison['first_difference']['index_zero_based'] == 179
assert comparison['counts'].get('different_outcome', 0) == 0
assert exact['reference_matches_desktop_recorded_values']
for n in names:
    p = ROOT/'analysis'/n
    if n == names[0]:
        (DEST/(n+'.gz')).write_bytes(gzip.compress(p.read_bytes(), mtime=0))
    else:
        shutil.copyfile(p, DEST/n)
shutil.copyfile(Path(__file__), DEST/'report_candidate1_oct2.py')
flags = {}
for name, p in [('mac', RESULTS/'mac/holes_20261001/candidate1_mac/flag.json'),
                ('desktop', RESULTS/'ataru-0608/穴出し/candidate1/flag.json')]:
    flags[name] = json.loads(p.read_text())
(DEST/'flags.json').write_text(json.dumps(flags,ensure_ascii=False,indent=1)+'\n')
lines = [
    '\n'+MARKER+'\n',
    f'保存時刻：{datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds")}。一対一の走行の合間に、到着した既存の台帳を読んで比較。新しい世界の走行はなし。',
    '',
    '候補1の区分：機械間の台帳本文の一致には穴あり（一字一句の一致が成立しない）。最初の数値差と、その数値を更新するコードの経路を特定。OSの数学の部品の単体比較は未実施。',
    '比較は、お店の世界2・A・f=0.5・忘却と学習の値段L50・種1・1740試行。マックのコードbc5cd13、デスクトップ88e0e38（模型の部分は同じ。世界1の台本の追加が差）。Pythonは双方3.12.13。マックarm64、デスクトップWSL2 Ubuntu24.04.5・x86_64・glibc2.39。元の旗はflags.jsonへ保存。',
    '',
    '| 項目 | 件数 / 全1740試行 |', '|---|---:|',
    f"| 本文の行の相違 | {comparison['counts']['different_bytes']} / 1740 |",
    f"| JSONとして読んだ内容の相違 | {comparison['counts']['different_json']} / 1740 |",
    f"| 状態の指紋の相違 | {comparison['counts']['different_state_hash']} / 1740 |",
    '| 予測した関係・使った定義・正誤・棄権の相違 | 0 / 1740 |',
    '| 削除の記録の数値の相違 | 2 / 1740 |',
    '',
    '正解1197・誤答10・棄権533は両側で全試行一致。異なる本文の欄は state_snapshot・agent_state_snapshot_hash・deletion_event・reg_del_events の四つだけ。',
    f"マックの本文の指紋：{comparison['left_body_sha']}。デスクトップ：{comparison['right_body_sha']}。",
    '',
    '浮動小数：数を二進で有限の桁数に丸めて保持する計算用の表現。以下の二つの値は、その表現の最小の刻み一つ分が異なる。',
    '最初の相違は試行番号179（180番目）。試行0〜178は本文が全て一致。定義R_0e5d236bf5b42b15の席2の、誕生時の評価を古くした二つの値が異なった。字の並べ方だけの相違ではなく、数として読んでも異なる。',
    '',
    '| 値 | マック | デスクトップ | 絶対差 |', '|---|---|---|---|',
    '| 初期の誤答費用の成分 | 1.1055565720257508e-08 | 1.105556572025751e-08 | 1.6543612251060553e-24 |',
    '| 初期の経験量の成分 | 1.8425942867095845e-09 | 1.8425942867095847e-09 | 2.0679515313825692e-25 |',
    '',
    '更新の経路：tools/v310be.py:145 の役割による採点 → tools/v39.py:228 の rec_add → 同:191〜195 の rec_values。席の前の時刻は78、今回179、差は101。_pow（同:184〜187）が作る古さの重み f**101 を、前の初期評価の値へ掛ける。',
    '小さな計算：f=0.8792940218288807（その二進表現は0x1.c232d376a58e8p-1）。マックの f**101 と math.pow(f,101) はともに2.2779603883522144e-06。',
    '同じ二進表現の数の101乗を整数の分数として計算し、最後に浮動小数へ丸めると2.277960388352215e-06。7000桁の十進計算でも同じ丸め結果だった。重みの表現は、マック0x1.31be1f7a12ea9p-19、その参考値0x1.31be1f7a12eaap-19。',
    '前の値0.0008088789849600693と0.004853273909760416にマックの重みを掛けると、マックの最初の二値と完全一致。隣の参考値を掛けると、デスクトップの最初の二値と完全一致。この計算は診断だけで、模型の重みや式を置き換えていない。',
    'デスクトップで実際に計算された f と f**101 は台帳に無い。上の参考値をデスクトップでのべき乗の実測値とはしていない。どのOSの数学の部品で差が出たかは、下記の単体値の確認を待つ。',
    '',
    'その他の数値差：試行1055（1056番目）の削除の記録で費用0.5625985714945886 / 0.5625985714945887と点数0.00218061461819608 / 0.0021806146181960803。試行1296（1297番目）で経験量0.06236399612512853 / 0.06236399612512854。削除した対象・変換の種類・試行は同じだった。',
    'この一本で、答え・選ばれた定義・正誤・棄権の入れ替わりは0。別の種や値段での頻度・成績への差は未計測。',
    '',
    '保存先：mac/holes_20261001/candidate1_compared_20261002/。最初の台帳の全行・全1740行の相違の件数・数値の小例・元の旗を保存。元の台帳は両機械の保存先と自分の作業場所に保持。',
    '',
    '#### デスクトップへの単体値の確認依頼（世界の走行をしない）',
    '',
    '同じPython3.12.13、コード88e0e38の作業場所で、次の出力だけをcontrol/へ追記してほしい。現在の走行を止める必要はない。',
    '',
    '```python',
    'from abm.accounting import decay_ladder',
    'import math',
    'f = decay_ladder(1740)[5]',
    'x = float.fromhex("0x1.c232d376a58e8p-1")',
    'print("decay", f.hex())',
    'print("power", (x**101).hex(), math.pow(x, 101).hex())',
    '```',
    '',
    'マックの出力：decay 0x1.c232d376a58e8p-1、power 0x1.31be1f7a12ea9p-19 0x1.31be1f7a12ea9p-19。',
]
with REPORT.open('a') as f:
    f.write('\n'.join(lines)+'\n')
manifest=[{'path':str(p.relative_to(DEST)),'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
          for p in sorted(DEST.iterdir()) if p.is_file()]
(DEST/'files.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=1)+'\n')
print(json.dumps({'compared_trials':1740,'first_trial_zero_based':179,'outcome_differences':0,'saved':str(DEST)},ensure_ascii=False))
