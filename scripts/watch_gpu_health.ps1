# Live correlator: GPU stats + shell responsiveness + pipeline log, one timestamped stream.
#
# Why this exists: after the Sept 2026 GPU-driver-wedge incident, we could not prove
# whether Explorer/Task Manager hangs were actually caused by GPU contention from the
# dubbing pipeline, because no Windows event log evidence survived to check afterward.
# This script watches all three signals live and writes them to one correlatable log
# so if it happens again, we have a real timestamped trace instead of reconstructing
# after the fact.
#
# Usage: powershell -File scripts\watch_gpu_health.ps1
# Stop with Ctrl+C. Log written to logs\gpu_watch.log (appended, safe to leave running for days).

$ErrorActionPreference = "SilentlyContinue"
$repoRoot   = Split-Path -Parent $PSScriptRoot
$pipeLog    = Join-Path $repoRoot "logs\pipeline.log"
$watchLog   = Join-Path $repoRoot "logs\gpu_watch.log"
$pollSecs   = 5

New-Item -ItemType Directory -Force -Path (Split-Path $watchLog) | Out-Null

function Write-Watch($line) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $entry = "[$ts] $line"
    Add-Content -Path $watchLog -Value $entry
    Write-Host $entry
}

# Track how far we've already read pipeline.log so we only report new lines.
$lastLineCount = 0
if (Test-Path $pipeLog) {
    $lastLineCount = (Get-Content $pipeLog | Measure-Object -Line).Lines
}

Write-Watch "=== watch_gpu_health started (poll every ${pollSecs}s) ==="

while ($true) {
    # --- GPU query, wrapped in a job with a hard timeout so a wedged driver can't hang THIS monitor ---
    # Both option values MUST be quoted -- Start-Job re-parses the scriptblock text, and
    # unquoted commas in --query-gpu=a,b,c / --format=csv,noheader get split into separate
    # (invalid) nvidia-smi arguments when run this way.
    $job = Start-Job -ScriptBlock {
        nvidia-smi --query-gpu="index,memory.used,memory.total,utilization.gpu,temperature.gpu" --format="csv,noheader"
    }
    $done = Wait-Job $job -Timeout 8
    if ($null -eq $done) {
        Write-Watch "GPU: *** nvidia-smi UNRESPONSIVE (no reply after 8s) - possible driver wedge in progress ***"
        Stop-Job $job | Out-Null
    } else {
        $gpuOut = Receive-Job $job
        if ($gpuOut) {
            # Known driver quirk on this box: memory.used sometimes reports a garbage
            # sentinel (~2^44 MiB) instead of a real reading (happens constantly at
            # idle). Clamping it to memory.total made every idle GPU display as FULL
            # (49140MiB/49140MiB), which is worse than useless in a health log —
            # print "used=n/a" so an unreliable reading can't be mistaken for a real
            # full-memory condition.
            $clean = foreach ($row in $gpuOut) {
                $f = $row -split ",\s*"
                if ($f.Count -ge 5) {
                    $used  = [double]($f[1] -replace " MiB","")
                    $total = [double]($f[2] -replace " MiB","")
                    if ($used -gt $total) {
                        "gpu{0}: used=n/a(sentinel)/{1}MiB  util={2}  temp={3}" -f $f[0].Trim(), [int]$total, $f[3].Trim(), $f[4].Trim()
                    } else {
                        "gpu{0}: {1}MiB/{2}MiB  util={3}  temp={4}" -f $f[0].Trim(), [int]$used, [int]$total, $f[3].Trim(), $f[4].Trim()
                    }
                } else {
                    $row
                }
            }
            Write-Watch "GPU: $($clean -join '  |  ')"
        } else {
            Write-Watch "GPU: query returned no data"
        }
    }
    Remove-Job $job -Force

    # --- Shell responsiveness: Explorer + Task Manager ---
    $shellProcs = Get-Process explorer, taskmgr -ErrorAction SilentlyContinue
    foreach ($p in $shellProcs) {
        if (-not $p.Responding) {
            Write-Watch "SHELL: *** $($p.ProcessName) (PID $($p.Id)) NOT RESPONDING ***"
        }
    }
    $taskmgr = $shellProcs | Where-Object { $_.ProcessName -eq "taskmgr" }
    if ($taskmgr) {
        Write-Watch "SHELL: taskmgr CPU=$($taskmgr.CPU)s (rising fast = spinning on GPU query)"
    }

    # --- New pipeline.log activity (surfaces TIMEOUT / STUCK lines immediately) ---
    if (Test-Path $pipeLog) {
        $allLines = Get-Content $pipeLog
        $count = $allLines.Count
        if ($count -gt $lastLineCount) {
            $newLines = $allLines[$lastLineCount..($count - 1)]
            foreach ($line in $newLines) {
                if ($line -match "TIMEOUT|STUCK|WEDGED|STALLED|respawn|giving up|evicted|SUCCESS|FAILED") {
                    Write-Watch "PIPE: $line"
                }
            }
            $lastLineCount = $count
        }
    }

    Start-Sleep -Seconds $pollSecs
}
