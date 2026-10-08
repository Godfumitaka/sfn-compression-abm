"""第 1 波の種 1・2 の 28 本を、クラウドの機械の上で始める（受け箱の指示 33 の 1）。命令は注意の係の書き出し（portable_argv）の三つの場所だけを割り当てたもの。
各本：cwd は版の作業場所（~/sfn/audit/_read/<attnprep|attnprune>）、PYTHONHASHSEED=0、LANG・LC_* を外す、setsid、/usr/bin/time -v。既にある出力の本は飛ばす。
始める前に、命令の --v39-price と --e-price、版の作業場所の HEAD、設定の sha256 を確かめる。"""
import hashlib, json, os, shlex, subprocess, sys, time
H=os.path.expanduser("~"); cmds=json.load(open(sys.argv[1]))
for c in cmds:
    a=c["argv"]; src=f"{H}/sfn/audit/_read/{c['wt']}"
    assert subprocess.check_output(["git","-C",src,"rev-parse","HEAD"],text=True).strip()==c["commit"]
    assert not subprocess.check_output(["git","-C",src,"status","--porcelain"])
    assert a[a.index("--v39-price")+1]=="0.00035129738499384776" and a[a.index("--e-price")+1]=="0.01873710622997919"
    assert hashlib.sha256(open(a[2],"rb").read()).hexdigest()==c["config_sha"]
    D=c["rundir"]
    if os.path.exists(a[3]): print("既にある出力なので飛ばす", c["name"]); continue
    os.makedirs(D,exist_ok=True); json.dump(a,open(f"{D}/native_command.json","w"),ensure_ascii=False,indent=1)
    open(f"{D}/run.sh","w").write(f"cd {shlex.quote(src)} && env -u LC_ALL -u LANG -u LC_CTYPE PYTHONHASHSEED=0 /usr/bin/time -v {shlex.join(a)} > {D}/run.log 2> {D}/time.log; echo rc=$? >> {D}/run.log\n")
    subprocess.Popen(["setsid","bash",f"{D}/run.sh"],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,env={**os.environ,"PATH":f"{H}/.local/bin:"+os.environ["PATH"]})
    print(time.strftime("%F %T"),"始めた",c["name"],c["wt"]); time.sleep(2)
