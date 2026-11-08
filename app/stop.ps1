# Stops the local stack (only the processes this app started).
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$logs = Join-Path $root 'data\logs'
foreach ($n in 'web','embed','llm') {
  $f = Join-Path $logs "$n.pid"
  if (Test-Path $f) {
    $id = [int](Get-Content $f)
    $p = Get-Process -Id $id -ErrorAction SilentlyContinue
    if ($p) { Stop-Process -Id $id -Force; Write-Host "stopped $n (pid $id)" }
    Remove-Item $f -Force
  }
}
