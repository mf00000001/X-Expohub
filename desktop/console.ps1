#requires -Version 5.1
<#
============================================================================
  ExpoHub 控制台
============================================================================
  一个常驻小窗口：实时显示前后端状态，提供 打开应用 / 重启 / 停止 / 看日志。
  用 PowerShell + WinForms 实现，不引入任何额外依赖。

  由 console.vbs 以隐藏控制台方式拉起（WinForms 窗口自带，不需要黑色命令行窗）。
============================================================================
#>
[CmdletBinding()]
param()

# $PSScriptRoot 在事件处理器/函数作用域里不一定可见，先固定成 script 变量再用
$script:ThisDir = $PSScriptRoot

. (Join-Path $script:ThisDir 'lib\common.ps1')

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# 为什么需要这段 P/Invoke：
# console.vbs 用 WScript.Shell.Run(cmd, 0, ...) 隐藏启动，0 = SW_HIDE 会写进进程的
# STARTUPINFO。Windows 会把这个"隐藏"状态套用到该进程创建的第一个顶层窗口上，
# 结果就是 WinForms 窗体被系统强制隐藏（进程活着、句柄为 0），ShowDialog 永远阻塞。
# 这里在窗体显示后显式 ShowWindow(SW_SHOW/SW_RESTORE)，把系统的默认行为覆盖掉。
Add-Type -Namespace ExpoHub -Name Win32 -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool SetForegroundWindow(System.IntPtr hWnd);
'@

$COLOR_OK    = [System.Drawing.Color]::FromArgb(22, 163, 74)    # green-600
$COLOR_DOWN  = [System.Drawing.Color]::FromArgb(220, 38, 38)    # red-600
$COLOR_MUTED = [System.Drawing.Color]::FromArgb(107, 114, 128)  # gray-500

# ------------------------------------------------------------------ 窗体
$form                 = New-Object System.Windows.Forms.Form
$form.Text            = 'ExpoHub 控制台'
$form.ClientSize      = New-Object System.Drawing.Size(452, 348)
$form.StartPosition   = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox     = $false
$form.Font            = New-Object System.Drawing.Font('Microsoft YaHei UI', 9)

$grpStatus           = New-Object System.Windows.Forms.GroupBox
$grpStatus.Text      = '服务状态'
$grpStatus.Location  = New-Object System.Drawing.Point(14, 10)
$grpStatus.Size      = New-Object System.Drawing.Size(424, 128)
$form.Controls.Add($grpStatus)

function New-RowLabel {
    # 宽度 130 是量出来的：'后端 FastAPI (8002)' 在 9pt 雅黑下需 117px，110 会截断
    param([string]$Text, [int]$Y, [int]$Width = 130, [System.Drawing.Font]$Font)
    $l           = New-Object System.Windows.Forms.Label
    $l.Text      = $Text
    $l.Location  = New-Object System.Drawing.Point(18, $Y)
    $l.Size      = New-Object System.Drawing.Size($Width, 22)
    if ($Font) { $l.Font = $Font }
    return $l
}

$lblBackendName  = New-RowLabel -Text '后端 FastAPI (8002)' -Y 28
$lblFrontendName = New-RowLabel -Text '前端 Vite (5173)'   -Y 56
$lblHintName     = New-RowLabel -Text '应用地址'            -Y 88

$script:lblBackendState  = New-Object System.Windows.Forms.Label
$script:lblBackendState.Location = New-Object System.Drawing.Point(180, 28)
$script:lblBackendState.Size     = New-Object System.Drawing.Size(230, 22)
$script:lblBackendState.Font     = New-Object System.Drawing.Font('Microsoft YaHei UI', 9, [System.Drawing.FontStyle]::Bold)

$script:lblFrontendState = New-Object System.Windows.Forms.Label
$script:lblFrontendState.Location = New-Object System.Drawing.Point(180, 56)
$script:lblFrontendState.Size     = New-Object System.Drawing.Size(230, 22)
$script:lblFrontendState.Font     = New-Object System.Drawing.Font('Microsoft YaHei UI', 9, [System.Drawing.FontStyle]::Bold)

$lblUrl           = New-Object System.Windows.Forms.Label
$lblUrl.Text      = $script:FrontendUrl
$lblUrl.Location  = New-Object System.Drawing.Point(180, 88)
$lblUrl.Size      = New-Object System.Drawing.Size(230, 22)
$lblUrl.ForeColor = $COLOR_MUTED

$grpStatus.Controls.AddRange(@($lblBackendName, $lblFrontendName, $lblHintName,
                               $script:lblBackendState, $script:lblFrontendState, $lblUrl))

# ------------------------------------------------------------------ 按钮
$grpActions          = New-Object System.Windows.Forms.GroupBox
$grpActions.Text     = '操作'
$grpActions.Location = New-Object System.Drawing.Point(14, 148)
$grpActions.Size     = New-Object System.Drawing.Size(424, 130)
$form.Controls.Add($grpActions)

function New-ActionButton {
    param([string]$Text, [int]$X, [int]$Y, [int]$W = 128)
    $b          = New-Object System.Windows.Forms.Button
    $b.Text     = $Text
    $b.Location = New-Object System.Drawing.Point($X, $Y)
    $b.Size     = New-Object System.Drawing.Size($W, 34)
    return $b
}

$btnOpen  = New-ActionButton -Text '打开应用'   -X 18  -Y 26
$btnStart = New-ActionButton -Text '启动服务'   -X 152 -Y 26
$btnStop  = New-ActionButton -Text '停止服务'   -X 286 -Y 26 -W 120
$btnLogs  = New-ActionButton -Text '打开日志目录' -X 18  -Y 76 -W 190
$btnAbout = New-ActionButton -Text '关于 / 帮助'  -X 216 -Y 76 -W 190

$grpActions.Controls.AddRange(@($btnOpen, $btnStart, $btnStop, $btnLogs, $btnAbout))

$lblFooter           = New-Object System.Windows.Forms.Label
$lblFooter.Location  = New-Object System.Drawing.Point(16, 290)
$lblFooter.Size      = New-Object System.Drawing.Size(428, 46)
$lblFooter.ForeColor = $COLOR_MUTED
# 文案按 428px 宽度收着写：原句 429px 会折行，多出的第 3 行超出标签高度被吃掉
$lblFooter.Text      = "改代码即时生效：前端 HMR 热更新，后端 --reload 自动重启。`r`n加载的是源码实时服务而非打包产物，所以无需重新打包。"
$form.Controls.Add($lblFooter)

# ------------------------------------------------------------------ 行为
function Update-ExpoStatus {
    $st = Get-ExpohubStatus

    if ($st.BackendUp) {
        $script:lblBackendState.Text      = "● 运行中   PID $($st.BackendPid)"
        $script:lblBackendState.ForeColor = $COLOR_OK
    } else {
        $script:lblBackendState.Text      = '○ 未运行'
        $script:lblBackendState.ForeColor = $COLOR_DOWN
    }

    if ($st.FrontendUp) {
        $script:lblFrontendState.Text      = "● 运行中   PID $($st.FrontendPid)"
        $script:lblFrontendState.ForeColor = $COLOR_OK
    } else {
        $script:lblFrontendState.Text      = '○ 未运行'
        $script:lblFrontendState.ForeColor = $COLOR_DOWN
    }

    $script:btnStop.Enabled  = ($st.BackendUp -or $st.FrontendUp)
    $script:btnStart.Enabled = -not ($st.BackendUp -and $st.FrontendUp)
}

function Invoke-StartScript {
    param([string[]]$ExtraArgs)
    # 独立进程跑，避免 UI 在最长 120 秒的健康检查期间卡死
    # 注意：变量不能叫 $args —— 那是 PowerShell 自动变量
    $psArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass',
                '-File', "`"$script:ThisDir\start.ps1`"", '-NoBrowser') + $ExtraArgs
    Start-Process -FilePath 'powershell.exe' -ArgumentList $psArgs -WindowStyle Hidden | Out-Null
}

$script:btnOpen  = $btnOpen
$script:btnStart = $btnStart
$script:btnStop  = $btnStop

$btnOpen.Add_Click({
    $st = Get-ExpohubStatus
    if ($st.BackendUp -and $st.FrontendUp) {
        try { Open-AppWindow | Out-Null } catch { Write-Log "打开窗口失败：$($_.Exception.Message)" 'WARN' }
    } else {
        # 服务没起齐 → 交给 start.ps1 走完整流程（它自己会开窗）
        Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', "`"$script:ThisDir\start.ps1`"") -WindowStyle Hidden | Out-Null
    }
})

$btnStart.Add_Click({ Invoke-StartScript -ExtraArgs @() })
$btnStop.Add_Click({
    Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', "`"$script:ThisDir\stop.ps1`"", '-Quiet') -WindowStyle Hidden | Out-Null
})

$btnLogs.Add_Click({
    if (-not (Test-Path $script:LogDir)) { New-Item -ItemType Directory -Force $script:LogDir | Out-Null }
    Start-Process explorer.exe $script:LogDir | Out-Null
})

$btnAbout.Add_Click({
    $txt = @"
ExpoHub 桌面启动器

应用地址
  $($script:FrontendUrl)      ← 前端（Vite dev server）
  $($script:BackendUrl)/docs  ← 后端 API 文档

热更新原理
  前端：Vite HMR，改 .vue/.ts 保存即生效
  后端：uvicorn --reload，改 .py 保存自动重启
  加载的是源码实时服务，不是打包产物 —— 所以不用重新打包。

日志
  $($script:LogDir)

手动启停
  powershell -ExecutionPolicy Bypass -File "$($script:DesktopDir)\start.ps1" -Restart
  powershell -ExecutionPolicy Bypass -File "$($script:DesktopDir)\stop.ps1"
"@
    [System.Windows.Forms.MessageBox]::Show($txt, '关于 ExpoHub',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
})

# ------------------------------------------------------------------ 启动
$timer          = New-Object System.Windows.Forms.Timer
$timer.Interval = 3000
$timer.Add_Tick({ try { Update-ExpoStatus } catch { } })
$timer.Start()

function Show-FormForcibly {
    <# 覆盖 STARTUPINFO 的隐藏状态：SW_SHOW(5) 让它出现，SW_RESTORE(9) 解除最小化/隐藏 #>
    try {
        $h = $form.Handle
        if ($h -ne [IntPtr]::Zero) {
            [void][ExpoHub.Win32]::ShowWindow($h, 5)
            [void][ExpoHub.Win32]::ShowWindow($h, 9)
            [void][ExpoHub.Win32]::SetForegroundWindow($h)
        }
    } catch {
        Write-Log "强制显示窗口失败：$($_.Exception.Message)" 'WARN'
    }
}

$form.Add_Shown({
    try { Update-ExpoStatus } catch { }
    Show-FormForcibly
})

# 一次性补刀：某些时序下 Shown 里的 ShowWindow 会被系统的默认显示再盖回去
$showTimer          = New-Object System.Windows.Forms.Timer
$showTimer.Interval = 450
$showTimer.Add_Tick({
    $showTimer.Stop()
    Show-FormForcibly
})
$showTimer.Start()

Write-Log '控制台已打开' 'INFO'
[void]$form.ShowDialog()
$timer.Stop()
Write-Log '控制台已关闭' 'INFO'
