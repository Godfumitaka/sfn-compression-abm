# 読むだけ：ページファイルの設定と使用、メモリのコミット、Windows Update・NVIDIA・ゲームの更新に関わる過程とサービスの状態。
$ErrorActionPreference = 'SilentlyContinue'
"## pagefile"
(Get-CimInstance Win32_ComputerSystem).AutomaticManagedPagefile | ForEach-Object { "AutomaticManagedPagefile`t$_" }
Get-CimInstance Win32_PageFileUsage | ForEach-Object { "PageFileUsage`t$($_.Name)`tAllocatedBaseSize_MB=$($_.AllocatedBaseSize)`tCurrentUsage_MB=$($_.CurrentUsage)`tPeakUsage_MB=$($_.PeakUsage)" }
Get-CimInstance Win32_PageFileSetting | ForEach-Object { "PageFileSetting`t$($_.Name)`tInitial=$($_.InitialSize)`tMax=$($_.MaximumSize)" }
$os = Get-CimInstance Win32_OperatingSystem
"TotalVisibleMemory_MB`t$([int]($os.TotalVisibleMemorySize/1024))`tFreePhysical_MB`t$([int]($os.FreePhysicalMemory/1024))"
"TotalVirtualMemory_MB`t$([int]($os.TotalVirtualMemorySize/1024))`tFreeVirtual_MB`t$([int]($os.FreeVirtualMemory/1024))"
"LastBootUpTime`t$($os.LastBootUpTime)"
"## services"
Get-Service wuauserv,BITS,UsoSvc,DoSvc,TrustedInstaller,NvContainerLocalSystem,NVDisplay.ContainerLocalSystem,SteamService,'Riot Vanguard',vgc | ForEach-Object { "$($_.Name)`t$($_.Status)" }
"## processes"
Get-Process | Where-Object { $_.ProcessName -match 'nvcontainer|NVIDIA|Share|steam|Riot|VALORANT|Overwolf|obs|wuau|TiWorker|MoUso|setup|install|update|Battle|EA|Ubisoft|upc|Epic|OneDrive|MsMpEng|SearchIndexer' } |
  Sort-Object ProcessName | ForEach-Object { "$($_.ProcessName)`t$($_.Id)`tWS_MB=$([int]($_.WorkingSet64/1MB))`tCPU_s=$([int]$_.CPU)`tStart=$($_.StartTime)" }
"## nvidia_capture_settings"
Get-ItemProperty 'HKCU:\Software\NVIDIA Corporation\Global\ShadowPlay\NVSPCAPS' | Select-Object -Property * -ExcludeProperty PS* | Format-List | Out-String -Width 200
"## recent_temp_writes"
foreach ($d in "$env:TEMP","C:\Windows\Temp","$env:LOCALAPPDATA\Temp") { $s = (Get-ChildItem -LiteralPath $d -Recurse -Force -File | Measure-Object Length -Sum).Sum; "$d`t$([int64]$s)" }
