<#
.SYNOPSIS
    把目录下所有 .ps1 统一重编码为 UTF-8 with BOM。

.DESCRIPTION
    PowerShell 5.1 按 ANSI(GBK) 读无 BOM 的脚本，含中文的脚本会全部乱码
    并引发语法解析失败。而大多数编辑器/工具（包括 AI 写文件）默认输出的是
    无 BOM 的 UTF-8，所以每次改动后都该跑一遍这个。

    构建脚本在打包收尾时会自动调用它，一般不需要手工执行。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File portable\build\bom_fix.ps1 -Root portable
    把 portable\ 下所有 .ps1 转成带 BOM。
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Root
)

if (-not (Test-Path $Root)) {
    Write-Host "  [错误] 目录不存在: $Root" -ForegroundColor Red
    exit 1
}

$bom   = New-Object System.Text.UTF8Encoding($true)
$noBom = New-Object System.Text.UTF8Encoding($false)
$n = 0

Get-ChildItem $Root -Recurse -Include *.ps1 -File | ForEach-Object {
    $text = [IO.File]::ReadAllText($_.FullName, $noBom)
    [IO.File]::WriteAllText($_.FullName, $text, $bom)
    $hex = (([IO.File]::ReadAllBytes($_.FullName)[0..2]) | ForEach-Object { $_.ToString('X2') }) -join ' '
    if ($hex -eq 'EF BB BF') {
        Write-Host "  OK  $($_.Name)"
        $n++
    } else {
        Write-Host "  !!  $($_.Name)  BOM=$hex" -ForegroundColor Red
    }
}

Write-Host "  已处理 $n 个 .ps1"
