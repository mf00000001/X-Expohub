<#
.SYNOPSIS
    从零构建 ExpoHub 便携试用包（可复现）。

.DESCRIPTION
    把"发给领导双击即用"的绿色包一次构建出来：
      Python 运行时 → 依赖 → 裁剪 → 后端代码 → 前端产物 → 演示数据 → 说明文档 → ZIP

    重复执行是幂等的：已下载的 Python 包会复用，各步骤直接覆盖产物。

.PARAMETER OutRoot
    构建工作区，默认 D:\Projects\expo-hub-portable。产物 ZIP 也落在这里。

.PARAMETER PythonVersion
    Python 版本，默认 3.13.9。**必须与开发用 .venv 的版本一致**——
    依赖里的 C 扩展（pydantic_core / greenlet / cryptography）是按
    解释器版本编译的，版本对不上会 import 失败。

.PARAMETER SkipDeps
    跳过依赖安装（site-packages 已就绪时用，省几分钟）。

.PARAMETER SkipFrontend
    跳过前端构建（dist 已是新的时用）。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File portable\build\build_portable.ps1
    全量重建。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File portable\build\build_portable.ps1 -SkipDeps -SkipFrontend
    只重新复刻代码/数据/文档并打包（最快，用于微调后出包）。

.NOTES
    本文件必须存为 **UTF-8 with BOM**。PowerShell 5.1 按 ANSI 读无 BOM 脚本，
    中文会全部乱码并导致语法解析失败。改完记得重跑 bom_fix.ps1。
#>
[CmdletBinding()]
param(
    [string]$OutRoot = 'D:\Projects\expo-hub-portable',
    [string]$PythonVersion = '3.13.9',
    [switch]$SkipDeps,
    [switch]$SkipFrontend
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# ---------------------------------------------------------------- 路径推导
# $PSScriptRoot = <repo>\portable\build  →  上两级 = 仓库根
$RepoRoot   = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$PortableSrc = Join-Path $RepoRoot 'portable'
$BackendSrc  = Join-Path $RepoRoot 'expohub-backend'
$FrontendSrc = Join-Path $RepoRoot 'expo-hub-frontend'

$PkgName = 'ExpoHub-' + [char]0x8BD5 + [char]0x7528 + [char]0x7248      # ExpoHub-试用版
$Pkg     = Join-Path $OutRoot $PkgName
$Runtime = Join-Path $Pkg 'runtime'
$Server  = Join-Path $Pkg 'server'
$Scripts = Join-Path $Pkg 'scripts'
$WebDir  = Join-Path $Server 'web'
$Logs    = Join-Path $Pkg 'logs'
$Cache   = Join-Path $OutRoot 'build\downloads'
$ZipOut  = Join-Path $OutRoot "$PkgName.zip"

$script:StepNo = 0
function Step([string]$Title) {
    $script:StepNo++
    Write-Host ''
    Write-Host ("[{0}] {1}" -f $script:StepNo, $Title) -ForegroundColor Cyan
}
function Ok([string]$Msg)   { Write-Host "     $Msg" -ForegroundColor Green }
function Info([string]$Msg) { Write-Host "     $Msg" }
function Die([string]$Msg)  { Write-Host "`n  [失败] $Msg" -ForegroundColor Red; exit 1 }

function Get-SystemPython {
    foreach ($c in 'python', 'py') {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    return $null
}

Write-Host ''
Write-Host '  ╔══════════════════════════════════════════════╗' -ForegroundColor Cyan
Write-Host '  ║   ExpoHub 便携试用包 · 构建                 ║' -ForegroundColor Cyan
Write-Host '  ╚══════════════════════════════════════════════╝' -ForegroundColor Cyan
Info "仓库根 : $RepoRoot"
Info "工作区 : $OutRoot"

# ================================================================ 0. 前置检查
Step '前置检查'
foreach ($p in @($BackendSrc, $FrontendSrc, $PortableSrc)) {
    if (-not (Test-Path $p)) { Die "缺少源目录: $p" }
}
Ok '源目录齐全'

$sysPy = Get-SystemPython
if (-not $sysPy) { Die '找不到系统 Python（需要它来 pip install 依赖到包内）。装一个或用 winget install Python.Python.3.13' }
$pyver = (& $sysPy --version) -join ''
Ok "系统 Python: $pyver  ($sysPy)"
if ($pyver -notmatch [regex]::Escape($PythonVersion)) {
    Write-Host "     ⚠️  系统 Python 版本与 -PythonVersion $PythonVersion 不一致。" -ForegroundColor Yellow
    Write-Host "         C 扩展是按解释器版本编译的，版本不符会导致 import 失败。" -ForegroundColor Yellow
}

if (-not $SkipFrontend) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Die '找不到 npm（构建前端需要）。或用 -SkipFrontend 跳过' }
    Ok 'npm 可用'
}

# ================================================================ 1. 目录
Step '准备工作目录'
foreach ($d in @($Pkg, $Runtime, $Server, $Scripts, $WebDir, $Logs, $Cache)) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
# 清掉上一次的运行态残留，避免把日志/备份打进包里
Get-ChildItem $Logs -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $Server -Directory -Filter 'app.bak-*' -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force
Ok "工作区就绪: $Pkg"

# ================================================================ 2. Python 运行时
Step "获取 Python $PythonVersion embeddable"
# 依赖已就绪时连下载都省掉
$reuseRuntime = $SkipDeps -and
                (Test-Path (Join-Path $Runtime 'python.exe')) -and
                (Test-Path (Join-Path $Runtime 'Lib\site-packages\fastapi'))

$zipCache = Join-Path $Cache "python-$PythonVersion-embed-amd64.zip"
if ($reuseRuntime) {
    Info '复用现有运行时，跳过下载'
} elseif (Test-Path $zipCache) {
    Ok "复用缓存: $zipCache"
} else {
    $urls = @(
        "https://mirrors.huaweicloud.com/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip",
        "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
    )
    $ok = $false
    foreach ($u in $urls) {
        try {
            Info "下载 $u"
            Invoke-WebRequest -Uri $u -OutFile $zipCache -TimeoutSec 120 -UseBasicParsing
            $ok = $true; break
        } catch { Info "  失败: $($_.Exception.Message.Split([char]10)[0])" }
    }
    if (-not $ok) { Die 'Python embeddable 下载失败（国内优先用华为云镜像，检查网络）' }
    Ok "已下载 $([math]::Round((Get-Item $zipCache).Length/1MB,2)) MB"
}

# 解压会把整个 runtime\ 清空（包括已装好的依赖）。
# 指定 -SkipDeps 且依赖已就绪时直接复用，否则 -SkipDeps 就名不副实了。
if ($reuseRuntime) {
    Ok '复用现有运行时与依赖（-SkipDeps）'
} else {
    Get-ChildItem $Runtime -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive -Path $zipCache -DestinationPath $Runtime -Force
    New-Item -ItemType Directory -Force -Path (Join-Path $Runtime 'Lib\site-packages') | Out-Null

    # ._pth：让 embeddable 认识 site-packages，否则依赖全都 import 不到
    $pth = Join-Path $Runtime 'python313._pth'
    Set-Content -Path $pth -Value @('python313.zip', '.', 'Lib\site-packages', 'import site') -Encoding ascii
    Ok '运行时已解压'
}

$rtVer = (& (Join-Path $Runtime 'python.exe') --version) -join ''
Ok "运行时: $rtVer"

# ================================================================ 3. 依赖
Step '安装后端依赖到包内'
$sitePackages = Join-Path $Runtime 'Lib\site-packages'
$req = Join-Path $BackendSrc 'requirements.txt'
if ($SkipDeps) {
    if (-not (Test-Path (Join-Path $sitePackages 'fastapi'))) { Die '指定了 -SkipDeps 但 site-packages 是空的' }
    Ok '已跳过（-SkipDeps）'
} else {
    Info "pip install --target $sitePackages"
    & $sysPy -m pip install -r $req --target $sitePackages `
        --no-warn-script-location --upgrade -q
    if ($LASTEXITCODE -ne 0) { Die 'pip install 失败' }
    $mb = [math]::Round((Get-ChildItem $sitePackages -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 2)
    Ok "依赖已装: ${mb} MB"
}

# ================================================================ 4. 裁剪
Step '裁剪用不到的部分'
# jieba 只用到 import jieba / add_word / lcut。下面三个子模块后端从不 import：
#   lac_small —— 只有 cut(use_paddle=True) 才会 lazy import，而 use_paddle 默认 False
#   posseg    —— 词性标注，未使用
#   analyse   —— TF-IDF，未使用
# 实测 42MB → 8MB。删完务必跑 verify_business.py 确认分词没退化成二元组。
$jieba = Join-Path $sitePackages 'jieba'
if (Test-Path $jieba) {
    $before = [math]::Round((Get-ChildItem $jieba -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 2)
    foreach ($m in 'lac_small', 'posseg', 'analyse') {
        $t = Join-Path $jieba $m
        if (Test-Path $t) { Remove-Item $t -Recurse -Force }
    }
    $after = [math]::Round((Get-ChildItem $jieba -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 2)
    Ok "jieba: ${before} MB -> ${after} MB"
} else {
    Info '未找到 jieba，跳过'
}

# ================================================================ 5. 后端代码
Step '复刻后端代码'
$appDst = Join-Path $Server 'app'
if (Test-Path $appDst) { Remove-Item $appDst -Recurse -Force }
# 排除测试/缓存/种子脚本/容器文件——运行时不需要，还会带进无谓的体积和密钥风险
& robocopy (Join-Path $BackendSrc 'app') $appDst /E /NFL /NDL /NJH /NJS /NP `
    /XD __pycache__ .pytest_cache | Out-Null
if ($LASTEXITCODE -ge 8) { Die "robocopy 失败（exit $LASTEXITCODE）" }

Copy-Item (Join-Path $BackendSrc 'requirements.txt') $Server -Force
Copy-Item (Join-Path $PortableSrc 'app\portable_main.py') $Server -Force
# .env 模板 -> .env（不带任何真实 API Key）
Copy-Item (Join-Path $PortableSrc 'app\.env.template') (Join-Path $Server '.env') -Force

foreach ($f in 'start.ps1', 'stop.ps1', 'update.ps1', 'update-source.txt') {
    Copy-Item (Join-Path $PortableSrc "app\scripts\$f") $Scripts -Force
}
$n = (Get-ChildItem $appDst -Recurse -File -Filter *.py).Count
Ok "后端 $n 个 .py；入口与脚本已就位"

# ================================================================ 6. 前端产物
Step '前端产物'
if ($SkipFrontend) {
    if (-not (Test-Path (Join-Path $WebDir 'index.html'))) { Die '指定了 -SkipFrontend 但 web/ 是空的' }
    Ok '已跳过（-SkipFrontend）'
} else {
    Info 'npm run build'
    Push-Location $FrontendSrc
    try {
        & npm run build 2>&1 | ForEach-Object { if ($_ -match 'error|Error') { Write-Host "     $_" -ForegroundColor DarkYellow } }
        if ($LASTEXITCODE -ne 0) { Die '前端构建失败' }
    } finally { Pop-Location }
    & robocopy (Join-Path $FrontendSrc 'dist') $WebDir /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { Die "前端产物复制失败（exit $LASTEXITCODE）" }
    $mb = [math]::Round((Get-ChildItem $WebDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 2)
    Ok "web/ ${mb} MB"
}

# ================================================================ 7. 演示数据
Step '清洗演示数据'
$dbSrc = Join-Path $BackendSrc 'expohub.db'
$dbDst = Join-Path $Server 'expohub.db'
& $sysPy (Join-Path $PSScriptRoot 'clean_demo_data.py') $dbSrc $dbDst
if ($LASTEXITCODE -ne 0) { Die '演示数据清理失败' }

# ================================================================ 8. 使用说明
Step '生成使用说明.docx'
# 注意：传给 python 的参数必须用 `--out-dir` 双横线形式。
# PowerShell 风格的 -OutDir 会被 argparse 当成未知短选项而报错。
& $sysPy (Join-Path $PSScriptRoot 'make_guide.py') `
    '--out-dir' $Pkg '--tools-dir' (Join-Path $OutRoot 'build\pytools')
if ($LASTEXITCODE -ne 0) { Die '生成说明文档失败' }

# ================================================================ 9. 顶层入口
Step '生成双击入口'
# .bat 必须纯 ASCII：cmd.exe 按 OEM 代码页读批处理，中文注释会乱码
$batLaunch = @'
@echo off
REM Pure ASCII on purpose. cmd.exe reads .bat with the OEM codepage, so Chinese
REM text here would turn into garbage. All Chinese lives in scripts\*.ps1.
chcp 65001 >nul
title ExpoHub
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
if errorlevel 1 pause
'@
$batStop = @'
@echo off
REM Pure ASCII on purpose - see the launch .bat for why.
chcp 65001 >nul
title ExpoHub
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1"
'@
$batUpdate = @'
@echo off
REM Pure ASCII on purpose - see the launch .bat for why.
chcp 65001 >nul
title ExpoHub
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\update.ps1"
if errorlevel 1 pause
'@
Set-Content -Path (Join-Path $Pkg (([char]0x53CC + [char]0x51FB + [char]0x542F + [char]0x52A8) + '.bat')) -Value $batLaunch -Encoding ascii
Set-Content -Path (Join-Path $Pkg (([char]0x505C + [char]0x6B62 + [char]0x8FD0 + [char]0x884C) + '.bat')) -Value $batStop -Encoding ascii
Set-Content -Path (Join-Path $Pkg (([char]0x68C0 + [char]0x67E5 + [char]0x66F4 + [char]0x65B0) + '.bat')) -Value $batUpdate -Encoding ascii
Ok '三个入口 .bat 已生成（纯 ASCII）'

# .ps1 必须带 BOM —— 这些脚本里有中文
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'bom_fix.ps1') -Root $Pkg | Out-Null
Ok '包内 .ps1 已统一为 UTF-8 with BOM'

# ================================================================ 10. 打包
Step '打包 ZIP'
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'make_package.ps1') `
    -PkgPath $Pkg -ZipPath $ZipOut
if ($LASTEXITCODE -ne 0) { Die '打包失败' }

# ================================================================ 11. 自检
Step '产物自检'
$must = @(
    (Join-Path $Pkg (([char]0x53CC + [char]0x51FB + [char]0x542F + [char]0x52A8) + '.bat')),
    (Join-Path $Pkg (([char]0x505C + [char]0x6B62 + [char]0x8FD0 + [char]0x884C) + '.bat')),
    (Join-Path $Pkg (([char]0x68C0 + [char]0x67E5 + [char]0x66F4 + [char]0x65B0) + '.bat')),
    (Join-Path $Pkg (([char]0x4F7F + [char]0x7528 + [char]0x8BF4 + [char]0x660E) + '.docx')),
    (Join-Path $Runtime 'python.exe'),
    (Join-Path $Server 'portable_main.py'),
    (Join-Path $Server 'expohub.db'),
    (Join-Path $WebDir 'index.html')
)
$miss = $must | Where-Object { -not (Test-Path $_) }
if ($miss) { Die ("产物缺文件:`n     " + ($miss -join "`n     ")) }
Ok '必需文件齐全'

# 密钥泄漏检查：真实 API Key 绝不能被带进发给外人的包
$leak = Select-String -Path (Join-Path $Pkg '*'), (Join-Path $Server '*') `
        -Pattern 'sk-[A-Za-z0-9]{20,}', '[0-9a-f]{32}\.[A-Za-z0-9]{16}' -ErrorAction SilentlyContinue
if ($leak) {
    Write-Host '     ⚠️  疑似 API Key 出现在包内，请人工确认后再发出去：' -ForegroundColor Yellow
    $leak | Select-Object -First 5 | ForEach-Object { Write-Host "        $($_.Path):$($_.LineNumber)" }
} else {
    Ok '未发现 API Key 泄漏'
}

Write-Host ''
Write-Host '  ══════════════════════════════════════════════' -ForegroundColor Green
Ok "构建完成 → $ZipOut"
Info "体积 $([math]::Round((Get-Item $ZipOut).Length/1MB,2)) MB"
Write-Host ''
Write-Host '  发出去之前建议跑一遍验收测试：' -ForegroundColor DarkGray
Write-Host '    powershell -ExecutionPolicy Bypass -File portable\build\test_acceptance.ps1' -ForegroundColor DarkGray
Write-Host ''
