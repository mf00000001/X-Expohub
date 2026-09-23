<#
.SYNOPSIS
    停止 ExpoHub 便携版服务。

.DESCRIPTION
    两条路都走，确保停干净：
      1. 按 logs\server.pid 记录的进程号停（正常路径）
      2. PID 文件丢了或过期时，反查端口上真正在监听的进程（兜底路径）

    必须杀**进程树**：uvicorn 是"父进程持 socket + 子进程跑应用"的结构，
    只杀父进程会留下孤儿进程继续占着端口。

.PARAMETER Quiet
    静默模式，只写日志不弹窗（供 start.ps1 -Restart 与更新脚本调用）。

.NOTES
    本文件必须存为 UTF-8 with BOM（原因见 start.ps1 的注释）。
    性能约束见 Get-Listening / Test-PortFree 的注释。
#>
[CmdletBinding()]
param([switch]$Quiet)

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$PkgRoot = Split-Path -Parent $PSScriptRoot
$LogDir  = Join-Path $PkgRoot 'logs'
$LogFile = Join-Path $LogDir  'launcher.log'
$PidFile = Join-Path $LogDir  'server.pid'
$PortRange = 8002..8010

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "{0} [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    try { Add-Content -Path $LogFile -Value $line -Encoding UTF8 } catch { }
    if (-not $Quiet) { Write-Host "  $Message" }
}

function Get-Listening {
    # 一次性取回所有监听项。
    # ⚠️ 不要改成逐个端口 Get-NetTCPConnection —— 单次约 1.3 秒，
    #    探 9 个端口就是十几秒，用户点"停止"会以为卡死了。
    return @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue)
}

function Test-PortFree {
    param([int]$Port)
    # 独占绑定探测，毫秒级。必须绑 0.0.0.0 且开 ExclusiveAddressUse：
    # Windows 允许 0.0.0.0:P 与 127.0.0.1:P 叠加绑定，绑回环地址会误判为"空闲"。
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

function Test-IsOurInstance {
    param([int]$Port)
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/health" `
                               -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -ne 200) { return $false }
        return (($r.Content | ConvertFrom-Json).mode -eq 'portable')
    } catch { return $false }
}

function Stop-Tree {
    param([int]$TargetPid, [string]$Why)
    try {
        & taskkill.exe /PID $TargetPid /T /F 2>&1 | Out-Null
        Write-Log "已停止进程 $TargetPid（$Why）"
        return $true
    } catch {
        Write-Log "停止进程 $TargetPid 失败：$($_.Exception.Message)" 'WARN'
        return $false
    }
}

if (-not $Quiet) {
    Write-Host ''
    Write-Host '  正在停止 ExpoHub 服务…' -ForegroundColor Yellow
    Write-Host ''
}

# ---- 路径 1：PID 文件 ----
if (Test-Path $PidFile) {
    $raw = Get-Content $PidFile -Raw -ErrorAction SilentlyContinue
    $savedPid = 0
    if ([int]::TryParse((($raw -split '\s+')[0]), [ref]$savedPid) -and $savedPid -gt 0) {
        if (Get-Process -Id $savedPid -ErrorAction SilentlyContinue) {
            Stop-Tree -TargetPid $savedPid -Why '来自 server.pid' | Out-Null
        } else {
            Write-Log "server.pid 中的进程 $savedPid 已不存在（可能被手动关闭）" 'WARN'
        }
    }
    Remove-Item -Force $PidFile -ErrorAction SilentlyContinue
} else {
    Write-Log '未找到 server.pid，改用端口反查' 'WARN'
}

# ---- 路径 2：端口反查（兜底）----
$listening = Get-Listening
foreach ($port in $PortRange) {
    foreach ($conn in ($listening | Where-Object { $_.LocalPort -eq $port })) {
        if ($conn.OwningProcess -and $conn.OwningProcess -gt 0) {
            # 只对我们自己的实例动手：别的程序占了端口范围里的某个端口，
            # 不能替用户把它杀掉。
            if (Test-IsOurInstance $port) {
                Stop-Tree -TargetPid $conn.OwningProcess -Why "监听端口 $port 的便携版实例" | Out-Null
            }
        }
    }
}

Start-Sleep -Seconds 1

# ---- 复核：只认"我们的实例还在不在"，不管别的程序占不占端口 ----
$listening = Get-Listening
$still = @()
foreach ($port in $PortRange) {
    if (($listening | Where-Object { $_.LocalPort -eq $port }) -and (Test-IsOurInstance $port)) {
        $still += $port
    }
}

if ($still.Count -eq 0) {
    Write-Log '✓ 服务已停止，端口已释放'
    if (-not $Quiet) {
        Write-Host ''
        Write-Host '  ✅ 已停止' -ForegroundColor Green
        Write-Host '  （本窗口 3 秒后自动关闭）' -ForegroundColor DarkGray
        Start-Sleep -Seconds 3
    }
    exit 0
} else {
    Write-Log "端口 $($still -join ', ') 上仍有 ExpoHub 实例在响应，未能完全停止" 'ERROR'
    if (-not $Quiet) {
        try {
            Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
            [System.Windows.Forms.MessageBox]::Show(
                "服务未能完全停止，端口 $($still -join ', ') 仍在响应。`n`n请打开任务管理器结束 python.exe 后重试。",
                'ExpoHub 停止失败', 'OK', 'Warning') | Out-Null
        } catch {
            Write-Host "  停止失败：端口 $($still -join ', ') 仍在响应" -ForegroundColor Red
        }
    }
    exit 1
}
