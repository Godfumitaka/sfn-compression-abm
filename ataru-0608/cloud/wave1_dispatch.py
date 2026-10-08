"""第 1 波の行を、クラウドの機械に配る段取り（受け箱の指示 27 の 4。まだ走らせない）。
使い方：
  wave1_dispatch.py plan <行の JSON（build_commands.py が作る）> <機械の種類> [一台の本数]
      → 種 1・2 を先にした順で、機械ごとの本の割り当て（<行>_plan.json）と、台数・費用の見込みを出す。立てない。
  wave1_dispatch.py launch <_plan.json>
      → 機械を立て、版（行の commit）を送って setup し、各機械に割り当ての本を送って remote_launch.sh で始める。
決まり：
  - 機械の種類：c7a.8xlarge（一本 2GB 以下の行、一台 28 本まで＝メモリ 64GiB で空き 4GiB を残す）、m7a.8xlarge（一本のメモリが大きい行、128GiB、一台 30 本まで）。
  - 種 1・2 を先に（D-07τ）。各本は一本 1 芯、setsid、time -v、PYTHONHASHSEED=0、LANG・LC_* を外す（remote_launch.sh）。
  - 出力は機械の上の ~/cloud_runs/wave1/<行>/<arm>/seedNNN。終わった本は aws_fetch_run.sh で D:・S3・GitHub に運ぶ（見張りは cloud_watch と同じ形）。
  - 走行の列の「走行中」「済み」は、デスクトップの queue_row.py で書く（クラウドに GitHub の鍵は置かない）。
  - 費用の見込み：台数 × 時間単価（prices_us_east_1.json）× 時間。予算の知らせ（100 ドル）に近づいたら、止めずに Claude に知らせる。"""
import json, math, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
PER = {"c7a.8xlarge": 28, "m7a.8xlarge": 30, "r7a.8xlarge": 30}
PRICE = json.load(open(os.path.join(HERE, "prices_us_east_1.json")))

def plan(rowjson, typ, per=None):
    r = json.load(open(rowjson)); runs = r["plan"]; per = int(per or PER[typ])
    runs = sorted(runs, key=lambda x: (0 if x["seed"] in (1, 2) else 1, x["seed"], x["arm"]))   # 種 1・2 を先に
    n = math.ceil(len(runs) / per)
    chunks = [runs[i * per:(i + 1) * per] for i in range(n)]
    out = dict(row=r["row"], commit=r["commit"], what=r["what"], type=typ, per_machine=per, machines=[dict(runs=c) for c in chunks])
    p = rowjson.replace(".json", "") + "_plan.json"; json.dump(out, open(p, "w"), ensure_ascii=False, indent=1)
    print(f"行 #{r['row']}：{len(runs)} 本、{typ} を {n} 台（一台 {per} 本まで）、時間単価の見込み {PRICE.get(typ, '?')}×{n} 台 → {p}")
    return p

def launch(planjson):
    p = json.load(open(planjson)); typ = p["type"]; commit = p["commit"]
    # 版：GitHub から commit を取り、一時の参照を作って束にする（aws_ship.sh は refs/remotes/origin/<枝> を束にする）
    repo = os.path.expanduser("~/sfn/sfn-compression-abm"); ref = f"wave1/{commit[:7]}"
    subprocess.run(["git", "-C", repo, "fetch", "-q", "origin", f"{commit}:refs/remotes/origin/{ref}"], check=True)
    for i, m in enumerate(p["machines"]):
        out = subprocess.run(["bash", os.path.join(HERE, "aws_launch.sh"), typ, "120"], capture_output=True, text=True).stdout.strip().splitlines()[-1]
        mid, ip = out.split()
        m.update(id=mid, ip=ip); json.dump(p, open(planjson, "w"), ensure_ascii=False, indent=1)
        subprocess.run(["bash", "-c", f"for i in $(seq 1 30); do ssh -i ~/.ssh/sfn-runner.pem -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 ubuntu@{ip} true && break; sleep 10; done"], check=False)
        subprocess.run(["bash", os.path.join(HERE, "aws_ship.sh"), ip, ref, commit, f"wave1_{commit[:7]}"], check=True)
        cmds = os.path.join(HERE, f"wave1_row{p['row']}_m{i}.json"); json.dump(m["runs"], open(cmds, "w"), ensure_ascii=False, indent=1)
        subprocess.run(["scp", "-q", "-i", os.path.expanduser("~/.ssh/sfn-runner.pem"), cmds, os.path.join(HERE, "remote_launch.sh"), f"ubuntu@{ip}:~/cloud/"], check=True)
        subprocess.run(["ssh", "-i", os.path.expanduser("~/.ssh/sfn-runner.pem"), f"ubuntu@{ip}",
                        f"setsid nohup bash ~/cloud/remote_launch.sh ~/cloud/{os.path.basename(cmds)} wave1_{commit[:7]} {p['row']} > ~/cloud/remote_launch.log 2>&1 < /dev/null &"], check=True)
        print(f"機械 {i}：{mid}（{ip}）に {len(m['runs'])} 本を配った")

if __name__ == "__main__":
    {"plan": lambda: plan(*sys.argv[2:]), "launch": lambda: launch(sys.argv[2])}[sys.argv[1]]()
