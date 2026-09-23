<#
.SYNOPSIS
    在线更新链路的端到端测试（不需要 Gitee 账号）。

.DESCRIPTION
    在本地起一个 HTTP 服务，模拟 Gitee 的代码归档压缩包，然后：
      成功路径 —— 下载 → 解压 → 定位 expohub-backend\app → 备份 → 替换 → 重启
      失败路径 —— 坏地址必须**不破坏**现有代码（回滚），且返回非零

    测试跑在 ZIP 解压出来的副本上，不动构建工作区里的原始包。

.NOTES
    ASCII-only，不需要 BOM。
#>
param(
    [string]$OutRoot = 'D:\Projects\expo-hub-portable',
    [int]$HttpPort = 8899
)

$ErrorActionPreference = 'Continue'
$name = 'ExpoHub-' + [char]0x8BD5 + [char]0x7528 + [char]0x7248
$zip  = Join-Path $OutRoot "$name.zip"

# 测试现场：解压一份副本，改它，删它
$simRoot = Join-Path (Split-Path $OutRoot -Parent) ('更新测试-' + $name)
$simPkg  = Join-Path $simRoot $name
$work    = Join-Path $simRoot '_http'
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

# ---------------------------------------------------------------- 0. 准备现场
Write-Host "`n=== 0. prepare sandbox ===" -ForegroundColor Cyan
Check "zip exists" (Test-Path $zip) "$([math]::Round((Get-Item $zip).Length/1MB,2)) MB"
if (Test-Path $simRoot) { Remove-Item $simRoot -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Force -Path $work | Out-Null

Expand-Archive -Path $zip -DestinationPath $simRoot -Force
Check "sandbox extracted" (Test-Path (Join-Path $simPkg 'server\portable_main.py')) ""

$py = Join-Path $simPkg 'runtime\python.exe'

# ---------------------------------------------------------------- 1. 造"新版本"
Write-Host "`n=== 1. build a fake 'new release' archive (Gitee layout) ===" -ForegroundColor Cyan
# Gitee/GitHub 归档解压后形如 <repo>-<branch>\expohub-backend\app\...
$newRoot = Join-Path $work 'X-Expohub-master'
$newApp  = Join-Path $newRoot 'expohub-backend\app'
New-Item -ItemType Directory -Force -Path (Split-Path $newApp -Parent) | Out-Null
Copy-Item (Join-Path $simPkg 'server\app') $newApp -Recurse -Force
$marker = '_UPDATE_MARKER_' + (Get-Date -Format 'HHmmss') + '.txt'
Set-Content -Path (Join-Path $newApp $marker) -Value 'updated by test_update.ps1' -Encoding ascii
Write-Host "  marker file: $marker"

$srcZip = Join-Path $work 'X-Expohub-master.zip'
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($newRoot, $srcZip, [System.IO.Compression.CompressionLevel]::Fastest, $false)
Write-Host "  archive: $srcZip ($([math]::Round((Get-Item $srcZip).Length/1KB,0)) KB)"

# ---------------------------------------------------------------- 2. 起本地源
Write-Host "`n=== 2. serve it over localhost HTTP ===" -ForegroundColor Cyan
$srv = Start-Process -FilePath $py `
    -ArgumentList '-m', 'http.server', "$HttpPort", '--bind', '127.0.0.1', '--directory', $work `
    -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 2
$url = "http://127.0.0.1:$HttpPort/X-Expohub-master.zip"
try {
    $probe = Invoke-WebRequest -Uri $url -Method Head -TimeoutSec 5 -UseBasicParsing
    Check "local update source reachable" ($probe.StatusCode -eq 200) "$url"
} catch {
    Check "local update source reachable" $false "$($_.Exception.Message)"
}

# ---------------------------------------------------------------- 3. 成功路径
Write-Host "`n=== 3. success path: run update.ps1 ===" -ForegroundColor Cyan
$upd = Join-Path $simPkg 'scripts\update.ps1'
& powershell -NoProfile -ExecutionPolicy Bypass -File $upd -NoDialog -NoBrowser -SourceUrl $url
$rc = $LASTEXITCODE
Check "update.ps1 exit 0" ($rc -eq 0) "rc=$rc"

$appDst = Join-Path $simPkg 'server\app'
Check "NEW code was applied (marker present)" `
      (Test-Path (Join-Path $appDst $marker)) "expected $marker"
Check "portable_main.py kept at server root (not inside app)" `
      (Test-Path (Join-Path $simPkg 'server\portable_main.py')) ""
$backup = @(Get-ChildItem (Join-Path $simPkg 'server') -Directory -Filter 'app.bak-*' -ErrorAction SilentlyContinue)
Check "backup of previous code created" ($backup.Count -eq 1) "$($backup | Select-Object -First 1 | ForEach-Object { $_.Name })"
if ($backup.Count -eq 1) {
    Check "backup does NOT contain the new marker" `
          (-not (Test-Path (Join-Path $backup[0].FullName $marker))) ""
}

$port = Find-PortablePort
Check "service restarted after update" ($port -ne 0) "port=$port"
if ($port -ne 0) {
    try {
        $h = Invoke-WebRequest -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 5 -UseBasicParsing
        Check "health ok after update" (($h.Content | ConvertFrom-Json).database -eq 'ok') ""
    } catch { Check "health after update" $false "$($_.Exception.Message)" }
}

# ---------------------------------------------------------------- 4. 失败路径
Write-Host "`n=== 4. failure path: bad URL must not damage the install ===" -ForegroundColor Cyan
$badUrl = "http://127.0.0.1:$HttpPort/does-not-exist.zip"
& powershell -NoProfile -ExecutionPolicy Bypass -File $upd -NoDialog -NoBrowser -SourceUrl $badUrl
$rc2 = $LASTEXITCODE
Check "bad URL returns non-zero" ($rc2 -ne 0) "rc=$rc2"
Check "code still intact after failed update" (Test-Path (Join-Path $appDst $marker)) ""

try {
    $h2 = Invoke-WebRequest -Uri "http://127.0.0.1:$HttpPort/X-Expohub-master.zip" -TimeoutSec 5 -UseBasicParsing
    Check "source server still alive (not our crash)" ($h2.StatusCode -eq 200) ""
} catch { }

# ---------------------------------------------------------------- 5. 结构不合法
Write-Host "`n=== 5. malformed archive must be rejected cleanly ===" -ForegroundColor Cyan
$junkDir = Join-Path $work 'junk'
New-Item -ItemType Directory -Force -Path $junkDir | Out-Null
Set-Content -Path (Join-Path $junkDir 'readme.txt') -Value 'not a project' -Encoding ascii
[System.IO.Compression.ZipFile]::CreateFromDirectory($junkDir, (Join-Path $work 'junk.zip'), [System.IO.Compression.CompressionLevel]::Fastest, $false)
& powershell -NoProfile -ExecutionPolicy Bypass -File $upd -NoDialog -NoBrowser -SourceUrl "http://127.0.0.1:$HttpPort/junk.zip"
$rc3 = $LASTEXITCODE
Check "malformed archive returns non-zero" ($rc3 -ne 0) "rc=$rc3"
Check "code untouched by malformed archive" (Test-Path (Join-Path $appDst $marker)) ""

# ---------------------------------------------------------------- 清理
Write-Host "`n=== 6. cleanup ===" -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $simPkg 'scripts\stop.ps1') -Quiet | Out-Null
Start-Sleep -Seconds 1
if ($srv -and -not $srv.HasExited) { & taskkill.exe /PID $srv.Id /T /F 2>&1 | Out-Null }
Start-Sleep -Seconds 1
# 进程句柄不是立刻释放的，删目录要重试（见 test_acceptance.ps1 同处注释）
for ($i = 1; $i -le 6; $i++) {
    Remove-Item -LiteralPath $simRoot -Recurse -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path $simRoot)) { break }
    Start-Sleep -Seconds 2
}
Check "sandbox removed" (-not (Test-Path $simRoot)) ""
Check "nothing left listening" ((Find-PortablePort) -eq 0) ""

Write-Host "`n=== RESULT ===" -ForegroundColor Cyan
if ($fail -eq 0) { Write-Host "  ALL PASSED" -ForegroundColor Green } else { Write-Host "  $fail CHECK(S) FAILED" -ForegroundColor Red }
exit $fail
