$s = Get-Counter '\Processor Information(0,*)\% Processor Time','\Processor Information(0,*)\% Processor Performance' -SampleInterval 2 -MaxSamples 5
$s | ForEach-Object { $_.CounterSamples } | Group-Object Path | ForEach-Object {
  $p = $_.Name
  if ($p -match 'information\(0,([^)]+)\)\\% processor (\w+)$') {
    $avg = [math]::Round(($_.Group | Measure-Object CookedValue -Average).Average, 1)
    "$($Matches[1])`t$($Matches[2])`t$avg"
  }
}
