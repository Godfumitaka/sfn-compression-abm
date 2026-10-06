$ErrorActionPreference = 'SilentlyContinue'
"## WindowsUpdateClient events (today)"
Get-WinEvent -LogName 'Microsoft-Windows-WindowsUpdateClient/Operational' -MaxEvents 40 | Where-Object { $_.TimeCreated -gt (Get-Date).Date } | ForEach-Object { "$($_.TimeCreated.ToString('HH:mm:ss'))`t$($_.Id)`t$(($_.Message -split "`n")[0])" }
"## System log: WindowsUpdateClient / Servicing (today)"
Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=(Get-Date).Date} -MaxEvents 200 | Where-Object { $_.ProviderName -match 'WindowsUpdateClient|Servicing|Kernel-Power|User32' } | ForEach-Object { "$($_.TimeCreated.ToString('HH:mm:ss'))`t$($_.ProviderName)`t$($_.Id)`t$(($_.Message -split "`n")[0])" }
"## DeliveryOptimization cache"
$p = 'C:\Windows\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache'
$s = (Get-ChildItem -LiteralPath $p -Recurse -Force -File | Measure-Object Length -Sum); "DO_cache`t$($s.Sum)`t$($s.Count)"
Get-DeliveryOptimizationPerfSnapThisMonth | Format-List | Out-String -Width 200
"## SoftwareDistribution\Download newest"
Get-ChildItem -Force 'C:\Windows\SoftwareDistribution\Download' | Sort-Object LastWriteTime -Descending | Select-Object -First 6 | ForEach-Object { $z = (Get-ChildItem -LiteralPath $_.FullName -Recurse -Force -File | Measure-Object Length -Sum).Sum; if (-not $_.PSIsContainer) { $z = $_.Length }; "$($_.LastWriteTime.ToString('MM-dd HH:mm'))`t$([int64]$z)`t$($_.Name)" }
