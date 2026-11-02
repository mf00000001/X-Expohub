#requires -Version 5.1
<#
  ExpoHub 一键启动（后端 FastAPI :8002 + 前端 Vite :5173）

  用法（通常由根目录 start_all.bat 调用，也可直接运行）：
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_all.ps1
    powershell ... -File scripts\start_all.ps1 -Reload           # 后端热重载
    powershell ... -File scripts\start_all.ps1 -NoBrowser        # 不自动开浏览器
    powershell ... -File scripts\start_all.ps1 -Background       # 后台模式（日志落 logs\）
    powershell ... -File scripts\start_all.ps1 -BindHost 0.0.0.0 # 局域网/手机访问

  参数：
    -BackendPort / -FrontendPort  端口，默认 8002 / 5173
    -BindHost                     监听地址，默认 127.0.0.1
    -NoBrowser                    启动后不打开浏览器
    -SkipInstall                  跳过依赖安装检查
    -Reload                       后端启用 --reload 热重载
    -Background                   不开新窗口，日志写入 logs\（自检/CI 用）
    -TimeoutSec                   等待服务就绪的秒数，默认 120
#>
[CmdletBinding()]
param(
    [int]$BackendPort = 8002,
    [int]$FrontendPort = 5173,
    [string]$BindHost = '127.0.0.1',
    [switch]$NoBrowser,
    [switch]$SkipInstall,
    [switch]$Reload,
    [switch]$Background,
    [int]$TimeoutSec = 120
)

$ErrorActionPreference = 'Stop'

# ---------- 路径 ----------
$scriptDir   = $PSScriptRoot
$Root        = Split-Path -Parent $scriptDir
$backendDir  = Join-Path $Root 'expohub-backend'
$frontendDir = Join-Path $Root 'expo-hub-frontend'
$venvDir     = Join-Path $Root '.venv'
$venvPy      = Join-Path $venvDir 'Scripts\python.exe'
$logDir      = Join-Path $Root 'logs'
$reqFile     = Join-Path $backendDir 'requirements.txt'

$backendUrl  = "http://127.0.0.1:$BackendPort/"
$docsUrl     = "http://127.0.0.1:$BackendPort/docs"
$frontendUrl = "http://127.0.0.1:$FrontendPort/"

$script:StartedPids = @()

# 是否交互式控制台（决定结束时是否等按键；被脚本/CI 调用时不阻塞）
$script:Interactive = $true
try { if ([Console]::IsInputRedirected) { $script:Interactive = $false } } catch { }

# ---------- 输出 ----------
function Write-Title($text) {
    Write-Host ''
    Write-Host ('  ' + $text) -ForegroundColor Cyan
    Write-Host ('  ' + ('-' * [Math]::Max(8, $text.Length))) -ForegroundColor DarkGray
}
function Write-Step($text) { Write-Host ("  [..] " + $text) -ForegroundColor Gray }
function Write-Ok($text)   { Write-Host ("  [OK] " + $text) -ForegroundColor Green }
function Write-Warn2($text){ Write-Host ("  [!!] " + $text) -ForegroundColor Yellow }
function Write-Fail($text) { Write-Host ("  [XX] " + $text) -ForegroundColor Red }

# ---------- 工具 ----------
function Test-PortListening([int]$port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect('127.0.0.1', $port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(400)
        if ($ok) {
            try { $client.EndConnect($iar) } catch { $ok = $false }
        }
        $client.Close()
        return $ok
    } catch {
        return $false
    }
}

function Get-PortOwner([int]$port) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
                Select-Object -First 1
        if (-not $conn) { return $null }
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        if ($proc) { return ("PID {0} ({1})" -f $proc.Id, $proc.ProcessName) }
        return ("PID {0}" -f $conn.OwningProcess)
    } catch {
        return $null
    }
}

# 判断端口上跑的到底是不是 ExpoHub 自己（避免把别人的服务当成"已在运行"）
function Test-BackendAlive([int]$port, [int]$timeoutSec = 4) {
    try {
        $resp = Invoke-WebRequest -Uri ("http://127.0.0.1:{0}/" -f $port) -UseBasicParsing -TimeoutSec $timeoutSec -ErrorAction Stop
        if ($resp.StatusCode -ne 200) { return $false }
        $json = $resp.Content | ConvertFrom-Json
        if (-not $json.success) { return $false }
        return ("$($json.message)" -match 'ExpoHub')
    } catch {
        return $false
    }
}

function Test-FrontendAlive([int]$port, [int]$timeoutSec = 4) {
    try {
        $resp = Invoke-WebRequest -Uri ("http://127.0.0.1:{0}/" -f $port) -UseBasicParsing -TimeoutSec $timeoutSec -ErrorAction Stop
        return ($resp.StatusCode -eq 200 -and $resp.Content -match 'id="app"')
    } catch {
        return $false
    }
}

function Get-CommandPath([string]$name) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { return $cmd.Source }
    return $null
}

# 原生命令调用：PowerShell 5.1 下 `2>&1` 会把原生 stderr 变成 ErrorRecord，
# 与 $ErrorActionPreference='Stop' 组合会直接抛异常；这里局部设置 Continue，并用退出码判断成败。
function Invoke-Native([string]$exe, [string[]]$argList) {
    $ErrorActionPreference = 'Continue'
    $out = & $exe @argList 2>&1
    $script:LastNativeExit = $LASTEXITCODE
    return @($out)
}

# 找可用的 Python（优先 py 启动器，其次 PATH，最后扫常见安装目录）
function Get-PythonCandidates {
    $result = New-Object System.Collections.ArrayList
    $seen = @{}

    $py = Get-CommandPath 'py'
    if ($py) {
        foreach ($v in @('3.13', '3.12', '3.11')) {
            $key = ("{0}|{1}" -f $py, $v).ToLower()
            if (-not $seen.ContainsKey($key)) {
                $seen[$key] = $true
                [void]$result.Add(@{ Exe = $py; Args = @("-" + $v) })
            }
        }
    }

    $direct = @()
    foreach ($n in @('python', 'python3')) {
        $p = Get-CommandPath $n
        if ($p) { $direct += $p }
    }
    # 扫描常见安装位置（含 uv 托管的 Python，避免 PATH 里只有 Microsoft Store 占位符）
    foreach ($pattern in @(
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python3*\python.exe'),
            (Join-Path $env:ProgramFiles 'Python3*\python.exe'),
            (Join-Path $env:APPDATA 'uv\python\cpython-3.1*\python.exe'))) {
        if (-not $pattern) { continue }
        foreach ($hit in @(Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | Sort-Object FullName -Descending)) {
            $direct += $hit.FullName
        }
    }

    foreach ($exePath in $direct) {
        if (-not $exePath) { continue }
        $key = $exePath.ToLower()
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true
        [void]$result.Add(@{ Exe = $exePath; Args = @() })
    }

    return $result
}

function Get-PythonVersion($cand) {
    $out = Invoke-Native $cand.Exe (@($cand.Args) + @('--version'))
    if ($script:LastNativeExit -ne 0) { return $null }
    foreach ($line in $out) {
        if ("$line" -match 'Python\s+(\d+)\.(\d+)') {
            return [version]("{0}.{1}" -f $Matches[1], $Matches[2])
        }
    }
    return $null
}

# ---------- 依赖准备 ----------
function Ensure-BackendEnv {
    $ErrorActionPreference = 'Continue'
    if ($SkipInstall) { Write-Warn2 '已跳过依赖检查（-SkipInstall）'; return }

    if (Test-Path $venvPy) {
        Write-Step '检查后端虚拟环境 .venv ...'
        $null = Invoke-Native $venvPy @('-c', 'import fastapi,sqlalchemy,uvicorn,aiosqlite')
        if ($script:LastNativeExit -eq 0) {
            Write-Ok '后端依赖已就绪'
            return
        }
        Write-Warn2 '已有 .venv 但依赖不完整，正在补装 requirements.txt ...'
        & $venvPy -m pip install --disable-pip-version-check --no-input --quiet -r $reqFile
        if ($LASTEXITCODE -ne 0) { throw "后端依赖安装失败，请检查网络或代理（pip install -r $reqFile）" }
        Write-Ok '后端依赖安装完成'
        return
    }

    Write-Step '首次运行：创建后端虚拟环境 .venv ...'
    $candidates = @(Get-PythonCandidates)
    if ($candidates.Count -eq 0) {
        throw '未找到 Python。请安装 Python 3.12/3.13（勾选 Add to PATH）后重试：https://www.python.org/downloads/'
    }

    $created = $false
    $lastErr = ''
    foreach ($cand in $candidates) {
        $ver = Get-PythonVersion $cand
        if (-not $ver) { continue }
        if ($ver -lt [version]'3.10') {
            Write-Warn2 ("跳过 Python {0}（版本过低，需 3.10+）：{1}" -f $ver, $cand.Exe)
            continue
        }
        Write-Step ("使用 Python {0} 创建虚拟环境（{1}）" -f $ver, $cand.Exe)
        if (Test-Path $venvDir) { Remove-Item -Recurse -Force $venvDir -ErrorAction SilentlyContinue }
        $null = Invoke-Native $cand.Exe (@($cand.Args) + @('-m', 'venv', $venvDir))
        if ($script:LastNativeExit -ne 0 -or -not (Test-Path $venvPy)) {
            $lastErr = ("Python {0} 创建 venv 失败" -f $ver)
            continue
        }
        $null = Invoke-Native $venvPy @('-m', 'pip', 'install', '--disable-pip-version-check', '--upgrade', 'pip')
        Write-Step '安装后端依赖（固定版本，首次约 1-3 分钟，静默安装请耐心等待）...'
        & $venvPy -m pip install --disable-pip-version-check --no-input --quiet -r $reqFile
        if ($LASTEXITCODE -eq 0) {
            $created = $true
            break
        }
        $lastErr = ("Python {0} 下安装依赖失败" -f $ver)
        Write-Warn2 $lastErr
    }

    if (-not $created) {
        if (Test-Path $venvDir) { Remove-Item -Recurse -Force $venvDir -ErrorAction SilentlyContinue }
        throw ("后端依赖安装失败：{0}。建议安装 Python 3.12/3.13 后重试。" -f $lastErr)
    }
    Write-Ok '后端虚拟环境创建完成'
}

function Ensure-FrontendEnv {
    $ErrorActionPreference = 'Continue'
    if ($SkipInstall) { return }
    $needInstall = -not (Test-Path (Join-Path $frontendDir 'node_modules\vite'))
    if (-not $needInstall) {
        Write-Ok '前端依赖已就绪'
        return
    }
    $npm = Get-CommandPath 'npm.cmd'
    if (-not $npm) { $npm = Get-CommandPath 'npm' }
    if (-not $npm) {
        throw '未找到 npm。请安装 Node.js 18+（https://nodejs.org/）后重试。'
    }
    Write-Step '首次运行：安装前端依赖 npm install（约 1-2 分钟）...'
    Push-Location $frontendDir
    try {
        & $npm install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw '前端依赖安装失败，请检查网络或代理（npm install）' }
    } finally {
        Pop-Location
    }
    Write-Ok '前端依赖安装完成'
}

# ---------- 启动 ----------
function Start-Window($title, $exe, [string[]]$argList, $workDir, $logPrefix) {
    if ($Background) {
        if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
        $outLog = Join-Path $logDir ("{0}.log" -f $logPrefix)
        $errLog = Join-Path $logDir ("{0}.err.log" -f $logPrefix)
        $p = Start-Process -FilePath $exe -ArgumentList $argList -WorkingDirectory $workDir `
                -NoNewWindow -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru
        $script:StartedPids += $p.Id
        return $p.Id
    }

    # 新窗口里先切 UTF-8 代码页（避免中文/箭头乱码），再设标题并启动服务
    $cmdLine = 'chcp 65001>nul & title {0} & "{1}" {2}' -f $title, $exe, ($argList -join ' ')
    $p = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/k', $cmdLine) -WorkingDirectory $workDir -PassThru
    $script:StartedPids += $p.Id
    return $p.Id
}

function Wait-Ready($label, $probe, $port, $procHandle) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    Write-Step ("{0} 启动中，等待 http://127.0.0.1:{1}/ 就绪 ..." -f $label, $port)
    while ((Get-Date) -lt $deadline) {
        if (& $probe $port) { return $true }
        if ($procHandle -and -not (Get-Process -Id $procHandle -ErrorAction SilentlyContinue)) { return $false }
        Start-Sleep -Milliseconds 800
    }
    return $false
}

function Stop-Started {
    foreach ($procId in $script:StartedPids) {
        try {
            $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($p) { & taskkill.exe /PID $procId /T /F 2>&1 | Out-Null }
        } catch { }
    }
    $script:StartedPids = @()
}

# ---------- 主流程 ----------
$exitCode = 0
try {
    Write-Host ''
    Write-Host '  ============================================================' -ForegroundColor Cyan
    Write-Host '    ExpoHub 展会撮合平台  ·  一键启动' -ForegroundColor Cyan
    Write-Host '  ============================================================' -ForegroundColor Cyan

    if (-not (Test-Path $backendDir))  { throw "找不到后端目录：$backendDir" }
    if (-not (Test-Path $frontendDir)) { throw "找不到前端目录：$frontendDir" }

    Write-Title '1/4 依赖检查'
    if (-not $SkipInstall) {
        $node = Get-CommandPath 'node'
        if (-not $node) {
            throw '未找到 Node.js。请安装 Node.js 18+（https://nodejs.org/）后重试。'
        }
        Write-Ok ("Node.js: " + (& $node --version))
    }
    Ensure-BackendEnv
    Ensure-FrontendEnv

    Write-Title '2/4 端口检查'
    $backupRunning = $false
    if (Test-PortListening $BackendPort) {
        if (Test-BackendAlive $BackendPort 5) {
            Write-Warn2 ("后端端口 {0} 已有 ExpoHub 在运行，直接复用" -f $BackendPort)
            $backupRunning = $true
        } else {
            throw ("端口 {0} 已被其它程序占用（{1}）。请先运行 stop_all.bat，或改用 -BackendPort 指定其它端口。" -f $BackendPort, (Get-PortOwner $BackendPort))
        }
    } else {
        Write-Ok ("后端端口 {0} 空闲" -f $BackendPort)
    }

    $frontRunning = $false
    if (Test-PortListening $FrontendPort) {
        if (Test-FrontendAlive $FrontendPort 5) {
            Write-Warn2 ("前端端口 {0} 已有服务在运行，直接复用" -f $FrontendPort)
            $frontRunning = $true
        } else {
            throw ("端口 {0} 已被其它程序占用（{1}）。请先运行 stop_all.bat，或改用 -FrontendPort 指定其它端口。" -f $FrontendPort, (Get-PortOwner $FrontendPort))
        }
    } else {
        Write-Ok ("前端端口 {0} 空闲" -f $FrontendPort)
    }

    Write-Title '3/4 启动服务'
    $backendPid = $null
    if (-not $backupRunning) {
        $uvArgs = @('-m', 'uvicorn', 'app.main:app', '--host', $BindHost, '--port', "$BackendPort")
        if ($Reload) { $uvArgs += '--reload' }
        $backendPid = Start-Window 'ExpoHub-Backend' $venvPy $uvArgs $backendDir 'backend'
        if (-not (Wait-Ready '后端' 'Test-BackendAlive' $BackendPort $backendPid)) {
            throw ("后端未能在 {0} 秒内就绪。请查看后端窗口报错，或运行 -Background 模式查看 logs\backend.err.log" -f $TimeoutSec)
        }
        Write-Ok ("后端已就绪  {0}" -f $backendUrl)
    } else {
        Write-Ok '后端沿用已在运行的实例'
    }

    $frontendPid = $null
    if (-not $frontRunning) {
        $npm = Get-CommandPath 'npm.cmd'
        if (-not $npm) { $npm = Get-CommandPath 'npm' }
        $feArgs = @('run', 'dev', '--', '--host', $BindHost, '--port', "$FrontendPort", '--strictPort')
        if ($Background) {
            # 后台模式：cmd /c 让 npm 退出后窗口不残留
            $frontendPid = Start-Window 'ExpoHub-Frontend' 'cmd.exe' (@('/c', ('"{0}" {1}' -f $npm, ($feArgs -join ' ')))) $frontendDir 'frontend'
        } else {
            $frontendPid = Start-Window 'ExpoHub-Frontend' $npm $feArgs $frontendDir 'frontend'
        }
        if (-not (Wait-Ready '前端' 'Test-FrontendAlive' $FrontendPort $frontendPid)) {
            throw ("前端未能在 {0} 秒内就绪。请查看前端窗口报错，或运行 -Background 模式查看 logs\frontend.err.log" -f $TimeoutSec)
        }
        Write-Ok ("前端已就绪  {0}" -f $frontendUrl)
    } else {
        Write-Ok '前端沿用已在运行的实例'
    }

    Write-Title '4/4 访问入口'
    Write-Host ''
    Write-Host ("    前端页面   " + $frontendUrl) -ForegroundColor White
    Write-Host ("    接口文档   " + $docsUrl) -ForegroundColor White
    Write-Host ("    接口根路径 " + $backendUrl) -ForegroundColor White
    Write-Host ''
    Write-Host '    测试账号（用户名 / 密码）' -ForegroundColor DarkGray
    Write-Host '      admin / admin123               平台管理员（展会自营）' -ForegroundColor DarkGray
    Write-Host '      organizer_canton / org123      平台运营子账号（原主办方，已升为 admin）' -ForegroundColor DarkGray
    Write-Host '      exhibitor_huawei / exh123      展商' -ForegroundColor DarkGray
    Write-Host '      buyer_li / buyer123            买家' -ForegroundColor DarkGray
    Write-Host '      visitor_chen / visitor123      游客' -ForegroundColor DarkGray
    Write-Host ''
    Write-Host '    关闭服务：双击 stop_all.bat，或直接关掉两个服务窗口' -ForegroundColor DarkGray
    Write-Host ''

    if (-not $NoBrowser) {
        try {
            Start-Process $frontendUrl | Out-Null
            Write-Ok '已在浏览器中打开前端页面'
        } catch {
            Write-Warn2 '自动打开浏览器失败，请手动访问上面的地址'
        }
    }
    Write-Ok '启动完成'

    # 双击运行时不要一闪而过：等用户看完再关这个窗口（服务仍在各自窗口里跑）
    if ($script:Interactive -and -not $Background) {
        Write-Host ''
        Write-Host '  按任意键关闭本窗口（后端/前端会继续运行，关闭服务请用 stop_all.bat）...' -ForegroundColor DarkGray
        try { [void]$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch { }
        Write-Host ''
    }
} catch {
    Write-Host ''
    Write-Fail $_.Exception.Message
    Stop-Started
    $exitCode = 1
} finally {
    # 仅在交互式控制台里暂停，避免被脚本/CI 调用时卡在按键上
    if ($exitCode -ne 0 -and -not $Background -and $script:Interactive) {
        Write-Host ''
        Write-Host '  按任意键退出 ...' -ForegroundColor DarkGray
        try { [void]$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch { }
    }
}

exit $exitCode
