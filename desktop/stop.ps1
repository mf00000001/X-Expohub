#requires -Version 5.1
<#
============================================================================
  ExpoHub 桌面启动器 — 停止服务
============================================================================
  停掉后端(8002)与前端(5173)。
  注意：会连带杀掉进程树（uvicorn --reload 有父子进程），确保端口真正释放。
  数据库(expohub.db)是磁盘文件，停止服务不会丢数据。
============================================================================
#>
[CmdletBinding()]
param(
    # 不弹提示框（给脚本调用）
    [switch]$Quiet
)

. (Join-Path $PSScriptRoot 'lib\common.ps1')

Write-Log '──────────── ExpoHub 停止 ────────────' 'INFO'

$before = Get-ExpohubStatus
$stoppedAnything = $false

if ($before.BackendUp -or (Test-PortOpen $script:BackendPort)) {
    if (Stop-ServiceOnPort -Port $script:BackendPort -Label '后端') { $stoppedAnything = $true }
}
if ($before.FrontendUp -or (Test-PortOpen $script:FrontendPort)) {
    if (Stop-ServiceOnPort -Port $script:FrontendPort -Label '前端') { $stoppedAnything = $true }
}

$after = Get-ExpohubStatus
$stillRunning = $after.BackendUp -or $after.FrontendUp

if ($stillRunning) {
    $msg = "部分服务未能停止：`r`n" +
           "  后端：$(if ($after.BackendUp) { '仍在运行' } else { '已停止' })`r`n" +
           "  前端：$(if ($after.FrontendUp) { '仍在运行' } else { '已停止' })`r`n`r`n" +
           "可手动处理：taskkill /PID <PID> /T /F（PID 见 logs\launcher.log）"
    Write-Log $msg 'WARN'
    if (-not $Quiet) { Show-MessageBox -Title 'ExpoHub' -Message $msg -Kind 'Warning' }
} else {
    if ($stoppedAnything) {
        $msg = "ExpoHub 已停止。`r`n`r`n后端 (8002) 与前端 (5173) 均已关闭，端口已释放。"
    } else {
        $msg = "ExpoHub 本来就未在运行。"
    }
    Write-Log $msg 'OK'
    if (-not $Quiet) { Show-InfoBox -Title 'ExpoHub' -Message $msg }
}

Write-Log '──────────── 停止流程结束 ────────────' 'INFO'
