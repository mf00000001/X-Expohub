# ============================================================================
#  ExpoHub 桌面启动器 — 共享库
#  被 start.ps1 / stop.ps1 / console.ps1 点源加载，不单独运行。
#  约定：所有路径绝对化；日志一律落文件（Windows 后台进程 stdout 不可靠）。
# ============================================================================

Set-StrictMode -Version Latest

# ---------------------------------------------------------------- 路径常量
$script:DesktopDir  = Split-Path -Parent (Split-Path -Parent $PSCommandPath)  # ...\X-Expohub\desktop
$script:ProjectRoot = Split-Path -Parent $script:DesktopDir                    # ...\X-Expohub
$script:BackendDir  = Join-Path $script:ProjectRoot 'expohub-backend'
$script:FrontendDir = Join-Path $script:ProjectRoot 'expo-hub-frontend'
$script:LogDir      = Join-Path $script:DesktopDir  'logs'
$script:AssetDir    = Join-Path $script:DesktopDir  'assets'
$script:RunDir      = Join-Path $script:DesktopDir  'run'    # 存 PID 文件

# 后端解释器：优先项目 venv，回落系统 python
$script:PythonExe = Join-Path $script:ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $script:PythonExe)) { $script:PythonExe = 'python' }

# 前端：直接跑 vite.js，绕开 npx/.cmd 包装，最少中间环节
$script:ViteJs = Join-Path $script:FrontendDir 'node_modules\vite\bin\vite.js'

# ---------------------------------------------------------------- 服务契约
$script:BackendPort  = 8002
$script:FrontendPort = 5173
$script:BackendUrl   = 'http://127.0.0.1:8002'
$script:FrontendUrl  = 'http://127.0.0.1:5173'
# 健康探针：/docs 是 FastAPI 自带且无鉴权的路由，用它判断"应用真的起来了"
# （端口打开 ≠ 应用就绪：uvicorn 先 bind socket 再跑 startup）
$script:BackendProbe = 'http://127.0.0.1:8002/docs'

# ---------------------------------------------------------------- 日志
function Write-Log {
    param(
        [Parameter(Mandatory)][string]$Message,
        [ValidateSet('INFO', 'WARN', 'ERROR', 'OK')][string]$Level = 'INFO'
    )
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line  = "[$stamp][$Level] $Message"

    # 控制台（console.ps1 里可能没有真实控制台，静默失败）
    switch ($Level) {
        'ERROR' { Write-Host $line -ForegroundColor Red }
        'WARN'  { Write-Host $line -ForegroundColor Yellow }
        'OK'    { Write-Host $line -ForegroundColor Green }
        default { Write-Host $line -ForegroundColor Gray }
    }

    # 文件（唯一可靠落点）
    try {
        if (-not (Test-Path $script:LogDir)) { New-Item -ItemType Directory -Force $script:LogDir | Out-Null }
        $launcherLog = Join-Path $script:LogDir 'launcher.log'
        # 简单轮转：超过 1MB 就滚动一次，避免无限增长
        if ((Test-Path $launcherLog) -and ((Get-Item $launcherLog).Length -gt 1MB)) {
            Move-Item $launcherLog "$launcherLog.1" -Force
        }
        Add-Content -Path $launcherLog -Value $line -Encoding UTF8
    } catch { }
}

function Show-MessageBox {
    param(
        [string]$Title = 'ExpoHub',
        [string]$Message,
        [ValidateSet('Error', 'Information', 'Warning')][string]$Kind = 'Information'
    )
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        $icon = [System.Windows.Forms.MessageBoxIcon]::$Kind
        [System.Windows.Forms.MessageBox]::Show($Message, $Title,
            [System.Windows.Forms.MessageBoxButtons]::OK, $icon) | Out-Null
    } catch {
        # 无 UI 会话（如计划任务）时退化为写日志
        Write-Log "无法弹窗，内容：$Message" 'ERROR'
    }
}

function Show-ErrorBox {
    param([string]$Title = 'ExpoHub', [string]$Message)
    Show-MessageBox -Title $Title -Message $Message -Kind 'Error'
}

function Show-InfoBox {
    param([string]$Title = 'ExpoHub', [string]$Message)
    Show-MessageBox -Title $Title -Message $Message -Kind 'Information'
}

# ---------------------------------------------------------------- 网络探测
function Test-PortOpen {
    <# 纯 TcpClient 探测，不依赖 NetTCPIP 模块，比 Get-NetTCPConnection 更可移植 #>
    param([Parameter(Mandatory)][int]$Port, [int]$TimeoutMs = 600)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne($TimeoutMs)) {
            $client.EndConnect($iar)   # 失败会抛异常 → catch
            return $true
        }
        return $false
    } catch { return $false }
    finally { $client.Close() }
}

function Test-HttpOk {
    <# 真发一次 HTTP，确认服务返回 200 —— 这才是"起来了"的证据 #>
    param([Parameter(Mandatory)][string]$Url, [int]$TimeoutSec = 4)
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec -ErrorAction Stop
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

function Wait-HttpOk {
    param(
        [Parameter(Mandatory)][string]$Url,
        [int]$TimeoutSeconds = 90,
        [int]$IntervalMs = 700
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpOk -Url $Url) { return $true }
        Start-Sleep -Milliseconds $IntervalMs
    }
    return $false
}

function Get-PortOwnerPid {
    <# 谁占着这个端口：先试 Get-NetTCPConnection，失败回落 netstat 解析 #>
    param([Parameter(Mandatory)][int]$Port)
    $conn = $null   # 显式初始化：StrictMode 下未赋值变量引用会抛错
    try {
        $conn = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop |
                Select-Object -First 1
        if ($conn) { return [int]$conn.OwningProcess }
    } catch { }

    try {
        $lines = & netstat -ano -p TCP 2>$null | Select-String -Pattern "LISTENING"
        foreach ($l in $lines) {
            $parts = ($l.ToString().Trim() -split '\s+')
            if ($parts.Length -ge 5 -and $parts[1] -match ":$Port$") {
                return [int]$parts[-1]
            }
        }
    } catch { }
    return 0
}

function Get-ProcessNameSafe {
    param([int]$ProcessId)
    if ($ProcessId -le 0) { return '未知' }
    try { return (Get-Process -Id $ProcessId -ErrorAction Stop).ProcessName } catch { return '未知' }
}

# ---------------------------------------------------------------- 服务状态
function Get-ExpohubStatus {
    <# 返回 [ordered]@{ BackendUp; FrontendUp; BackendPid; FrontendPid } #>
    $backendUp  = Test-HttpOk -Url $script:BackendProbe -TimeoutSec 3
    $frontendUp = Test-HttpOk -Url $script:FrontendUrl  -TimeoutSec 3
    $st = [ordered]@{
        BackendUp   = $backendUp
        FrontendUp  = $frontendUp
        BackendPid  = 0
        FrontendPid = 0
    }
    if ($backendUp)  { $st.BackendPid  = Get-PortOwnerPid $script:BackendPort }
    if ($frontendUp) { $st.FrontendPid = Get-PortOwnerPid $script:FrontendPort }
    return $st
}

# ---------------------------------------------------------------- 进程控制
function Stop-ServiceOnPort {
    <#
      按端口杀进程树。必须用 /T（连带子进程）：
      uvicorn --reload 是"父进程持 socket + 子进程跑应用"，只杀父会留下孤儿监听。
    #>
    param([Parameter(Mandatory)][int]$Port, [Parameter(Mandatory)][string]$Label)
    $procId = Get-PortOwnerPid $Port
    if ($procId -le 0) {
        Write-Log "$Label (端口 $Port) 未在运行" 'INFO'
        return $false
    }
    $pname = Get-ProcessNameSafe $procId
    Write-Log "停止 $Label：PID $procId ($pname)，端口 $Port" 'INFO'
    $null = & taskkill /PID $procId /T /F 2>&1
    Start-Sleep -Milliseconds 600
    if (Test-PortOpen $Port) {
        Write-Log "$Label 端口 $Port 仍在监听，停止可能未完成" 'WARN'
        return $false
    }
    Write-Log "$Label 已停止" 'OK'
    return $true
}

function Open-AppWindow {
    <#
      用 Edge --app 打开：独立窗口、无地址栏/标签页、任务栏独立图标 —— 接近原生软件观感。
      不指定 --user-data-dir，避免多占一份浏览器 profile；需要完全隔离时自行加上。
      找不到 Edge 则回退默认浏览器（观感差些，但可用）。
    #>
    param([switch]$NoBrowser)
    if ($NoBrowser) { return 'skip' }

    $edgeCandidates = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $env:ProgramFiles        'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $env:LOCALAPPDATA        'Microsoft\Edge\Application\msedge.exe')
    )
    $edge = $null
    foreach ($c in $edgeCandidates) {
        if ($c -and (Test-Path $c)) { $edge = $c; break }
    }

    if ($edge) {
        $appArgs = @(
            "--app=$script:FrontendUrl",
            '--window-size=1500,950',
            '--window-position=60,30',
            '--no-first-run',
            '--no-default-browser-check'
        )
        Write-Log "以应用窗口模式打开：$script:FrontendUrl" 'INFO'
        Start-Process -FilePath $edge -ArgumentList $appArgs -ErrorAction Stop | Out-Null
        return 'app'
    }

    Write-Log '未找到 Edge，回退到默认浏览器' 'WARN'
    Start-Process $script:FrontendUrl -ErrorAction Stop | Out-Null
    return 'browser'
}

function Test-Prerequisites {
    <# 启动前置校验：缺什么就明确说缺什么，不要在后面以奇怪的方式失败 #>
    param()
    $errors = @()

    if (-not (Test-Path $script:BackendDir)) {
        $errors += "后端目录不存在：$script:BackendDir"
    }
    if (-not (Test-Path $script:PythonExe)) {
        $errors += "Python 解释器不存在：$script:PythonExe`n  → 请先运行 scripts\setup_env.bat 创建虚拟环境"
    }
    if (-not (Test-Path $script:FrontendDir)) {
        $errors += "前端目录不存在：$script:FrontendDir"
    }
    if (-not (Test-Path $script:ViteJs)) {
        $errors += "Vite 未安装：$script:ViteJs 不存在`n  → 请在 expo-hub-frontend 下执行 npm install"
    }
    return $errors
}
