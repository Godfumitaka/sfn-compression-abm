#!/bin/bash
# 見回りのたびに：この係の走っている機械の数・種類・立ててからの時間と、その時点の費用の見込み（種類×時間×オンデマンドの時間単価）。
# 時間単価は AWS の価格の API（us-east-1、Linux、共有）から引く。Cost Explorer の実費（遅れて出る）も、引けるなら並べる。
set -uo pipefail; source $(dirname "$0")/aws_env.sh
price() { aws pricing get-products --region us-east-1 --service-code AmazonEC2 --filters \
  Type=TERM_MATCH,Field=instanceType,Value=$1 Type=TERM_MATCH,Field=location,Value="US East (N. Virginia)" \
  Type=TERM_MATCH,Field=operatingSystem,Value=Linux Type=TERM_MATCH,Field=tenancy,Value=Shared \
  Type=TERM_MATCH,Field=preInstalledSw,Value=NA Type=TERM_MATCH,Field=capacitystatus,Value=Used --max-results 1 \
  --query 'PriceList[0]' --output text 2>/dev/null | python3 -c "import json,sys;d=json.loads(sys.stdin.read());od=d['terms']['OnDemand'];print(next(iter(next(iter(od.values()))['priceDimensions'].values()))['pricePerUnit']['USD'])" 2>/dev/null || echo "?"; }
aws ec2 describe-instances --filters Name=tag:Project,Values=$TAG_PROJECT Name=instance-state-name,Values=pending,running \
  --query 'Reservations[].Instances[].[InstanceId,InstanceType,LaunchTime]' --output text | while read -r id type lt; do
  h=$(python3 -c "import datetime as d;t=d.datetime.fromisoformat('$lt'.replace('Z','+00:00'));print(round((d.datetime.now(d.timezone.utc)-t).total_seconds()/3600,2))")
  p=$(price $type); [ "$p" == "?" ] && p=$(python3 -c "import json;print(json.load(open('$HOME/cloud/prices_us_east_1.json')).get('$type','?'))") && src="見込みの表" || src="価格の API"
  cost=$(python3 -c "print(round($h*float('$p'),2) if '$p'!='?' else '?')")
  echo -e "$id\t$type\t立ててから ${h} 時間\t時間単価 \$$p（$src）\t見込み \$$cost"
done
echo "走っている機械：$(aws ec2 describe-instances --filters Name=tag:Project,Values=$TAG_PROJECT Name=instance-state-name,Values=pending,running --query 'length(Reservations[].Instances[])' --output text) 台"
aws ce get-cost-and-usage --time-period Start=$(date -u -d '-7 days' +%F),End=$(date -u -d '+1 day' +%F) --granularity DAILY --metrics UnblendedCost \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["Amazon Elastic Compute Cloud - Compute"]}}' --query 'ResultsByTime[].[TimePeriod.Start,Total.UnblendedCost.Amount]' --output text 2>/dev/null \
  | sed 's/^/Cost Explorer（EC2、日ごと、USD）：/' || echo "Cost Explorer は引けなかった（権限が無いか、まだ出ていない）"
