<#
.SYNOPSIS
    把已构建好的便携包目录打成 ZIP。

.DESCRIPTION
    ⚠️ 不要用 [ZipFile]::CreateFromDirectory。在 .NET Framework（PowerShell 5.1
    用的就是它）上，它写入的条目名用平台分隔符，也就是
        ExpoHub-试用版\runtime\python.exe
    ZIP 规范要求正斜杠。Windows 资源管理器勉强能解，但 7-Zip / Bandizip /
    WinRAR 以及所有非 Windows 解压器会解出一堆畸形文件名。
    所以这里手工建条目，强制 '/'，并让中文名带上 UTF-8 标志。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File make_package.ps1 `
        -PkgPath D:\out\ExpoHub-试用版 -ZipPath D:\out\ExpoHub-试用版.zip
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PkgPath,
    [Parameter(Mandatory = $true)][string]$ZipPath
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

if (-not (Test-Path $PkgPath)) {
    Write-Host "  [错误] 包目录不存在: $PkgPath" -ForegroundColor Red
    exit 1
}
$PkgPath = (Resolve-Path $PkgPath).Path

# 打包前清掉运行态残留
$logs = Join-Path $PkgPath 'logs'
if (Test-Path $logs) {
    Get-ChildItem $logs -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host '  已清空 logs/'
}
Get-ChildItem (Join-Path $PkgPath 'server') -Directory -Filter 'app.bak-*' -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force }
Remove-Item (Join-Path $logs 'server.pid') -Force -ErrorAction SilentlyContinue

$files = Get-ChildItem $PkgPath -Recurse -File
$rawMB = [math]::Round(($files | Measure-Object Length -Sum).Sum / 1MB, 2)
Write-Host "  files=$($files.Count)  uncompressed=${rawMB} MB"

# ---- 手工建 ZIP 条目（正斜杠）----
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
$zipDir = Split-Path $ZipPath -Parent
if ($zipDir -and -not (Test-Path $zipDir)) { New-Item -ItemType Directory -Force -Path $zipDir | Out-Null }

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$parent = Split-Path $PkgPath -Parent
$buf = New-Object byte[] 1048576
$count = 0
$sw = [Diagnostics.Stopwatch]::StartNew()

$archive = [System.IO.Compression.ZipFile]::Open($ZipPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($parent.Length + 1).Replace('\', '/')
        $entry = $archive.CreateEntry($rel, [System.IO.Compression.CompressionLevel]::Optimal)
        $in  = [IO.File]::OpenRead($f.FullName)
        $dst = $entry.Open()
        try {
            while (($n = $in.Read($buf, 0, $buf.Length)) -gt 0) { $dst.Write($buf, 0, $n) }
        } finally { $dst.Dispose(); $in.Dispose() }
        $count++
    }
    # 空目录也要保留（logs/ 否则解压后得靠启动脚本自己建）
    foreach ($d in (Get-ChildItem $PkgPath -Recurse -Directory | Where-Object {
                        @(Get-ChildItem $_.FullName -Force -Recurse -File).Count -eq 0 })) {
        $rel = $d.FullName.Substring($parent.Length + 1).Replace('\', '/') + '/'
        $archive.CreateEntry($rel) | Out-Null
    }
} finally { $archive.Dispose() }
$sw.Stop()

$zipMB = [math]::Round((Get-Item $ZipPath).Length / 1MB, 2)
Write-Host "  entries: $count files (+ empty dirs)  in $([math]::Round($sw.Elapsed.TotalSeconds,1))s"
Write-Host "  -> $ZipPath"
Write-Host "  ${zipMB} MB   ratio $([math]::Round(100 * $zipMB / $rawMB, 1))%"

# ---- 校验条目名规范 ----
$archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
    $all = $archive.Entries
    $bad = @($all | Where-Object { $_.FullName -like '*\*' })
    if ($bad.Count -eq 0) {
        Write-Host '  [OK] 条目名全为正斜杠' -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] $($bad.Count) 个条目用了反斜杠" -ForegroundColor Red
        exit 1
    }
    Write-Host "  total entries: $($all.Count)"
} finally { $archive.Dispose() }
