#!/bin/bash
# 指示 63 の 2：AWS の走っている本の試行を 30 分ごとに記録する（読むだけ）。最近の一試行の時間を、二つの時刻の差から出すため。
# ~/cloud/wave1/aws_trials.tsv に「時刻・機械・本の出力先・試行」を足す。
source $HOME/cloud/aws_env.sh; W=$HOME/cloud/wave1; OUT=$W/aws_trials.tsv
while true; do
  for m in ../wave1_machine machine_m1 machine_m2 machine_m3 machine_m4; do
    read MID MIP < $W/$m
    ssh -n -i $KEY_FILE -o ConnectTimeout=15 ubuntu@$MIP 'python3 - <<"PY"
import os, glob, re, time
for p in os.listdir("/proc"):
    if not p.isdigit(): continue
    try: a=open(f"/proc/{p}/cmdline","rb").read().split(b"\0")
    except Exception: continue
    if len(a)>3 and a[0]==b"python3.12" and a[1]==b"tools/v3_run.py":
        out=a[3].decode(); f=glob.glob(out+"/side/*/seed*.jsonl"); t=""
        if f:
            with open(f[0],"rb") as fh:
                fh.seek(0,2); n=fh.tell(); fh.seek(max(0,n-300000))
                for l in reversed(fh.read().split(b"\n")):
                    m=re.search(rb"\"trial\": (\d+)",l)
                    if m: t=m[1].decode(); break
        print(f"{int(time.time())}\t{out}\t{t}")
PY' 2>/dev/null | sed "s#^#$MID\t#" >> $OUT
  done
  sleep 1800
done
