param(
    [Parameter(Mandatory)][string]$Files,
    [Parameter(Mandatory)][string]$ExpectedPublisher,
    [switch]$CheckPathsOnly
)
$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd([char[]]'\/')
$paths = @($Files -split '[,\r\n]+' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($paths.Count -lt 1 -or $paths.Count -gt 3) { throw 'Expected one to three exact release-signing files.' }
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($path in $paths) {
    if (-not [IO.Path]::IsPathFullyQualified($path)) { throw 'Signing paths must be absolute.' }
    $fullPath = [IO.Path]::GetFullPath($path)
    $relative = [IO.Path]::GetRelativePath($repository, $fullPath).Replace('\', '/')
    $allowed = $relative -ceq 'build/onefile/FileTree.exe' -or
               $relative -ceq 'build/standalone/start_file_tree.dist/FileTree.exe' -or
               $relative -cmatch '^FileTree-[0-9]+\.[0-9]+\.[0-9]+-windows-x64\.msi$'
    if (-not $allowed -or -not $seen.Add($fullPath)) { throw 'Unexpected or duplicate release-signing path.' }
    $item = Get-Item -LiteralPath $fullPath -Force
    if ($item.PSIsContainer) { throw 'Release signing requires a regular file.' }
    $current = $item
    while ($null -ne $current) {
        if ($current.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked signing path refused.' }
        if ($current.FullName -eq $repository) { break }
        $current = if ($current -is [IO.DirectoryInfo]) { $current.Parent } else { $current.Directory }
    }
    if ($null -eq $current) { throw 'Signing file is outside the repository.' }
    if (-not $CheckPathsOnly) {
        $signature = Get-AuthenticodeSignature -LiteralPath $fullPath
        if ($signature.Status -ne 'Valid' -or $null -eq $signature.SignerCertificate -or
            $null -eq $signature.TimeStamperCertificate -or
            $signature.SignerCertificate.Subject -cne $ExpectedPublisher) {
            throw 'Release signature, timestamp, trust or expected publisher verification failed.'
        }
    }
}
if ($CheckPathsOnly) { 'Exact release-signing paths checked.' } else { 'Release signatures verified.' }
