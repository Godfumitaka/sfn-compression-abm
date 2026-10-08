# クラウド（AWS の Ubuntu Server 24.04）で走らせる台本（受け箱の指示 16 の B・指示 17。まだ走らせていない）

鍵や合い言葉はここに無い。aws configure はアストラが自分で行う。クラウドの機械には GitHub の鍵を置かない（版は git の束で送り、小さい記録はデスクトップが持ってきて GitHub に上げる）。模型は標準の部品だけで動く（pip の追加は要らない、デスクトップで確かめた）。

## 走らせ方
1. デスクトップで `bash aws_ship.sh <公開 IP>`：版を git の束で送り、機械の上で setup.sh（Python 3.12.13・準備版 e9ed84a・AWS CLI）を走らせる。
2. 機械の上で `bash verify200.sh`：最初に、世界 1・種 41・試行 200 を走らせ、デスクトップの基準（ref200_desktop_wsl.tsv）と比べる。台帳の見出し一行と時間の欄を除いて、全部一致すること。一致しなければ第 1 波を始めない。
3. 機械の上で `bash run_calib.sh 世界 種 [出力の根] [試行]`：較正の一本。デスクトップの較正と同じ旗（calib_template.json）。setsid で切り離し、time -v を残す。
4. 第 1 波の行：queue_row.py・build_commands.py・launch_row.sh・memroom_any.py・run_after_audit.py（デスクトップと同じ決まり。一本ずつ setsid、time -v、空き 4GiB）。行を取って状態を書くのはデスクトップ側（GitHub に書けるのはデスクトップだけ）。
5. 一本が終わるたびに、機械の上で `bash push_small.sh <本> <名前> <バケット>`：大きい出力は S3、小さい記録は <本>/small/。デスクトップで `bash aws_fetch_small.sh <公開 IP> <本> <名前>` で GitHub に上げる。

## AWS の操作（受け箱の指示 17。地域 us-east-1。鍵の値は書かない・上げない。aws configure はアストラが行う）
- aws_env.sh：地域、許される機械の種類（c7a.xlarge・c7a.16xlarge・m7a.16xlarge・r7a.16xlarge）、AMI（Canonical の Ubuntu Server 24.04 LTS、x86_64、SSM の公開の値から引く）、名前の決まり。バケットの名前は ~/cloud/BUCKET の一行。
- aws_prepare.sh：鍵が入った後に一度だけ。SSH の鍵の組（秘密鍵は ~/.ssh、上げない）と入口（デスクトップの公開 IP からの SSH だけ）を作る。
- aws_launch.sh <種類> [ディスク GB]：許された種類だけを立てる（札 Project=sfn-runner）。受け箱に始めの指示が来るまで使わない。
- aws_ship.sh <公開 IP>：版と台本を送って setup する。
- （機械の上で）verify200.sh → run_calib.sh / 第 1 波の道具 → push_small.sh <本> <名前> <バケット>（大きい出力は S3、小さい記録は small/）。
- aws_fetch_small.sh <公開 IP> <本のフォルダ> <名前>：小さい記録をデスクトップへ持ってきて GitHub に上げる。
- aws_status.sh：見回りのたびに、走っている機械の数・種類・時間と、費用の見込み（時間単価は価格の API から）、Cost Explorer の実費（引ければ）。
- aws_terminate.sh <ID>：使い終わった機械をすぐ消す（札が sfn-runner の機械だけ）。
- 未定・要確認：機械から S3 に書く権限（IAM の役割の付け方。鍵の権限で iam:PassRole ができるか）。できなければ、出力はデスクトップへ scp で持ってくる。
