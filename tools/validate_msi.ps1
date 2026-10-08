param([switch]$DisposableRunner, [switch]$CompiledPayload)
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
New-Item -ItemType Directory -Path $build | Out-Null
$payload = Join-Path $build 'fixture.dist'
function New-FixturePayload {
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
}
function Read-OwnedInventory([string]$root) {
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push($root)
    $inventory = @{}
    while ($pending.Count -gt 0) {
        $current = $pending.Pop()
        $item = Get-Item -LiteralPath $current -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Payload contains a link.' }
        $relative = [IO.Path]::GetRelativePath($root, $current)
        if ($item.PSIsContainer) {
            $inventory[$relative] = '<directory>'
            foreach ($child in Get-ChildItem -LiteralPath $current -Force) { $pending.Push($child.FullName) }
        } else {
            $inventory[$relative] = (Get-FileHash -LiteralPath $current -Algorithm SHA256).Hash
        }
    }
    return $inventory
}
function Confirm-Inventory([string]$root, [hashtable]$expected) {
    $actual = Read-OwnedInventory $root
    if ($actual.Count -ne $expected.Count) { throw 'Payload inventory has missing or unexpected entries.' }
    foreach ($relative in $expected.Keys) {
        if (-not $actual.ContainsKey($relative) -or $actual[$relative] -ne $expected[$relative]) {
            throw "Payload differs: $relative"
        }
    }
}
function Copy-CompiledPayload {
    $sourceBuild = Join-Path $env:GITHUB_WORKSPACE 'build/standalone'
    foreach ($directory in @((Join-Path $env:GITHUB_WORKSPACE 'build'), $sourceBuild)) {
        if ((Get-Item -LiteralPath $directory).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'Compiled source ancestors contain a link.'
        }
    }
    $folders = @(Get-ChildItem -LiteralPath $sourceBuild -Directory -Filter '*.dist')
    if ($folders.Count -ne 1) { throw 'Expected one owned compiled standalone folder.' }
    $script:compiledRoot = $folders[0].FullName
    $script:originalInventory = Read-OwnedInventory $compiledRoot
    foreach ($relative in $originalInventory.Keys) {
        $destination = Join-Path $payload $relative
        if ($originalInventory[$relative] -eq '<directory>') {
            New-Item -ItemType Directory -Path $destination -Force | Out-Null
        } else {
            New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
            Copy-Item -LiteralPath (Join-Path $compiledRoot $relative) -Destination $destination
        }
    }
    Confirm-Inventory $payload $originalInventory
    Confirm-Inventory $compiledRoot $originalInventory
    if (-not $originalInventory.ContainsKey('FileTree.exe')) { throw 'Compiled FileTree.exe missing.' }
    foreach ($required in @('Qt6Core.dll', 'qwindows.dll', 'qtbase_zh_TW.qm', 'qtbase_zh_CN.qm')) {
        $matches = @($originalInventory.Keys | Where-Object { [IO.Path]::GetFileName($_) -eq $required })
        if ($matches.Count -ne 1) { throw "Compiled runtime incomplete or ambiguous: $required" }
    }
}
if ($CompiledPayload) {
    # Copy into a separate fresh payload; the compiler output is never edited or launched.
    $payload = Join-Path $build 'compiled.dist'
    New-Item -ItemType Directory -Path $payload | Out-Null
    Copy-CompiledPayload
} else { New-FixturePayload }
$payloadInventory = Read-OwnedInventory $payload
$evidence = @{ phase = 'starting'; fixture_only = (-not $CompiledPayload); compiled_payload = [bool]$CompiledPayload;
               app_launched = $false; cleanup_verified = $false }
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
function Confirm-OwnedPayload {
    Confirm-Inventory $installRoot $payloadInventory
    Confirm-Inventory $payload $payloadInventory
    if (-not (Test-Path -LiteralPath $shortcut)) { throw 'Owned Start-menu shortcut missing.' }
    if ($CompiledPayload) {
        Confirm-Inventory $compiledRoot $originalInventory
    }
}
$attempted = $false
try {
    Save-Proof
    python tools/build_msi.py --version 1.2.3 --source $build --output $scratch
    if ($LASTEXITCODE -ne 0) { throw 'MSI fixture compilation failed.' }
    $msi = Join-Path $scratch 'FileTree-1.2.3-windows-x64.msi'
    $msiHash = (Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash
    python tools/package_standalone.py --version 1.2.3 --source $build --output $scratch
    if ($LASTEXITCODE -ne 0) { throw 'Owned package review archive failed.' }
    $drafts = Join-Path $scratch 'package-drafts'
    python tools/prepare_packages.py --version 1.2.3 --source $scratch --output $drafts
    if ($LASTEXITCODE -ne 0) { throw 'Owned package review drafts failed.' }
    $evidence.package_drafts_prepared = $true
    $evidence.package_provenance = Get-Content -LiteralPath (Join-Path $drafts 'provenance.json') -Raw |
        ConvertFrom-Json -AsHashtable
    $evidence.phase = 'installing'
    Save-Proof
    $attempted = $true
    Invoke-OwnedInstaller '/i' 'install.log'
    Confirm-OwnedPayload
    $evidence.phase = 'upgrading'
    Save-Proof
    $changedName = if ($CompiledPayload) { 'installer-validation.txt' } else { 'Qt6Core.dll' }
    $changedFile = Join-Path $payload $changedName
    [IO.File]::WriteAllBytes($changedFile, [Text.Encoding]::UTF8.GetBytes('owned upgraded library fixture'))
    $payloadInventory[$changedName] = (Get-FileHash -LiteralPath $changedFile -Algorithm SHA256).Hash
    python tools/build_msi.py --version 1.2.4 --source $build --output $scratch
    if ($LASTEXITCODE -ne 0) { throw 'MSI upgrade fixture compilation failed.' }
    $msi = Join-Path $scratch 'FileTree-1.2.4-windows-x64.msi'
    $msiHash = (Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash
    Invoke-OwnedInstaller '/i' 'upgrade.log'
    Confirm-OwnedPayload
    $products = @($installer.RelatedProducts($upgradeCode))
    if ($products.Count -ne 1 -or $installer.ProductInfo($products[0], 'VersionString') -ne '1.2.4') {
        throw 'Owned major upgrade did not leave exactly the expected new product.'
    }
    $evidence.upgrade_verified = $true
    $evidence.installed_files = @($payloadInventory.Values | Where-Object { $_ -ne '<directory>' }).Count
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
