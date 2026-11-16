# Peer-to-Peer Content-Addressable Chunk Streaming Protocol - Phase 1 baseline.
# Runs unit/integration tests, then 4 CONCURRENT clients against one server.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$hostAddress = "127.0.0.1"
$port = 5001
$numberOfClients = 4

# System Python (no virtual environment).
$python = $null
foreach ($candidate in @("python", "python3")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) { $python = $cmd.Source; break }
}
if (-not $python) { throw "Python 3 was not found on PATH." }

Write-Host "===================================================="
Write-Host " Peer-to-Peer Content-Addressable Chunk Streaming Protocol"
Write-Host " Phase 1 Baseline Local Test - $numberOfClients concurrent clients"
Write-Host "===================================================="
& $python --version

New-Item -ItemType Directory -Force -Path "logs" | Out-Null
$runtimeLogDir = Join-Path ([IO.Path]::GetTempPath()) ("casp_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $runtimeLogDir | Out-Null
$env:CASP_LOG_DIR = $runtimeLogDir
$env:PYTHONIOENCODING = "utf-8"

$serverLog = "logs\baseline_server.log"
$serverErr = Join-Path $runtimeLogDir "server.stderr"
Remove-Item "logs\baseline_server.log", "logs\baseline_client_*.log" -ErrorAction SilentlyContinue

Write-Host "`n[1/3] Running unit and integration tests..."
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Unit/integration tests FAILED." }

$server = $null
$exitStatus = 0
try {
    Write-Host "`n[2/3] Starting UDP server on ${hostAddress}:$port..."
    if (Get-NetUDPEndpoint -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "UDP port $port is already in use. Stop the existing process first."
    }

    $server = Start-Process -FilePath $python `
        -ArgumentList @("server.py", "--host", $hostAddress, "--port", "$port") `
        -WorkingDirectory $PSScriptRoot -NoNewWindow -PassThru `
        -RedirectStandardOutput $serverLog -RedirectStandardError $serverErr
    $null = $server.Handle   # cache handle so ExitCode is readable later

    $ready = $false
    for ($n = 0; $n -lt 50; $n++) {
        Start-Sleep -Milliseconds 100
        if ($server.HasExited) { break }
        if ((Test-Path $serverLog) -and (Select-String -Path $serverLog -Pattern "listening" -Quiet)) { $ready = $true; break }
    }
    if (-not $ready) { throw "Server did not start. See $serverLog" }
    Write-Host "Server started successfully."

    Write-Host "`n[3/3] Running INIT and DATA exchanges for $numberOfClients concurrent clients..."
    $clients = @()
    for ($i = 1; $i -le $numberOfClients; $i++) {
        $clientLog = "logs\baseline_client_$i.log"
        $clientErr = Join-Path $runtimeLogDir "client_$i.stderr"
        $p = Start-Process -FilePath $python `
            -ArgumentList @("client.py", "--host", $hostAddress, "--port", "$port",
                            "--peer-id", "$i", "--name", "baseline-peer-$i",
                            "--message", "`"Baseline DATA test from Client $i`"") `
            -WorkingDirectory $PSScriptRoot -NoNewWindow -PassThru `
            -RedirectStandardOutput $clientLog -RedirectStandardError $clientErr
        $null = $p.Handle
        $clients += [pscustomobject]@{ Id = $i; Process = $p; Log = $clientLog }
    }

    $failed = $false
    foreach ($c in $clients) {
        $c.Process.WaitForExit()
        if ($c.Process.ExitCode -ne 0) {
            Write-Host "Client $($c.Id): FAILED (exit code $($c.Process.ExitCode))"
            $failed = $true
        } else {
            Write-Host "Client $($c.Id): exit code 0"
        }
    }

    Write-Host "`n===================================================="
    Write-Host " TEST RESULTS"
    Write-Host "===================================================="
    foreach ($c in $clients) {
        Write-Host "`n----- Client $($c.Id) Log -----"
        Get-Content $c.Log | ForEach-Object { Write-Host $_ }
        if (-not (Select-String -Path $c.Log -Pattern "Communication completed successfully" -Quiet)) {
            Write-Host "FAILED: Client $($c.Id) did not complete successfully."
            $failed = $true
        }
    }

    $initCount = @(Select-String -Path $serverLog -Pattern "INIT received").Count
    $dataCount = @(Select-String -Path $serverLog -Pattern "DATA received").Count
    Write-Host "`n----- Server Validation -----"
    Write-Host "INIT messages received: $initCount / $numberOfClients"
    Write-Host "DATA messages received: $dataCount / $numberOfClients"
    if ($initCount -lt $numberOfClients) { Write-Host "FAILED: missing INIT messages."; $failed = $true }
    if ($dataCount -lt $numberOfClients) { Write-Host "FAILED: missing DATA messages."; $failed = $true }

    if ($failed) {
        Write-Host "`nFAILED: $numberOfClients-Client Baseline Test. Check logs\ for details."
        $exitStatus = 1
    } else {
        Write-Host "`nSUCCESS: $numberOfClients-Client Concurrent Baseline Test Passed."
        Write-Host "Evidence logs:"
        Write-Host " - logs\baseline_server.log"
        for ($i = 1; $i -le $numberOfClients; $i++) { Write-Host " - logs\baseline_client_$i.log" }
    }
}
catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    $exitStatus = 1
}
finally {
    if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    Remove-Item $runtimeLogDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "`nServer stopped."
}
exit $exitStatus
