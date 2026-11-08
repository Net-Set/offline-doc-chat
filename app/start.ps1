# Starts the fully local stack: chat model + embedding model (llama.cpp) + web app.
# Everything binds to 127.0.0.1 only. No internet access is needed or used.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$bin  = Join-Path $root 'bin\llama-server.exe'
$logs = Join-Path $root 'data\logs'
New-Item -ItemType Directory -Force $logs | Out-Null
$py = Join-Path $root 'venv\Scripts\python.exe'

function Start-Bg($name, $exe, $argList) {
  $p = Start-Process -FilePath $exe -ArgumentList $argList -WorkingDirectory $root -WindowStyle Hidden `
       -RedirectStandardOutput (Join-Path $logs "$name.out.log") -RedirectStandardError (Join-Path $logs "$name.err.log") -PassThru
  $p.Id | Out-File (Join-Path $logs "$name.pid") -Encoding ascii
  Write-Host "started $name (pid $($p.Id))"
}

function Wait-Ready($url, $label, $secs) {
  $t = [DateTime]::Now.AddSeconds($secs)
  while ([DateTime]::Now -lt $t) {
    try { if ((Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2).StatusCode -eq 200) { Write-Host "$label ready"; return $true } } catch {}
    Start-Sleep -Seconds 2
  }
  Write-Host "$label NOT ready after $secs s - see $logs"; return $false
}

& (Join-Path $root 'stop.ps1') | Out-Null

# Chat model: Qwen2.5-1.5B-Instruct (Q4_K_M). 4096 context keeps CPU prefill affordable.
Start-Bg 'llm' $bin @('-m', (Join-Path $root 'models\qwen2.5-1.5b-instruct-q4_k_m.gguf'),
  '--host','127.0.0.1','--port','8081','-c','4096','-t','4','-np','1','--no-webui')

# Embedding model: nomic-embed-text-v1.5 (Q4_K_M)
Start-Bg 'embed' $bin @('-m', (Join-Path $root 'models\nomic-embed-text-v1.5.Q4_K_M.gguf'),
  '--embedding','--host','127.0.0.1','--port','8082','-c','2048','-b','2048','-ub','2048','-t','2','-np','1')

Start-Bg 'web' $py @('-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8000')

$a = Wait-Ready 'http://127.0.0.1:8081/health' 'chat model' 180
$b = Wait-Ready 'http://127.0.0.1:8082/health' 'embedding model' 120
$c = Wait-Ready 'http://127.0.0.1:8000/api/health' 'web app' 60
if ($a -and $b -and $c) { Write-Host "`nOpen http://127.0.0.1:8000 in your browser." }
