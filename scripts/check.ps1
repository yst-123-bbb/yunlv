<#
.SYNOPSIS
    本地检查脚本：lint + 格式检查 + 单元测试，任一失败即以非 0 退出。
.EXAMPLE
    pwsh -File scripts/check.ps1
#>
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    ruff check .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    ruff format --check .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    pytest
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

exit 0