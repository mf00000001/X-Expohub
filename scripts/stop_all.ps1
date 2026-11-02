#requires -Version 5.1
<#
  ExpoHub 一键停止：结束后端 :8002 与前端 :5173 上运行的 ExpoHub 进程
  （会连带结束由 start_all 拉起的 cmd 窗口 / npm 包装进程）

  用法：
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\stop_all.ps1
    powershell ... -File scripts\stop_all.ps1 -BackendPort 8002 -FrontendPort 5173
#>
[CmdletBinding()]
param(
    [int]$BackendPort = 8002,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = 'Continue'

$Root = Split-Path -Parent $PSScriptRoot

function Write-Ok($text)   { Write-Host ("  [OK] " + $text) -ForegroundColor Green }
function Write-Warn2($text){ Write-Host ("  [!!] " + $text) -ForegroundColor Yellow }
function Write-Step($text) { Write-Host ("  [..] " + $text) -ForegroundColor Gray }

function Get-ListenerPids([int]$port) {
    try {
        return @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
                 Select-Object -ExpandProperty OwningProcess -Unique)
    } catch {
        return @()
    }
}

# 进程表快照：pid -> 名称/父进程/命令行
function Get-ProcessTable {
    $table = @{}
    try {
        $procs = Get-CimInstance Win32_Process -ErrorAction Stop
    } catch {
        return $table
    }
    foreach ($p in $procs) {
        $table[[int]$p.ProcessId] = @{
            Name = "$($p.Name)"
            PPid = [int]$p.ParentProcessId
            CL   = "$($p.CommandLine)"
        }
    }
    return $table
}

# 判断某个父进程是否属于本次启动的 ExpoHub 进程链（避免误杀其它程序）
function Test-IsOurs($info, [string]$rootLower) {
    if (-not $info) { return $false }
    $cl = $info.CL.ToLower()
    switch ($info.Name.ToLower()) {
        'cmd.exe' {
            return (($cl -match 'expohub-(backend|frontend)') -or ($cl.IndexOf($rootLower) -ge 0))
        }
        'node.exe' {
            return (($cl -match 'npm-cli\.js') -or ($cl.IndexOf($rootLower) -ge 0))
        }
        'python.exe' { return ($cl.IndexOf($rootLower) -ge 0) }
        default { return ($cl.IndexOf($rootLower) -ge 0) }
    }
}

Write-Host ''
Write-Host '  ExpoHub 一键停止' -ForegroundColor Cyan

$table = Get-ProcessTable
$rootLower = $Root.ToLower()

$seeds = New-Object System.Collections.Generic.List[int]
foreach ($port in @($BackendPort, $FrontendPort)) {
    foreach ($procId in (Get-ListenerPids $port)) {
        if ($procId) { $seeds.Add([int]$procId) }
    }
}
# 兜底 1：命令行里带本仓库路径的 uvicorn / vite / npm run dev 进程
foreach ($key in $table.Keys) {
    $info = $table[$key]
    if (-not $info.CL) { continue }
    $cl = $info.CL.ToLower()
    if ($cl.IndexOf($rootLower) -lt 0) { continue }
    if (($cl -match 'uvicorn') -or ($cl -match 'app\.main') -or ($cl -match 'vite') -or ($cl -match 'npm-cli\.js')) {
        $seeds.Add([int]$key)
    }
}
# 兜底 2：start_all 打开的服务窗口（标题带 ExpoHub-Backend / ExpoHub-Frontend 标记）
foreach ($key in $table.Keys) {
    $info = $table[$key]
    if (-not $info.CL) { continue }
    if ($info.Name.ToLower() -ne 'cmd.exe') { continue }
    if ($info.CL.ToLower() -match 'expohub-(backend|frontend)') { $seeds.Add([int]$key) }
}

# 向上补充父进程（我们自己拉起的 cmd 窗口 / npm 包装），最多上溯 4 层
$all = New-Object System.Collections.Generic.List[int]
foreach ($seed in ($seeds | Sort-Object -Unique)) { $all.Add([int]$seed) }
foreach ($seed in ($seeds | Sort-Object -Unique)) {
    $cur = $seed
    for ($depth = 0; $depth -lt 4; $depth++) {
        if (-not $table.ContainsKey($cur)) { break }
        $parentId = $table[$cur].PPid
        if (-not $parentId -or -not $table.ContainsKey($parentId)) { break }
        if (Test-IsOurs $table[$parentId] $rootLower) {
            $all.Add([int]$parentId)
            $cur = $parentId
        } else {
            break
        }
    }
}

$targets = @($all | Sort-Object -Unique | Where-Object { $_ -and $_ -ne $PID })

if ($targets.Count -eq 0) {
    Write-Warn2 ("未发现运行中的 ExpoHub 服务（端口 {0} / {1} 均无监听）" -f $BackendPort, $FrontendPort)
} else {
    foreach ($procId in $targets) {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if (-not $proc) { continue }
        $name = $proc.ProcessName
        if ($table.ContainsKey($procId)) { $name = $table[$procId].Name }
        Write-Step ("结束 PID {0} ({1})" -f $procId, $name)
        & taskkill.exe /PID $procId /T /F 2>&1 | Out-Null
    }
    Write-Ok ("已结束 {0} 个进程" -f $targets.Count)
}

# 等待端口释放（最多 5 秒）
$stillUsed = @()
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Milliseconds 500
    $stillUsed = @()
    foreach ($port in @($BackendPort, $FrontendPort)) {
        if ((Get-ListenerPids $port).Count -gt 0) { $stillUsed += $port }
    }
    if ($stillUsed.Count -eq 0) { break }
}

if ($stillUsed.Count -gt 0) {
    Write-Warn2 ("端口仍被占用：" + ($stillUsed -join ', ') + "（可能权限不足或为其它程序占用，可尝试以管理员身份运行）")
} else {
    Write-Ok ("端口 {0} / {1} 已释放" -f $BackendPort, $FrontendPort)
}

Write-Host ''
Start-Sleep -Milliseconds 800
exit 0
