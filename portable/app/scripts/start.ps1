<#
.SYNOPSIS
    ExpoHub 便携版启动器。

.DESCRIPTION
    零安装启动：拉起包内自带的 Python 运行时 + 后端（同源托管前端页面），
    健康检查通过后再打开一个无地址栏的应用窗口。

    启动器窗口关掉不影响服务——服务是独立进程。

.PARAMETER NoBrowser
    只启动服务，不打开窗口（排障用）。

.PARAMETER Restart
    先停掉正在运行的实例，再重新启动。

.NOTES
    改本文件前请先读这几条（都是踩过的坑）：

    1. 本文件必须存为 **UTF-8 with BOM**。PowerShell 5.1 默认按 ANSI 读脚本，
       没有 BOM 时下面的中文会全部变成乱码，领导看到的就是一串问号。
    2. 所有路径一律从 $PSScriptRoot 推导，绝不依赖当前工作目录——
       用户可能从任何位置（甚至是快捷方式）双击启动。
    3. 健康检查走 HTTP 而不是"端口通不通"。uvicorn 先 bind socket 再跑 startup，
       端口开了不等于应用真的能用。
    4. 端口探测只认 /api/health 返回 200 的实例。开发用的后端没有这个端点，
       因此不会误把开发服务当成便携版实例。
#>
[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$Restart,
    [switch]$NoDialog      # 不弹窗，失败信息只写控制台（自动化测试用）
)

$ErrorActionPreference = 'Stop'

# 控制台按 UTF-8 输出，否则中文进度提示会乱码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# ---------------------------------------------------------------- 路径（全绝对）
$PkgRoot  = Split-Path -Parent $PSScriptRoot          # scripts\ 的上一级 = 包根
$Runtime  = Join-Path $PkgRoot  'runtime'
$Python   = Join-Path $Runtime  'python.exe'
$Server   = Join-Path $PkgRoot  'server'
$WebDir   = Join-Path $Server   'web'
$DbPath   = Join-Path $Server   'expohub.db'
$LogDir   = Join-Path $PkgRoot  'logs'
$LogFile  = Join-Path $LogDir   'launcher.log'
$OutLog   = Join-Path $LogDir   'server.out.log'
$ErrLog   = Join-Path $LogDir   'server.err.log'
$PidFile  = Join-Path $LogDir   'server.pid'

$PortRange    = 8002..8010      # 被占用时依次退让
$HealthWaitSec = 90             # 首启动要编译 .pyc，给足时间

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# ---------------------------------------------------------------- 小工具
function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "{0} [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    try {
        if ((Test-Path $LogFile) -and (Get-Item $LogFile).Length -gt 1MB) {
            Move-Item -Force $LogFile "$LogFile.1"
        }
        Add-Content -Path $LogFile -Value $line -Encoding UTF8
    } catch { }
    Write-Host "  $Message"
}

function Show-Failure {
    # 失败时弹窗，并把日志末尾附上——比让窗口一闪而过有用得多。
    param([string]$Reason, [string]$Detail)
    $tail = ''
    foreach ($f in @($ErrLog, $OutLog)) {
        if (Test-Path $f) {
            $t = (Get-Content $f -Tail 15 -Encoding UTF8 -ErrorAction SilentlyContinue) -join "`n"
            if ($t) { $tail += "`n--- $(Split-Path -Leaf $f) ---`n$t" }
        }
    }
    $msg = "$Reason`n`n日志目录：`n$LogDir`n$tail"
    if ($NoDialog) { Write-Host "`n[失败] $msg" -ForegroundColor Red; return }
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        [System.Windows.Forms.MessageBox]::Show(
            $msg, 'ExpoHub 启动失败', 'OK', 'Error') | Out-Null
    } catch {
        Write-Host "`n$msg" -ForegroundColor Red
    }
}

function Test-Health {
    param([int]$Port)
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/health" `
                               -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

function Test-PortFree {
    param([int]$Port)

    # 只做一件事：尝试**独占绑定** 0.0.0.0:$Port。几毫秒，快且准。
    #
    # ⚠️ 两条不能改的约束（都是实测踩出来的）：
    #
    # 1. 必须绑 0.0.0.0，不能绑 127.0.0.1。
    #    Windows 允许在 0.0.0.0:P 已被占用时，再绑一个更具体的 127.0.0.1:P，
    #    绑 127.0.0.1 会假阳性地报告"端口空闲"→ 启动器挑中被占端口 →
    #    Python 绑不上 → 服务起不来。
    #
    # 2. **不要**再加"逐个端口调 Get-NetTCPConnection 二次校验"这种保险。
    #    那个 cmdlet 单次约 1.3 秒，探 9 个端口会让启动白等 12 秒，
    #    而独占绑定这一步已经把该判断的都判断了。
    $listener = $null
    try {
        $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, $Port)
        $listener.ExclusiveAddressUse = $true
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) { try { $listener.Stop() } catch { } }
    }
}

function Get-RunningPort {
    # 返回已在运行的便携版实例端口；没有则返回 0。
    #
    # 先用 bind 探测（毫秒级）排除空闲端口，只对"确实被监听"的端口发 HTTP。
    # 反过来做会很难受：空的端口要等连接超时，9 个端口能让启动白等十几秒。
    foreach ($p in $PortRange) {
        if (Test-PortFree $p) { continue }
        if (Test-Health $p) { return $p }
    }
    return 0
}

function Open-AppWindow {
    param([int]$Port, [string]$Url)
    if ($NoBrowser) { Write-Log "已指定 -NoBrowser，跳过打开窗口"; return }
    $edge = @(
        (Join-Path $env:ProgramFiles       'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $env:LOCALAPPDATA       'Microsoft\Edge\Application\msedge.exe')
    ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

    if ($edge) {
        # --app：无地址栏、无标签页，看起来就是个原生软件
        Start-Process -FilePath $edge -ArgumentList "--app=$Url", '--window-size=1500,950'
        Write-Log "已用 Edge 应用窗口打开：$Url"
    } else {
        Start-Process $Url
        Write-Log "未找到 Edge，已回退默认浏览器打开：$Url" 'WARN'
    }
}

# ---------------------------------------------------------------- 前置校验
Write-Host ''
Write-Host '  ╔══════════════════════════════════════════╗' -ForegroundColor Cyan
Write-Host '  ║        ExpoHub 展会撮合平台 · 试用版      ║' -ForegroundColor Cyan
Write-Host '  ╚══════════════════════════════════════════╝' -ForegroundColor Cyan
Write-Host ''

Write-Log '正在检查运行环境…'

foreach ($required in @($Python, $Server, $DbPath, $WebDir)) {
    if (-not (Test-Path $required)) {
        Write-Log "缺少必要文件：$required" 'ERROR'
        Show-Failure "安装包不完整，缺少：`n$required" ''
        exit 1
    }
}
if (-not (Test-Path (Join-Path $WebDir 'index.html'))) {
    Write-Log "前端页面缺失：$WebDir\index.html" 'ERROR'
    Show-Failure "安装包不完整，缺少前端页面。`n请重新解压，注意不要只解压部分文件。" ''
    exit 1
}
Write-Log '✓ 运行环境完整'

# ---------------------------------------------------------------- 已在运行？
if ($Restart) {
    Write-Log '检测到 -Restart，先停止已有实例…'
    $running = Get-RunningPort
    if ($running) {
        & (Join-Path $PSScriptRoot 'stop.ps1') -Quiet
        Start-Sleep -Seconds 2
    }
}

$existing = Get-RunningPort
if ($existing) {
    Write-Log "✓ 服务已在运行（端口 $existing），直接打开窗口"  'INFO'
    Open-AppWindow -Port $existing -Url "http://127.0.0.1:$existing"
    Write-Host ''
    Write-Host '  启动完成！应用窗口正在打开…' -ForegroundColor Green
    Start-Sleep -Seconds 2
    exit 0
}

# ---------------------------------------------------------------- 选端口
$Port = 0
foreach ($p in $PortRange) {
    if (Test-PortFree $p) { $Port = $p; break }
}
if ($Port -eq 0) {
    Write-Log "端口 $($PortRange[0])–$($PortRange[-1]) 全部被占用" 'ERROR'
    Show-Failure "端口全部被占用，无法启动。" '请先关闭占用端口的程序后重试。'
    exit 1
}
if ($Port -ne $PortRange[0]) {
    Write-Log "端口 $($PortRange[0]) 被占用，改用 $Port" 'WARN'
}

# ---------------------------------------------------------------- 拉起服务
# 子进程继承当前环境变量，因此这里设置即可
$env:DATABASE_URL     = "sqlite:///$($DbPath -replace '\\','/')"
$env:FRONTEND_DIR     = $WebDir
$env:CONSOLE_LOG_PATH = (Join-Path $LogDir 'console_log.jsonl')
$env:HOST             = '127.0.0.1'
$env:PORT             = "$Port"
$env:PYTHONUTF8       = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '0'

Write-Log "正在启动服务（端口 $Port）…"
try {
    $proc = Start-Process -FilePath $Python `
        -ArgumentList 'portable_main.py' `
        -WorkingDirectory $Server `
        -WindowStyle Hidden `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError  $ErrLog `
        -PassThru -ErrorAction Stop
} catch {
    Write-Log "无法启动 Python 进程：$($_.Exception.Message)" 'ERROR'
    Show-Failure "无法启动服务进程。`n$($_.Exception.Message)" ''
    exit 1
}
Set-Content -Path $PidFile -Value "$($proc.Id) $Port" -Encoding ASCII

# ---------------------------------------------------------------- 等健康检查
Write-Host ''
Write-Host '  正在启动服务，请稍候…' -ForegroundColor Yellow
$ready = $false
for ($i = 1; $i -le $HealthWaitSec; $i++) {
    if (Test-Health $Port) { $ready = $true; break }
    if ($proc.HasExited) {
        Write-Log "服务进程提前退出（退出码 $($proc.ExitCode)）" 'ERROR'
        Show-Failure "服务启动失败，进程已退出（退出码 $($proc.ExitCode)）。" ''
        exit 1
    }
    Write-Host '.' -NoNewline -ForegroundColor DarkGray
    Start-Sleep -Seconds 1
}
Write-Host ''

if (-not $ready) {
    Write-Log "等待 $HealthWaitSec 秒后服务仍未就绪" 'ERROR'
    Show-Failure "服务在 $HealthWaitSec 秒内没有就绪。" '可尝试关闭杀毒软件后重试，或把 logs 目录发给技术人员。'
    exit 1
}

Write-Log "✓ 服务就绪（http://127.0.0.1:$Port）"

# ---------------------------------------------------------------- 打开窗口
Open-AppWindow -Port $Port -Url "http://127.0.0.1:$Port"

Write-Host ''
Write-Host '  ✅ 启动完成！应用窗口正在打开…' -ForegroundColor Green
Write-Host "     如果窗口没有自动出现，请手动打开浏览器访问：" -ForegroundColor Gray
Write-Host "     http://127.0.0.1:$Port" -ForegroundColor Gray
Write-Host ''
Write-Host '  （本窗口可以关闭，不影响使用）' -ForegroundColor DarkGray
Write-Log '启动流程完成'
Start-Sleep -Seconds 2
exit 0
