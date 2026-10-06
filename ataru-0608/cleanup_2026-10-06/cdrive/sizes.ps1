# 読むだけ：C: の大きいフォルダの大きさ（各フォルダの下のファイルの和）を標準出力へ出す。
$ErrorActionPreference = 'SilentlyContinue'
$targets = @()
$targets += Get-ChildItem -Force -Directory 'C:\Users\tatsu' | ForEach-Object FullName
$targets += Get-ChildItem -Force -Directory 'C:\Users\tatsu\AppData\Local' | ForEach-Object FullName
$targets += Get-ChildItem -Force -Directory 'C:\Users\tatsu\AppData\Roaming' | ForEach-Object FullName
$targets += Get-ChildItem -Force -Directory 'C:\ProgramData' | ForEach-Object FullName
$targets += Get-ChildItem -Force -Directory 'C:\' | ForEach-Object FullName
$targets += 'C:\Windows\Temp','C:\Windows\SoftwareDistribution','C:\Windows\Logs','C:\Windows\WinSxS','C:\Windows\Prefetch','C:\Windows\LiveKernelReports','C:\Windows\Minidump','C:\Windows\System32\LogFiles'
$skip = 'C:\Users','C:\Windows','C:\Users\tatsu\AppData','C:\Users\tatsu\AppData\Local','C:\Users\tatsu\AppData\Roaming'
foreach ($t in ($targets | Sort-Object -Unique)) {
  if ($skip -contains $t) { continue }
  $s = (Get-ChildItem -LiteralPath $t -Recurse -Force -File | Measure-Object Length -Sum).Sum
  "$t`t$([int64]$s)"
}
foreach ($f in 'C:\pagefile.sys','C:\hiberfil.sys','C:\swapfile.sys') { $i = Get-Item -Force $f; if ($i) { "$f`t$($i.Length)" } }
$d = Get-PSDrive C; "C_free`t$($d.Free)"
