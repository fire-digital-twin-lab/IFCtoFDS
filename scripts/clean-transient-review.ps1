param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$cacheRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot '.cache'))
# Exact, reviewed transient outputs only. Current conversion evidence, caches,
# reference cases, source IFCs and the test suite are intentionally retained.
$names = @(
    'ui-baseline-preview', 'ui-improved-preview', 'ui-shared-preview',
    'ui-preview-cold-cache', 'ui-preview-warm-cache', 'pytest-complete-final',
    'pytest-evidence-final', 'pytest-jobs-final', 'pytest-recovery',
    'pytest-recovery-final', 'pytest-reference-exact', 'pytest-reference-local',
    'pytest-solver-final', 'pytest-targeted', 'pytest-unit-final',
    'pytest-unit-final2', 'pytest-unit-final3', 'tang7-cached-proofs.prof',
    'tang7-convert-local.prof', 'tang7-convert.prof'
)
$targets = @()
foreach ($name in $names) {
    $candidate = Join-Path $cacheRoot $name
    if (-not (Test-Path -LiteralPath $candidate)) { continue }
    $item = Get-Item -LiteralPath $candidate
    $resolved = (Resolve-Path -LiteralPath $candidate).Path
    if (-not $resolved.StartsWith($cacheRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Outside intended cache directory: $resolved"
    }
    $members = @($item)
    if ($item.PSIsContainer) { $members += @(Get-ChildItem -LiteralPath $resolved -Recurse -Force) }
    if ($members | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) {
        throw "Refusing directory containing a filesystem link: $resolved"
    }
    $files = @($members | Where-Object { -not $_.PSIsContainer })
    $targets += [PSCustomObject]@{path=$resolved;files=$files.Count;bytes=($files | Measure-Object Length -Sum).Sum}
}
$targets | Format-Table -AutoSize
if ($Apply) {
    foreach ($target in $targets) { Remove-Item -LiteralPath $target.path -Recurse -Force }
    Write-Output "Removed $($targets.Count) reviewed transient targets."
} else {
    Write-Output 'Preview only. Use -Apply to delete exactly these transient targets.'
}
