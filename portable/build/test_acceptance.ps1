# ASCII-only final acceptance test.
#
# Simulates the leader's real path end to end:
#   fresh extract of the ZIP (into a path containing Chinese characters)
#   -> double-click the launch .bat
#   -> app window opens by itself
#
# This is the only step that exercises the .bat -> start.ps1 chain and the
# Edge --app window. It DOES open a real browser window on screen.

param(
    [string]$OutRoot = 'D:\Projects\expo-hub-portable',
    [string]$SimRoot = ''
)

$root = $OutRoot
$name = 'ExpoHub-' + [char]0x8BD5 + [char]0x7528 + [char]0x7248
$zip  = Join-Path $root "$name.zip"

# 模拟领导侧的解压位置。**刻意带中文** —— 中文路径下的 Python embeddable
# 与脚本行为是必须验证的一环（领导很可能解压到带中文的目录）。
if (-not $SimRoot) {
    $SimRoot = Join-Path (Split-Path $OutRoot -Parent) ('验收-' + $name)
}
$simRoot = $SimRoot
$simPkg  = Join-Path $simRoot $name
$fail = 0

function Check($n, $c, $d) {
    if ($c) { Write-Host "  [PASS] $n  $d" -ForegroundColor Green }
    else    { Write-Host "  [FAIL] $n  $d" -ForegroundColor Red; $script:fail++ }
}

function Find-PortablePort {
    foreach ($p in 8002..8010) {
        if (@(Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue).Count -eq 0) { continue }
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$p/api/health" -TimeoutSec 2 -UseBasicParsing
            if ($r.StatusCode -eq 200 -and (($r.Content | ConvertFrom-Json).mode -eq 'portable')) { return $p }
        } catch { }
    }
    return 0
}

Write-Host "`n=== 1. extract ZIP into a Chinese-named folder (as the leader would) ===" -ForegroundColor Cyan
Check "zip exists" (Test-Path $zip) "$([math]::Round((Get-Item $zip).Length/1MB,2)) MB"
if (Test-Path $simRoot) { Remove-Item $simRoot -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Force -Path $simRoot | Out-Null

$sw = [Diagnostics.Stopwatch]::StartNew()
Expand-Archive -Path $zip -DestinationPath $simRoot -Force
$sw.Stop()
Write-Host "  extracted in $([math]::Round($sw.Elapsed.TotalSeconds,1))s to $simRoot"

Write-Host "`n=== 2. did the Chinese filenames survive the zip round-trip? ===" -ForegroundColor Cyan
# ⚠️ 这里**不要** Set-Location 进沙箱。PowerShell 的当前目录一旦落进去，
# 第 6 步的删除必然失败——Windows 不允许删除任何进程的当前工作目录，
# 而且报错是"拒绝访问"，很容易误判成杀软拦截或句柄未释放。
# 下面全部用 Join-Path $simPkg 的绝对路径，本来也不需要切目录。
foreach ($f in '双击启动.bat', '停止运行.bat', '检查更新.bat', '使用说明.docx') {
    Check "$f" (Test-Path (Join-Path $simPkg $f)) ""
}
Check "runtime\python.exe" (Test-Path (Join-Path $simPkg 'runtime\python.exe')) ""
Check "server\web\index.html" (Test-Path (Join-Path $simPkg 'server\web\index.html')) ""
Check "server\expohub.db" (Test-Path (Join-Path $simPkg 'server\expohub.db')) ""

Write-Host "`n=== 3. double-click the launch .bat (real path, opens Edge window) ===" -ForegroundColor Cyan
$pre = Find-PortablePort
Check "nothing running before" ($pre -eq 0) ""

$bat = Join-Path $simPkg '双击启动.bat'
$sw2 = [Diagnostics.Stopwatch]::StartNew()
# Do NOT pass -Wait: the launcher deliberately detaches the server process, and
# -Wait would block on that grandchild forever.
Start-Process -FilePath $bat | Out-Null
# Wait for the service to answer instead (the launcher's own success signal).
for ($i = 0; $i -lt 60; $i++) {
    if ((Find-PortablePort) -ne 0) { break }
    Start-Sleep -Seconds 1
}
$sw2.Stop()
Write-Host "  service became reachable after $([math]::Round($sw2.Elapsed.TotalSeconds,1))s"

Write-Host "`n=== 4. did it come up? ===" -ForegroundColor Cyan
$port = Find-PortablePort
Check "portable instance is up" ($port -ne 0) "port=$port"

if ($port -ne 0) {
    try {
        $h = Invoke-WebRequest -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 5 -UseBasicParsing
        Check "health ok" (($h.Content | ConvertFrom-Json).database -eq 'ok') ""
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/" -TimeoutSec 5 -UseBasicParsing
        Check "serves the app page" ($r.Headers['Content-Type'] -like '*text/html*') ""
    } catch { Check "http" $false "$($_.Exception.Message)" }

    Start-Sleep -Seconds 3
    $edgeWins = @(Get-Process msedge -ErrorAction SilentlyContinue |
                  Where-Object { $_.MainWindowTitle -like '*ExpoHub*' })
    Check "Edge app window opened by itself" ($edgeWins.Count -gt 0) `
          "$($edgeWins.Count) window(s): $($edgeWins.MainWindowTitle -join ' | ')"
}

Write-Host "`n=== 5. stop it again ===" -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $simPkg 'scripts\stop.ps1') -Quiet | Out-Null
Check "stop rc=0" ($LASTEXITCODE -eq 0) "rc=$LASTEXITCODE"
Start-Sleep -Seconds 2
Check "instance gone" ((Find-PortablePort) -eq 0) ""

Write-Host "`n=== 6. cleanup sandbox ===" -ForegroundColor Cyan
# 保险：确保本进程的当前目录不在沙箱内（否则删除必失败，见第 2 步的注释）
Set-Location (Split-Path $simRoot -Parent)
# 刚被 kill 的进程句柄也不一定立刻释放，重试几轮
Remove-Item -LiteralPath $simRoot -Recurse -Force -ErrorAction SilentlyContinue
for ($i = 1; $i -le 5 -and (Test-Path $simRoot); $i++) {
    Start-Sleep -Seconds 2
    Remove-Item -LiteralPath $simRoot -Recurse -Force -ErrorAction SilentlyContinue
}
Check "sandbox removed (no 96MB left behind)" (-not (Test-Path $simRoot)) ""

Write-Host "`n=== RESULT ===" -ForegroundColor Cyan
if ($fail -eq 0) { Write-Host "  ACCEPTANCE PASSED" -ForegroundColor Green } else { Write-Host "  $fail CHECK(S) FAILED" -ForegroundColor Red }
exit $fail
