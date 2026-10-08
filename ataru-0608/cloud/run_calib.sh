#!/bin/bash
# 較正の一本を走らせる（デスクトップの較正と同じ旗、準備版 e9ed84a）。引数：世界 種 [出力の根（既定 ~/cloud_runs/calib）] [試行（既定 1740）]
# 一本ずつ setsid で切り離し、/usr/bin/time -v で実時間と最大常駐を残す。PYTHONHASHSEED=0、LC_ALL・LANG・LC_CTYPE を外す。
set -euo pipefail
W=$1; S=$2; ROOT=${3:-$HOME/cloud_runs/calib}; TRIALS=${4:-1740}
HERE=$(cd "$(dirname "$0")" && pwd); SRC=$HOME/sfn/audit/_read/${WT:-attnprep}   # 高速化の版は WT と EXTRA_FLAGS（足す旗、空白区切り）を替える
D=$ROOT/w${W}_seed$(printf %03d $S); [ -e $D/output ] && { echo "★ もう出力がある：$D/output（上書きしない）"; exit 2; }
mkdir -p $D
python3 - "$HERE/calib_template.json" "$D" "$W" "$S" "$TRIALS" <<'PY'
import json, sys
t = json.load(open(sys.argv[1])); D, W, S, T = sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
cfg = t["config_template"]; cfg["seeds"]["start"] = S; cfg["output"]["dir"] = D + "/unused_config_output_dir"
json.dump(cfg, open(f"{D}/config.json", "w"), ensure_ascii=False, indent=1)
f = list(t["flags"]); f[f.index("--shop-world") + 1] = W; f[f.index("--seeds") + 1] = str(S); f[f.index("--trial-count") + 1] = T
import os, shlex
f += shlex.split(os.environ.get("EXTRA_FLAGS", ""))
json.dump(["python3.12", "tools/v3_run.py", f"{D}/config.json", f"{D}/output", *f], open(f"{D}/native_command.json", "w"), ensure_ascii=False, indent=1)
PY
CMD=$(python3 -c "import json,shlex;print(shlex.join(json.load(open('$D/native_command.json'))))")
cat > $D/run.sh <<EOS
#!/bin/bash
cd $SRC && env -u LC_ALL -u LANG -u LC_CTYPE PYTHONHASHSEED=0 /usr/bin/time -v $CMD > $D/run.log 2> $D/time.log; echo rc=\$? >> $D/run.log
EOS
setsid nohup bash $D/run.sh < /dev/null > /dev/null 2>&1 &
echo "始めた：世界 $W・種 $S・試行 $TRIALS → $D"
