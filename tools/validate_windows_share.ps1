param(
    [switch]$DisposableRunner,
    [switch]$DisconnectOnly,
    [string]$FixtureRoot = '',
    [string]$Output = 'windows-share.json'
)
$ErrorActionPreference = 'Stop'
if (-not $DisposableRunner -or $env:GITHUB_ACTIONS -ne 'true' -or
    $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:RUNNER_OS -ne 'Windows') {
    throw 'SMB validation requires an explicit disposable hosted Windows runner.'
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Administrator fixture runner required; no elevation is requested.'
}
function Confirm-OwnedRoot([string]$root) {
    $resolved = [IO.Path]::GetFullPath($root)
    $parent = [IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\')
    if ([IO.Path]::GetDirectoryName($resolved) -ne $parent -or
        [IO.Path]::GetFileName($resolved) -notmatch '^filetree-smb-[0-9a-f]{32}$') {
        throw 'Refusing an unowned SMB fixture root.'
    }
    foreach ($path in @($parent, $resolved, (Join-Path $resolved 'owner.json'), (Join-Path $resolved 'sources'))) {
        $entry = Get-Item -LiteralPath $path -Force
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Redirected SMB fixture refused.' }
    }
    $receipt = Get-Content -LiteralPath (Join-Path $resolved 'owner.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($receipt.root -ne $resolved -or $receipt.sid -ne $identity.User.Value -or
        $receipt.share -ne ('ftscan-' + [IO.Path]::GetFileName($resolved).Substring(13))) {
        throw 'SMB fixture receipt differs.'
    }
    return $receipt
}
function Remove-OwnedShare([string]$root) {
    $receipt = Confirm-OwnedRoot $root
    $share = Get-SmbShare -Name $receipt.share -ErrorAction SilentlyContinue
    if ($null -ne $share) {
        if ($share.Path -ne (Join-Path $receipt.root 'sources') -or $share.Special) {
            throw 'SMB share ownership changed; refusing removal.'
        }
        Remove-SmbShare -Name $receipt.share -Force -Confirm:$false
    }
}
if ($DisconnectOnly) {
    $receipt = Confirm-OwnedRoot $FixtureRoot
    if ($null -eq (Get-SmbShare -Name $receipt.share -ErrorAction SilentlyContinue)) {
        throw 'Disconnect fixture share is already absent.'
    }
    Remove-OwnedShare $FixtureRoot
    exit 0
}
if ($FixtureRoot) { throw 'Existing fixture roots are not accepted for setup.' }
$token = [guid]::NewGuid().ToString('N')
$scratch = [IO.Path]::GetFullPath((Join-Path $env:RUNNER_TEMP ('filetree-smb-' + $token)))
$shareName = 'ftscan-' + $token
$unc = '\\localhost\' + $shareName
if ((Test-Path -LiteralPath $scratch) -or (Get-SmbShare -Name $shareName -ErrorAction SilentlyContinue)) {
    throw 'Refusing an existing fixture directory or share.'
}
$letter = @('Z', 'Y', 'X', 'W', 'V', 'U', 'T') | Where-Object {
    -not (Test-Path -LiteralPath ($_ + ':\')) -and
    -not (Get-SmbMapping -LocalPath ($_ + ':') -ErrorAction SilentlyContinue) -and
    -not (Get-PSDrive -Name $_ -ErrorAction SilentlyContinue)
} | Select-Object -First 1
if (-not $letter) { throw 'No unused fixture mapping letter; existing mappings are never replaced.' }
$mapping = $letter + ':'
$mapped = $false
$created = $false
$denied = $null
$originalAcl = $null
$proof = [ordered]@{ phase = 'started'; transport = 'native SMB loopback'; slow_remote_link_verified = $false }
function Save-Proof {
    $proof | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $Output -Encoding UTF8
}
function Invoke-Probe([string]$mode) {
    $result = & python tools/windows_share_probe.py --mode $mode --owned $scratch --unc $unc --mapped ($mapping + '\')
    if ($LASTEXITCODE -ne 0) { throw "Native SMB $mode validation failed." }
    $proof[$mode] = ($result | ConvertFrom-Json)
    $proof.phase = $mode
    Save-Proof
}
Save-Proof
try {
    New-Item -ItemType Directory -Path $scratch | Out-Null
    $created = $true
    New-Item -ItemType Directory -Path (Join-Path $scratch 'sources') | Out-Null
    @{ root = $scratch; share = $shareName; sid = $identity.User.Value } | ConvertTo-Json |
        Set-Content -LiteralPath (Join-Path $scratch 'owner.json') -Encoding UTF8
    Invoke-Probe 'prepare'
    New-SmbShare -Name $shareName -Path (Join-Path $scratch 'sources') -ReadAccess $identity.Name | Out-Null
    New-SmbMapping -LocalPath $mapping -RemotePath $unc -Persistent $false | Out-Null
    $mapped = $true
    Invoke-Probe 'compare'
    $denied = Join-Path $scratch 'sources/denied'
    $originalAcl = Get-Acl -LiteralPath $denied
    $changedAcl = Get-Acl -LiteralPath $denied
    $changedAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
        [Security.Principal.SecurityIdentifier]::new('S-1-1-0'),
        [Security.AccessControl.FileSystemRights]::ListDirectory, [Security.AccessControl.AccessControlType]::Deny))
    try {
        Set-Acl -LiteralPath $denied -AclObject $changedAcl
        Invoke-Probe 'denied'
    } finally {
        Set-Acl -LiteralPath $denied -AclObject $originalAcl
        if ((Get-Acl -LiteralPath $denied).Sddl -ne $originalAcl.Sddl) { throw 'Owned DACL was not restored exactly.' }
        $proof.acl_restored = $true
        $originalAcl = $null
        Save-Proof
    }
    Invoke-Probe 'disconnect'
    Invoke-Probe 'verify'
    $proof.phase = 'verified'
    Save-Proof
} catch {
    $proof.phase = 'failed'
    $proof.error = $_.Exception.Message
    Save-Proof
    throw
} finally {
    if ($created) {
        if ($null -ne $originalAcl) { Set-Acl -LiteralPath $denied -AclObject $originalAcl }
        $receipt = Confirm-OwnedRoot $scratch
        $existing = Get-SmbMapping -LocalPath $mapping -ErrorAction SilentlyContinue
        if ($null -ne $existing) {
            if (-not $mapped -or $existing.RemotePath -ne $unc) { throw 'Changed SMB mapping; cleanup refused.' }
            Remove-SmbMapping -LocalPath $mapping -Force -Confirm:$false
        }
        Remove-OwnedShare $scratch
        # Check every owned entry before recursive cleanup; never cross a reparse point.
        $pending = [Collections.Generic.Stack[string]]::new()
        $pending.Push($receipt.root)
        while ($pending.Count) {
            $path = $pending.Pop()
            $entry = Get-Item -LiteralPath $path -Force
            if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked cleanup entry refused.' }
            if ($entry.PSIsContainer) {
                foreach ($child in Get-ChildItem -LiteralPath $path -Force) { $pending.Push($child.FullName) }
            }
        }
        Remove-Item -LiteralPath $receipt.root -Recurse -Force
        $proof.owned_fixture_cleanup = $true
        if ($proof.phase -eq 'verified') { $proof.phase = 'complete' }
        Save-Proof
    }
}
