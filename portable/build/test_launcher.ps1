# Test harness for the portable launcher: encoding rules, port fallback,
# idempotency, health, start/stop. Opens no windows.
#
# Chinese is written as [char] escapes rather than literals so this file stays
# readable in any editor, but it is BOM-encoded anyway (bom_fix.ps1 enforces it).

param(
    [string]$OutRoot = 'D:\Projects\expo-hub-portable'
)

$pkg  = Join-Path $OutRoot ('ExpoHub-' + [char]0x8BD5 + [char]0x7528 + [char]0x7248)
$fail = 0

function Check($name, $cond, $detail) {
    if ($cond) { Write-Host "  [PASS] $name  $detail" -ForegroundColor Green }
    else       { Write-Host "  [FAIL] $name  $detail" -ForegroundColor Red; $script:fail++ }
}

function Test-PortListening([int]$Port) {
    return @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue).Count -gt 0
}

# Identify OUR instance. Gate on "is anything even listening" first, otherwise
# every empty port costs a TCP timeout and the harness takes minutes.
# Only the portable build answers /api/health with mode=portable; a dev backend
# on the same range 404s there, so the two are never confused.
function Find-PortablePort {
    foreach ($p in 8002..8010) {
        if (-not (Test-PortListening $p)) { continue }
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$p/api/health" -TimeoutSec 2 -UseBasicParsing
            if ($r.StatusCode -eq 200) {
                $j = $r.Content | ConvertFrom-Json
                if ($j.mode -eq 'portable') { return $p }
            }
        } catch { }
    }
    return 0
}

Write-Host "`n===== encoding checks =====" -ForegroundColor Cyan
Get-ChildItem $pkg -Filter *.bat | ForEach-Object {
    $n = ([IO.File]::ReadAllBytes($_.FullName) | Where-Object { $_ -gt 127 }).Count
    Check "$($_.Name) pure-ascii" ($n -eq 0) "non-ascii=$n"
}
Get-ChildItem $pkg -Recurse -Include *.ps1 | ForEach-Object {
    $hex = (([IO.File]::ReadAllBytes($_.FullName)[0..2]) | ForEach-Object { $_.ToString('X2') }) -join ' '
    Check "$($_.Name) has-BOM" ($hex -eq 'EF BB BF') "prefix=$hex"
}

Write-Host "`n===== pre-start =====" -ForegroundColor Cyan
Check "no portable instance running" ((Find-PortablePort) -eq 0) ""
$devOn8002 = Test-PortListening 8002
Write-Host "  (context) something else already listens on 8002: $devOn8002"

Write-Host "`n===== run start.ps1 -NoBrowser -NoDialog =====" -ForegroundColor Cyan
$sw = [Diagnostics.Stopwatch]::StartNew()
& "$pkg\scripts\start.ps1" -NoBrowser -NoDialog
$startRc = $LASTEXITCODE
$sw.Stop()
$startSec = [math]::Round($sw.Elapsed.TotalSeconds, 1)
Check "start.ps1 exit 0" ($startRc -eq 0) "rc=$startRc, took=${startSec}s"
Check "startup under 25s" ($startSec -lt 25) "took ${startSec}s"

Write-Host "`n===== post-start verification =====" -ForegroundColor Cyan
$pidFile = "$pkg\logs\server.pid"
Check "pid file created" (Test-Path $pidFile) ""

$fields = @()
if (Test-Path $pidFile) { $fields = (Get-Content $pidFile -Raw).Trim() -split '\s+' }
$pidVal  = if ($fields.Count -ge 1) { $fields[0] } else { '' }
$portVal = if ($fields.Count -ge 2) { $fields[1] } else { '' }
Check "pid+port recorded" ($fields.Count -eq 2) "pid=$pidVal port=$portVal"
Check "process alive" ($null -ne (Get-Process -Id $pidVal -ErrorAction SilentlyContinue)) "pid=$pidVal"

$port = Find-PortablePort
Check "portable instance reachable" ($port -ne 0) "port=$port"

if ($devOn8002) {
    Check "PORT FALLBACK worked (8002 busy -> picked another)" ($port -ne 0 -and $port -ne 8002) "chose $port"
}
Check "recorded port matches live port" ("$port" -eq "$portVal") "file=$portVal live=$port"

try {
    $h = Invoke-WebRequest -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 5 -UseBasicParsing
    $j = $h.Content | ConvertFrom-Json
    Check "health 200 + database ok" ($h.StatusCode -eq 200 -and $j.database -eq 'ok') "database=$($j.database)"
} catch { Check "health" $false "$($_.Exception.Message)" }

try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/" -TimeoutSec 5 -UseBasicParsing
    Check "root serves HTML" ($r.Headers['Content-Type'] -like '*text/html*') "$($r.Headers['Content-Type'])"
} catch { Check "root serves HTML" $false "$($_.Exception.Message)" }

try {
    $a = Invoke-WebRequest -Uri "http://127.0.0.1:$port/api/exhibitions" -TimeoutSec 5 -UseBasicParsing
    $aj = $a.Content | ConvertFrom-Json
    Check "business API works" ($a.StatusCode -eq 200) "exhibitions=$($aj.data.list.Count)"
} catch { Check "business API" $false "$($_.Exception.Message)" }

Write-Host "`n===== idempotency =====" -ForegroundColor Cyan
$snapBefore = (Get-Content $pidFile -Raw).Trim()
$sw2 = [Diagnostics.Stopwatch]::StartNew()
& "$pkg\scripts\start.ps1" -NoBrowser -NoDialog
$sw2.Stop()
$snapAfter = (Get-Content $pidFile -Raw).Trim()
Check "second start reuses instance" ($snapBefore -eq $snapAfter) "before=[$snapBefore] after=[$snapAfter]"
Check "second start is fast (<8s)" ($sw2.Elapsed.TotalSeconds -lt 8) "took $([math]::Round($sw2.Elapsed.TotalSeconds,1))s"
Check "still exactly one portable instance" ((Find-PortablePort) -eq $port) ""

Write-Host "`n===== run stop.ps1 =====" -ForegroundColor Cyan
& "$pkg\scripts\stop.ps1" -Quiet
Check "stop.ps1 exit 0" ($LASTEXITCODE -eq 0) "rc=$LASTEXITCODE"
Start-Sleep -Seconds 2
Check "portable instance gone" ((Find-PortablePort) -eq 0) ""
Check "pid file removed" (-not (Test-Path $pidFile)) ""
Check "process terminated" ($null -eq (Get-Process -Id $pidVal -ErrorAction SilentlyContinue)) "pid=$pidVal"
if ($devOn8002) {
    Check "dev server on 8002 untouched" (Test-PortListening 8002) ""
}

Write-Host "`n===== RESULT =====" -ForegroundColor Cyan
if ($fail -eq 0) { Write-Host "  ALL PASSED" -ForegroundColor Green } else { Write-Host "  $fail CHECK(S) FAILED" -ForegroundColor Red }
exit $fail
