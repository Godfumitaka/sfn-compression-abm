# クラウド（AWS の Ubuntu）で走らせる台本（受け箱の指示 16 の B、まだ走らせない）

鍵や合い言葉はここに無い。GitHub の権限は、機械を作った人が設定する。模型は標準の部品だけで動く（pip の追加は要らない、デスクトップで確かめた）。

1. `bash setup.sh`：Python 3.12.13（uv で入れる）と準備版 e9ed84a を、デスクトップと同じ場所の形（~/sfn/audit/_read/attnprep）に置く。results の枝も取り出し、行を取る道具を置く。
2. `bash verify200.sh`：最初に、世界 1・種 41・試行 200 を走らせ、デスクトップの基準（ref200_desktop_wsl.tsv）と比べる。台帳の見出し一行と時間の欄を除いて、全部一致すること。一致しなければ第 1 波を始めない。
3. `bash run_calib.sh 世界 種 [出力の根] [試行]`：較正の一本。デスクトップの較正と同じ旗（calib_template.json）。setsid で切り離し、time -v を残す。
4. 第 1 波の行を取って走らせる：~/queue/ の queue_row.py（takeable・claim・done）、build_commands.py、launch_row.sh。デスクトップと同じ決まり（一本ずつ setsid、time -v、空き 4GiB、C: の決まりはクラウドではそのディスクの空きに読み替える）。
5. `bash push_small.sh <一本のフォルダ> <名前>`：出力はクラウドに置いたまま、ファイルごとの sha256 と大きさの一覧・比べ用の sha256（norm_hash.py）・命令・time.log・flag・manifest・.done だけを results の枝（ataru-0608/cloud_runs/）に上げる。
