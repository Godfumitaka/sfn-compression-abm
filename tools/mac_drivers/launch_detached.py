"""台本を端末から切り離して走らせる（新しいセッション・新しいプロセスグループ。標準入出力は /dev/null とログ）。
使い方  python3.12 tools/mac_drivers/launch_detached.py <ログ> <台本> [引数...]   （環境変数はそのまま渡る）"""
import os
import sys

log, cmd = sys.argv[1], sys.argv[2:]
if os.fork() > 0:
    sys.exit(0)
os.setsid()
if os.fork() > 0:
    os._exit(0)
fd_in = os.open(os.devnull, os.O_RDONLY)
fd_out = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
os.dup2(fd_in, 0); os.dup2(fd_out, 1); os.dup2(fd_out, 2)
os.execvp("bash", ["bash", *cmd])
