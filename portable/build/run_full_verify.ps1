# ASCII-only runner: timed start -> business verification -> timed stop.
#
# 用途：出包后确认"服务起得来、业务链路通、停得干净"，并给出耗时。
# 比 test_acceptance.ps1 轻（不解压 ZIP、不开窗口），适合改完后端快速回归。

param(
    [string]$OutRoot = 'D:\Projects\expo-hub-portable'
)

$name  = 'ExpoHub-' + [char]0x8BD5 + [char]0x7528 + [char]0x7248
$pkg   = Join-Path $OutRoot $name
$build = $PSScriptRoot          # 本脚本与 verify_business.py 同目录
$py    = Join-Path $pkg 'runtime\python.exe'
$fail  = 0

if (-not (Test-Path $py)) {
    Write-Host "  [FAIL] package not found: $pkg" -ForegroundColor Red
    exit 1
}

Write-Host "`n########## STEP 1: timed start ##########" -ForegroundColor Cyan
$sw = [Diagnostics.Stopwatch]::StartNew()
& "$pkg\scripts\start.ps1" -NoBrowser -NoDialog | Out-Null
$rc = $LASTEXITCODE
$sw.Stop()
$t = [math]::Round($sw.Elapsed.TotalSeconds, 1)
Write-Host "  start.ps1 rc=$rc  took ${t}s"

Write-Host "`n########## STEP 2: business verification ##########" -ForegroundColor Cyan
$env:PYTHONIOENCODING = 'utf-8'
& $py "$build\verify_business.py" --pkg $pkg
$biz = $LASTEXITCODE
if ($biz -ne 0) { $fail++ }

Write-Host "`n########## STEP 3: timed stop ##########" -ForegroundColor Cyan
$sw2 = [Diagnostics.Stopwatch]::StartNew()
& "$pkg\scripts\stop.ps1" -Quiet
$rc2 = $LASTEXITCODE
$sw2.Stop()
$t2 = [math]::Round($sw2.Elapsed.TotalSeconds, 1)
Write-Host "  stop.ps1 rc=$rc2  took ${t2}s"

Write-Host "`n########## SUMMARY ##########" -ForegroundColor Cyan
Write-Host "  start : ${t}s (rc=$rc)"
Write-Host "  stop  : ${t2}s (rc=$rc2)"
Write-Host "  business check failures: $fail"
if ($rc -ne 0 -or $rc2 -ne 0 -or $fail -ne 0) {
    Write-Host "  RESULT: PROBLEMS" -ForegroundColor Red
    exit 1
}
Write-Host "  RESULT: OK" -ForegroundColor Green
exit 0
