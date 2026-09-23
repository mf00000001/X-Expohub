#requires -Version 5.1
<#
============================================================================
  ExpoHub — 在桌面创建快捷方式（幂等，可重复运行）
============================================================================
  默认创建两个图标：
    ExpoHub.lnk         双击 = 启动服务 + 打开应用窗口
    ExpoHub 控制台.lnk   状态面板，含 启动/停止/看日志

  加 -IncludeStop 再补一个 "ExpoHub 停止.lnk"。

  用法：powershell -ExecutionPolicy Bypass -File desktop\install-shortcuts.ps1
============================================================================
#>
[CmdletBinding()]
param(
    [switch]$IncludeStop,
    # 指定目标桌面目录（默认取系统桌面，用于测试可覆盖）
    [string]$DesktopPath
)

$ErrorActionPreference = 'Stop'

$here       = $PSScriptRoot
$iconPath   = Join-Path $here 'assets\expohub.ico'
$wscript    = Join-Path $env:SystemRoot 'System32\wscript.exe'

if (-not $DesktopPath) {
    $DesktopPath = [Environment]::GetFolderPath('Desktop')
}

# --- 前置校验：缺什么直接说，别静默产出一个坏快捷方式 ---
$problems = @()
if (-not (Test-Path $wscript))  { $problems += "找不到 wscript.exe：$wscript" }
if (-not (Test-Path $iconPath)) { $problems += "找不到图标：$iconPath`n  → 先运行 python assets\make_icon.py" }
foreach ($v in @('start.vbs', 'console.vbs', 'stop.vbs')) {
    if (-not (Test-Path (Join-Path $here $v))) { $problems += "找不到 $v" }
}
if (-not (Test-Path $DesktopPath)) { $problems += "桌面目录不存在：$DesktopPath" }

if ($problems.Count -gt 0) {
    Write-Host '创建快捷方式失败：' -ForegroundColor Red
    $problems | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}

$shell = New-Object -ComObject WScript.Shell

function New-Shortcut {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Script,
        [Parameter(Mandatory)][string]$Description
    )
    $linkPath    = Join-Path $DesktopPath $Name
    $targetVbs   = Join-Path $here $Script

    $lnk = $shell.CreateShortcut($linkPath)
    # 显式指向 wscript.exe：不依赖 .vbs 的文件关联（关联被改成编辑器时会失效）
    $lnk.TargetPath       = $wscript
    $lnk.Arguments        = "`"$targetVbs`""
    $lnk.WorkingDirectory = $here
    $lnk.IconLocation     = $iconPath
    $lnk.Description      = $Description
    $lnk.Save()

    if (Test-Path $linkPath) {
        Write-Host "  OK  $Name" -ForegroundColor Green
        return $true
    }
    Write-Host "  失败 $Name" -ForegroundColor Red
    return $false
}

Write-Host ""
Write-Host "在桌面创建 ExpoHub 快捷方式：$DesktopPath" -ForegroundColor Cyan
Write-Host ""

$ok = $true
$ok = (New-Shortcut -Name 'ExpoHub.lnk'         -Script 'start.vbs'   -Description '启动 ExpoHub（自动拉起前后端并打开应用窗口）') -and $ok
$ok = (New-Shortcut -Name 'ExpoHub 控制台.lnk'   -Script 'console.vbs' -Description 'ExpoHub 状态控制台') -and $ok
if ($IncludeStop) {
    $ok = (New-Shortcut -Name 'ExpoHub 停止.lnk' -Script 'stop.vbs'    -Description '停止 ExpoHub 前后端服务') -and $ok
}

Write-Host ""
if ($ok) {
    Write-Host "完成。双击桌面上的 “ExpoHub” 即可启动（首次约 10-20 秒）。" -ForegroundColor Green
} else {
    Write-Host "部分快捷方式创建失败，见上方输出。" -ForegroundColor Yellow
    exit 1
}
