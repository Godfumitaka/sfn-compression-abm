# 読むだけ：指定の場所（既定 C:\）の下で、指定の時刻より後に書かれた 50MB 以上のファイルを、大きい順に標準出力へ出す。
param([string]$Since, [string]$Root = 'C:\')
$ErrorActionPreference = 'SilentlyContinue'
$t = [datetime]::Parse($Since)
Get-ChildItem -LiteralPath $Root -Recurse -Force -File | Where-Object { $_.LastWriteTime -gt $t -and $_.Length -gt 50MB } |
  Sort-Object Length -Descending | ForEach-Object { "$($_.FullName)`t$($_.Length)`t$($_.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))" }
