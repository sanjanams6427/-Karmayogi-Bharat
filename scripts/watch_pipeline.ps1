<#
.SYNOPSIS
  Live, color-coded tail of logs/pipeline.log — a clearer view of what's
  actually happening during a dubbing job than the web UI's log panel.

.USAGE
  From anywhere:
    C:\dataset\-Karmayogi-Bharat\scripts\watch_pipeline.ps1

  Leave it running in its own terminal window while you drive the web UI
  in the browser. Ctrl+C to stop watching (does not stop the server/job).

.WHAT THE COLORS MEAN
  White-on-red  : TIMEOUT / WEDGED / STUCK.
                  "TIMEOUT ... hit max_time deadline (stopped cleanly)" —
                  a generation ran past its deadline and was stopped from
                  INSIDE the generation loop; the pipeline falls back to
                  MMS-TTS for that segment. Costs wall-clock time but
                  leaves no stuck GPU thread behind.
                  "WEDGED" — generate() did not return even past its
                  deadline + grace period: a driver-level stall, the
                  serious one. A cluster of these means the GPU/driver is
                  in trouble.
                  Shard-worker lines carry a "gpu" field ("gpu": "2") so
                  you can tell WHICH GPU each timeout came from.
  Red           : FAILED / ERROR / Exception — something actually broke.
  Magenta       : evicted / unload_models — GPU memory was freed.
  Cyan          : Loading / loaded — a model just came onto the GPU.
  Yellow        : WARNING.
  Green         : SUCCESS / completed.
  Gray          : everything else (routine per-segment progress).
#>

param(
    [string]$LogPath = (Join-Path $PSScriptRoot "..\logs\pipeline.log")
)

if (-not (Test-Path $LogPath)) {
    Write-Host "Log file not found yet: $LogPath" -ForegroundColor Yellow
    Write-Host "(It's created on the first pipeline run. Start a job from the web UI, then re-run this script.)" -ForegroundColor DarkGray
    exit 1
}

Write-Host "Watching $LogPath" -ForegroundColor Cyan
Write-Host "Ctrl+C to stop (the server and any running job keep going).`n" -ForegroundColor DarkGray

Get-Content -Path $LogPath -Wait -Tail 30 | ForEach-Object {
    $line = $_
    switch -Regex ($line) {
        'STUCK FOR LONG TIME|TIMEOUT|WEDGED|STALLED' {
            Write-Host $line -ForegroundColor White -BackgroundColor DarkRed
        }
        'FAILED|ERROR|Exception|Traceback' {
            Write-Host $line -ForegroundColor Red
        }
        'evicted|unload_models' {
            Write-Host $line -ForegroundColor Magenta
        }
        'Loading|loaded|^\[.*\] Load' {
            Write-Host $line -ForegroundColor Cyan
        }
        'SUCCESS|completed|✅' {
            Write-Host $line -ForegroundColor Green
        }
        'WARNING|⚠' {
            Write-Host $line -ForegroundColor Yellow
        }
        default {
            Write-Host $line -ForegroundColor Gray
        }
    }
}
