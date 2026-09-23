<#
.SYNOPSIS
    从配置的更新源下载最新后端代码并替换。

.DESCRIPTION
    只替换 server\app（后端代码）。前端 server\web 是 Vite 编译产物，
    更新它需要 Node 环境，因此本脚本不动它——改前端要重新出一份试用包。

    流程：读配置 → 停服务 → 备份 → 下载解压 → 替换 → 重启
    任何一步失败都从备份回滚。

.NOTES
    1. 本文件必须存为 UTF-8 with BOM（原因见 start.ps1 的注释）。
    2. PowerShell 5.1 的 Invoke-WebRequest 默认走 TLS 1.0，
       现代站点会直接拒绝，必须先强制 TLS 1.2。
#>
[CmdletBinding()]
param(
    [switch]$NoDialog,   # 不弹窗，信息只写控制台（自动化测试用）
    [switch]$NoBrowser,  # 更新完不自动开窗（静默更新）
    [string]$SourceUrl   # 覆盖 update-source.txt 里的地址（测试用）
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# PowerShell 5.1 默认 TLS 1.0 —— 不设这行，下载会以"基础连接已关闭"失败
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$PkgRoot     = Split-Path -Parent $PSScriptRoot
$ServerDir   = Join-Path $PkgRoot 'server'
$AppDir      = Join-Path $ServerDir 'app'
$SourceFile  = Join-Path $PSScriptRoot 'update-source.txt'
$LogDir      = Join-Path $PkgRoot 'logs'
$LogFile     = Join-Path $LogDir 'launcher.log'
$WorkDir     = Join-Path $env:TEMP ("expohub-update-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "{0} [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    try { Add-Content -Path $LogFile -Value $line -Encoding UTF8 } catch { }
    Write-Host "  $Message"
}

function Show-Info {
    param([string]$Message, [string]$Title = 'ExpoHub 检查更新', [string]$Icon = 'Information')
    if ($NoDialog) { Write-Host "`n$Message"; return }
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        [System.Windows.Forms.MessageBox]::Show($Message, $Title, 'OK', $Icon) | Out-Null
    } catch { Write-Host "`n$Message" }
}

function Restart-Service {
    # 更新流程会先停服务再下载。任何一步失败都必须把服务恢复起来，
    # 否则用户面对的是一个**打不开的程序**，而错误提示里完全没提这件事。
    Write-Log '正在恢复服务…'
    try {
        & (Join-Path $PSScriptRoot 'start.ps1') -NoDialog:$NoDialog -NoBrowser:$NoBrowser
    } catch {
        Write-Log "服务恢复失败，请手动双击「双击启动.bat」：$($_.Exception.Message)" 'WARN'
    }
}

Write-Host ''
Write-Host '  ExpoHub 检查更新' -ForegroundColor Cyan
Write-Host ''

# ---------------------------------------------------------------- 读配置
# -SourceUrl 优先（测试与高级用法），其次读配置文件
if ($SourceUrl) {
    $url = $SourceUrl.Trim()
    Write-Log '更新源由命令行指定，覆盖配置文件'
} elseif (Test-Path $SourceFile) {
    $url = (Get-Content $SourceFile -Encoding UTF8 |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ -and -not $_.StartsWith('#') } |
            Select-Object -First 1)
} else {
    Write-Log '未找到 scripts\update-source.txt' 'ERROR'
    Show-Info "找不到配置文件：`n$SourceFile" 'ExpoHub 检查更新' 'Warning'
    exit 1
}

if (-not $url) {
    Write-Log '更新源未配置（update-source.txt 里没有有效地址）' 'WARN'
    Show-Info @"
本试用包尚未配置在线更新源。

这不影响正常使用——你仍然可以双击「双击启动.bat」启动。

如果需要在线更新，请让开发者把代码压缩包地址填进：
  scripts\update-source.txt
"@
    exit 0
}

Write-Log "更新源：$url"

# ---------------------------------------------------------------- 停服务
Write-Log '正在停止服务…'
try {
    & (Join-Path $PSScriptRoot 'stop.ps1') -Quiet
} catch {
    Write-Log "停止服务时出错（继续尝试更新）：$($_.Exception.Message)" 'WARN'
}

# ---------------------------------------------------------------- 下载
try {
    New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
    $zip = Join-Path $WorkDir 'update.zip'
    Write-Log '正在下载最新代码…'
    Invoke-WebRequest -Uri $url -OutFile $zip -TimeoutSec 120 -UseBasicParsing
    Write-Log ("下载完成（{0:N2} MB）" -f ((Get-Item $zip).Length / 1MB))

    Write-Log '正在解压…'
    $extractDir = Join-Path $WorkDir 'src'
    Expand-Archive -Path $zip -DestinationPath $extractDir -Force
} catch {
    Write-Log "下载或解压失败：$($_.Exception.Message)" 'ERROR'
    Remove-Item -Recurse -Force $WorkDir -ErrorAction SilentlyContinue
    Restart-Service
    Show-Info "更新失败：下载或解压出错。`n`n$($_.Exception.Message)`n`n程序已恢复到更新前的版本，可以继续使用。`n请检查网络后重试，或联系开发者。" 'ExpoHub 更新失败' 'Error'
    exit 1
}

# ---------------------------------------------------------------- 定位新代码
# 压缩包解压后形如 <repo>-<branch>\expohub-backend\app\...
$newApp = Get-ChildItem -Path $extractDir -Recurse -Directory -Filter 'app' -ErrorAction SilentlyContinue |
          Where-Object { $_.Parent -and $_.Parent.Name -eq 'expohub-backend' } |
          Select-Object -First 1

if (-not $newApp) {
    Write-Log '压缩包里没找到 expohub-backend\app' 'ERROR'
    Remove-Item -Recurse -Force $WorkDir -ErrorAction SilentlyContinue
    Restart-Service
    Show-Info "更新包结构不对：里面没有找到 expohub-backend\app 目录。`n`n程序仍是更新前的版本，可以继续使用。`n请确认更新源地址指向的是本项目的代码压缩包。" 'ExpoHub 更新失败' 'Error'
    exit 1
}
Write-Log "找到新代码：$($newApp.FullName)"

# ---------------------------------------------------------------- 备份 + 替换
$backup = Join-Path $ServerDir ("app.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$replaced = $false
try {
    Write-Log "正在备份当前代码到 $(Split-Path -Leaf $backup)"
    Copy-Item -Path $AppDir -Destination $backup -Recurse -Force

    Write-Log '正在替换后端代码…'
    Remove-Item -Path $AppDir -Recurse -Force
    Copy-Item -Path $newApp.FullName -Destination $AppDir -Recurse -Force
    $replaced = $true
    Write-Log '✓ 代码已更新'
} catch {
    Write-Log "替换失败：$($_.Exception.Message)" 'ERROR'
    if ($replaced) {
        Write-Log '正在回滚…' 'WARN'
        Remove-Item -Path $AppDir -Recurse -Force -ErrorAction SilentlyContinue
        Copy-Item -Path $backup -Destination $AppDir -Recurse -Force
        Write-Log '已回滚到更新前状态' 'WARN'
    }
    Remove-Item -Recurse -Force $WorkDir -ErrorAction SilentlyContinue
    Restart-Service
    Show-Info "更新失败，已回滚到原来的版本。`n`n$($_.Exception.Message)`n`n程序可以继续使用。" 'ExpoHub 更新失败' 'Error'
    exit 1
}

Remove-Item -Recurse -Force $WorkDir -ErrorAction SilentlyContinue

# ---------------------------------------------------------------- 重启
Write-Log '正在重新启动服务…'
try {
    & (Join-Path $PSScriptRoot 'start.ps1') -NoDialog:$NoDialog -NoBrowser:$NoBrowser
} catch {
    Write-Log "重启失败：$($_.Exception.Message)" 'ERROR'
    Show-Info "代码已更新成功，但自动重启失败。`n`n请手动双击「双击启动.bat」。`n`n如需回退，备份在：`n$backup" 'ExpoHub 更新' 'Warning'
    exit 1
}

Show-Info "更新完成，服务已重新启动。`n`n如需回退到更新前的版本，把下面这个目录覆盖回 server\app 即可：`n$backup" 'ExpoHub 更新完成'
exit 0
