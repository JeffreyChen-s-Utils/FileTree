param([switch]$DisposableRunner)
$ErrorActionPreference = 'Stop'
if (-not $DisposableRunner -or $env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') {
    throw 'MSI installation validation requires an explicit disposable hosted Windows runner.'
}
$installRoot = Join-Path $env:ProgramFiles 'FileTree'
$shortcut = Join-Path $env:ProgramData 'Microsoft/Windows/Start Menu/Programs/FileTree.lnk'
$installer = New-Object -ComObject WindowsInstaller.Installer
$upgradeCode = '{1CF91EA0-1ED2-45CB-B2FC-A6F321F67B73}'
$related = @($installer.RelatedProducts($upgradeCode))
if ((Test-Path -LiteralPath $installRoot) -or (Test-Path -LiteralPath $shortcut) -or $related.Count -gt 0) {
    throw 'Existing FileTree installation/shortcut/product found; refusing installer validation.'
}
$scratch = Join-Path $env:RUNNER_TEMP ('filetree-msi-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $scratch | Out-Null
$build = Join-Path $scratch 'build'
$payload = Join-Path $build 'fixture.dist'
New-Item -ItemType Directory -Path (Join-Path $payload 'PySide6/translations') -Force | Out-Null
# A native PE and small runtime fixtures prove installer behavior, not a compiled FileTree launch.
Copy-Item -LiteralPath (Join-Path $env:SystemRoot 'System32/where.exe') -Destination (Join-Path $payload 'FileTree.exe')
[IO.File]::WriteAllBytes((Join-Path $payload 'Qt6Core.dll'), [Text.Encoding]::UTF8.GetBytes('owned library fixture'))
foreach ($name in @('qtbase_zh_TW.qm', 'qtbase_zh_CN.qm')) {
    [IO.File]::WriteAllBytes((Join-Path $payload ('PySide6/translations/' + $name)),
                           [Text.Encoding]::UTF8.GetBytes('owned catalogue fixture'))
}
New-Item -ItemType Directory -Path (Join-Path $payload 'PySide6/plugins/platforms') -Force | Out-Null
[IO.File]::WriteAllBytes((Join-Path $payload 'PySide6/plugins/platforms/qwindows.dll'),
                       [Text.Encoding]::UTF8.GetBytes('owned platform fixture'))
$fixtureFiles = @(Get-ChildItem -LiteralPath $payload -Recurse -File)
$hashes = @{}
foreach ($file in $fixtureFiles) {
    $relative = [IO.Path]::GetRelativePath($payload, $file.FullName)
    $hashes[$relative] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
}
$evidence = @{ phase = 'starting'; fixture_only = $true; cleanup_verified = $false }
$proofPath = Join-Path $scratch 'msi-proof.json'
function Save-Proof {
    [IO.File]::WriteAllText($proofPath, ($evidence | ConvertTo-Json -Depth 6), [Text.UTF8Encoding]::new($false))
    Copy-Item -LiteralPath $proofPath -Destination 'msi-proof.json'
}
function Invoke-OwnedInstaller([string]$operation, [string]$logName) {
    if ((Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash -ne $msiHash) {
        throw 'Owned MSI changed; refusing installer action.'
    }
    $arguments = @($operation, ('"' + $msi + '"'), '/qn', '/norestart', '/l*v',
                   ('"' + (Join-Path $scratch $logName) + '"'))
    $process = Start-Process -FilePath (Join-Path $env:SystemRoot 'System32/msiexec.exe') `
        -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -notin @(0, 3010)) { throw "Owned MSI operation failed: $($process.ExitCode)" }
}
$attempted = $false
try {
    Save-Proof
    python tools/build_msi.py --version 1.2.3 --source $build --output $scratch
    if ($LASTEXITCODE -ne 0) { throw 'MSI fixture compilation failed.' }
    $msi = Join-Path $scratch 'FileTree-1.2.3-windows-x64.msi'
    $msiHash = (Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash
    $evidence.phase = 'installing'
    Save-Proof
    $attempted = $true
    Invoke-OwnedInstaller '/i' 'install.log'
    foreach ($relative in $hashes.Keys) {
        $installed = Join-Path $installRoot $relative
        $item = Get-Item -LiteralPath $installed
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            (Get-FileHash -LiteralPath $installed -Algorithm SHA256).Hash -ne $hashes[$relative]) {
            throw "Installed fixture differs: $relative"
        }
        if ((Get-FileHash -LiteralPath (Join-Path $payload $relative) -Algorithm SHA256).Hash -ne $hashes[$relative]) {
            throw "Installer changed source fixture: $relative"
        }
    }
    if (-not (Test-Path -LiteralPath $shortcut)) { throw 'Owned Start-menu shortcut missing.' }
    $evidence.installed_files = $hashes.Count
    $evidence.shortcut_verified = $true
    $evidence.source_preserved = $true
    $evidence.phase = 'validated'
    Save-Proof
} catch {
    $evidence.phase = 'failed'
    $evidence.error = $_.Exception.Message
    throw
} finally {
    try {
        if ($attempted) { Invoke-OwnedInstaller '/x' 'uninstall.log' }
        if ((Test-Path -LiteralPath $installRoot) -or (Test-Path -LiteralPath $shortcut) -or
            @($installer.RelatedProducts($upgradeCode)).Count -gt 0) {
            throw 'Owned installation was not completely removed.'
        }
        $evidence.cleanup_verified = $true
        if ($evidence.phase -eq 'validated') { $evidence.phase = 'complete' }
    } finally {
        Save-Proof
        Get-ChildItem -LiteralPath $scratch -Filter '*.log' -File | Copy-Item -Destination .
    }
}
