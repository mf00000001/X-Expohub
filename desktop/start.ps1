#requires -Version 5.1
<#
============================================================================
  ExpoHub 桌面启动器
============================================================================
  做什么：拉起后端(FastAPI, 8002) + 前端(Vite, 5173)，两者健康检查通过后，
          用 Edge --app 模式打开一个无地址栏的独立窗口。

  为什么这样设计（"热更新"怎么来的）：
    前端跑 Vite dev server → HMR，改 .vue/.ts 保存即生效，无需刷新；
    后端跑 uvicorn --reload → 改 .py 保存自动重启。
    这里加载的是**源码实时服务**而非打包产物，所以代码一改，桌面上的
    应用立刻就是最新的——不需要重新打包。

  幂等：服务已在运行则直接复用并开窗，重复双击不会起第二套。

  手动调试：powershell -ExecutionPolicy Bypass -File desktop\start.ps1
============================================================================
#>
[CmdletBinding()]
param(
    # 强制重启：先停掉现有前后端再拉起
    [switch]$Restart,
    # 只起服务，不开浏览器窗口
    [switch]$NoBrowser,
    # 静默：出错也不弹窗（给脚本/计划任务用）
    [switch]$Quiet,
    # 健康检查总超时（秒）
    [int]$TimeoutSeconds = 120
)

. (Join-Path $PSScriptRoot 'lib\common.ps1')

$exitCode = 0

function Get-LogTail {
    param([string]$Path, [int]$Lines = 14)
    if (-not (Test-Path $Path)) { return '(该日志文件不存在)' }
    try { return ((Get-Content $Path -Tail $Lines -ErrorAction Stop) -join "`r`n") }
    catch { return '(读取日志失败)' }
}

function Start-BackendService {
    $outLog = Join-Path $script:LogDir 'backend.out.log'
    $errLog = Join-Path $script:LogDir 'backend.err.log'
    foreach ($f in @($outLog, $errLog)) {
        if (Test-Path $f) { Remove-Item $f -Force -ErrorAction SilentlyContinue }
    }
    # uvicorn 的日志走 stderr；stdout 留给应用自己的 print
    $pyArgs = @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0',
                '--port', "$script:BackendPort", '--reload')

    Write-Log "启动后端：$script:PythonExe $($pyArgs -join ' ')" 'INFO'
    $p = Start-Process -FilePath $script:PythonExe -ArgumentList $pyArgs `
                       -WorkingDirectory $script:BackendDir -WindowStyle Hidden `
                       -RedirectStandardOutput $outLog -RedirectStandardError $errLog `
                       -PassThru -ErrorAction Stop
    Write-Log "后端进程已派生 PID $($p.Id)（日志：logs\backend.err.log）" 'INFO'
    return $p.Id
}

function Start-FrontendService {
    $outLog = Join-Path $script:LogDir 'frontend.out.log'
    $errLog = Join-Path $script:LogDir 'frontend.err.log'
    foreach ($f in @($outLog, $errLog)) {
        if (Test-Path $f) { Remove-Item $f -Force -ErrorAction SilentlyContinue }
    }
    # 直接跑 vite.js，不经 npx / .cmd 包装：中间环节最少，失败点最少
    $nodeArgs = @("`"$script:ViteJs`"", '--host', '0.0.0.0', '--port', "$script:FrontendPort")

    Write-Log "启动前端：node $($nodeArgs -join ' ')" 'INFO'
    $p = Start-Process -FilePath 'node' -ArgumentList $nodeArgs `
                       -WorkingDirectory $script:FrontendDir -WindowStyle Hidden `
                       -RedirectStandardOutput $outLog -RedirectStandardError $errLog `
                       -PassThru -ErrorAction Stop
    Write-Log "前端进程已派生 PID $($p.Id)（日志：logs\frontend.out.log）" 'INFO'
    return $p.Id
}

# ============================================================================
#  主流程
# ============================================================================
Write-Log '──────────── ExpoHub 启动 ────────────' 'INFO'

# --- 0. 前置校验（缺什么先说清楚，不要在后面以奇怪的方式失败）---
$errors = @(Test-Prerequisites)
if ($errors.Count -gt 0) {
    $msg = "启动条件不满足：`r`n`r`n" + ($errors -join "`r`n`r`n")
    Write-Log $msg 'ERROR'
    if (-not $Quiet) { Show-ErrorBox -Title 'ExpoHub 启动失败' -Message $msg }
    exit 1
}

# --- 1. 可选强制重启 ---
if ($Restart) {
    Write-Log '收到 -Restart，先停止现有服务' 'WARN'
    Stop-ServiceOnPort -Port $script:BackendPort  -Label '后端' | Out-Null
    Stop-ServiceOnPort -Port $script:FrontendPort -Label '前端' | Out-Null
}

# --- 2. 后端 ---
$backendUp = Test-HttpOk -Url $script:BackendProbe -TimeoutSec 3
if ($backendUp) {
    Write-Log "后端已在运行（$script:BackendUrl），复用现有实例" 'OK'
} elseif (Test-PortOpen $script:BackendPort) {
    $owner = Get-PortOwnerPid $script:BackendPort
    $msg = "端口 $($script:BackendPort) 已被占用，但它不是 ExpoHub 后端。`r`n`r`n" +
           "占用进程：PID $owner ($(Get-ProcessNameSafe $owner))`r`n`r`n" +
           "处理办法：结束该进程，或改端口后重试。"
    Write-Log $msg 'ERROR'
    if (-not $Quiet) { Show-ErrorBox -Title 'ExpoHub 启动失败' -Message $msg }
    exit 1
} else {
    try { Start-BackendService | Out-Null }
    catch {
        $msg = "后端进程启动失败：$($_.Exception.Message)"
        Write-Log $msg 'ERROR'
        if (-not $Quiet) { Show-ErrorBox -Title 'ExpoHub 启动失败' -Message $msg }
        exit 1
    }
}

# --- 3. 前端 ---
$frontendUp = Test-HttpOk -Url $script:FrontendUrl -TimeoutSec 3
if ($frontendUp) {
    Write-Log "前端已在运行（$script:FrontendUrl），复用现有实例" 'OK'
} elseif (Test-PortOpen $script:FrontendPort) {
    $owner = Get-PortOwnerPid $script:FrontendPort
    $msg = "端口 $($script:FrontendPort) 已被占用，但它不是 ExpoHub 前端。`r`n`r`n" +
           "占用进程：PID $owner ($(Get-ProcessNameSafe $owner))`r`n`r`n" +
           "处理办法：结束该进程，或改端口后重试。"
    Write-Log $msg 'ERROR'
    if (-not $Quiet) { Show-ErrorBox -Title 'ExpoHub 启动失败' -Message $msg }
    exit 1
} else {
    try { Start-FrontendService | Out-Null }
    catch {
        $msg = "前端进程启动失败：$($_.Exception.Message)"
        Write-Log $msg 'ERROR'
        if (-not $Quiet) { Show-ErrorBox -Title 'ExpoHub 启动失败' -Message $msg }
        exit 1
    }
}

# --- 4. 等待就绪（端口开了 ≠ 应用好了，必须真发 HTTP 拿到 200）---
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

if (-not $backendUp) {
    Write-Log "等待后端就绪（最长 $TimeoutSeconds 秒）..." 'INFO'
    if (-not (Wait-HttpOk -Url $script:BackendProbe -TimeoutSeconds $TimeoutSeconds)) {
        $msg = "后端在 $TimeoutSeconds 秒内未就绪。`r`n`r`n" +
               "--- logs\backend.err.log 末尾 ---`r`n" +
               (Get-LogTail (Join-Path $script:LogDir 'backend.err.log'))
        Write-Log $msg 'ERROR'
        if (-not $Quiet) { Show-ErrorBox -Title 'ExpoHub 后端启动超时' -Message $msg }
        $exitCode = 1
    } else {
        Write-Log '后端就绪' 'OK'
    }
}

if ($exitCode -eq 0 -and -not $frontendUp) {
    $remain = [int][Math]::Max(5, ($deadline - (Get-Date)).TotalSeconds)
    Write-Log "等待前端就绪（剩余配额 $remain 秒）..." 'INFO'
    if (-not (Wait-HttpOk -Url $script:FrontendUrl -TimeoutSeconds $remain)) {
        $msg = "前端在超时前未就绪。`r`n`r`n" +
               "--- logs\frontend.out.log 末尾 ---`r`n" +
               (Get-LogTail (Join-Path $script:LogDir 'frontend.out.log')) +
               "`r`n`r`n--- logs\frontend.err.log 末尾 ---`r`n" +
               (Get-LogTail (Join-Path $script:LogDir 'frontend.err.log'))
        Write-Log $msg 'ERROR'
        if (-not $Quiet) { Show-ErrorBox -Title 'ExpoHub 前端启动超时' -Message $msg }
        $exitCode = 1
    } else {
        Write-Log '前端就绪' 'OK'
    }
}

# --- 5. 开窗 ---
if ($exitCode -eq 0) {
    try { Open-AppWindow -NoBrowser:$NoBrowser | Out-Null }
    catch { Write-Log "打开窗口失败：$($_.Exception.Message)" 'WARN' }
    Write-Log "ExpoHub 已就绪：$script:FrontendUrl" 'OK'
}

Write-Log '──────────── 启动流程结束 ────────────' 'INFO'
exit $exitCode
