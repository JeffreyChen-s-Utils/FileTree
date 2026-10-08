param(
    [Parameter(Mandatory = $true)][ValidateSet('Read', 'Deny', 'Restore')][string]$Action,
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$VolumeId,
    [string]$Descriptor = ''
)
$ErrorActionPreference = 'Stop'
if ($Path -notmatch '^[A-Z]:\\owned-fixtures\\denied-[0-9a-f]{32}$') {
    throw 'Only the fresh private-image denied fixture is accepted.'
}
if ($VolumeId -notmatch '^\\\\\?\\Volume\{[0-9A-Fa-f-]{36}\}\\$') { throw 'Invalid owned volume identity.' }
$volume = Get-CimInstance Win32_Volume -Filter "DriveLetter='$($Path.Substring(0, 2))'"
if ($volume.DeviceID -ne $VolumeId -or $volume.FileSystem -ne 'NTFS' -or $volume.Label -notmatch '^FT-[0-9a-f]{12}$') {
    throw 'Refusing an unrecognized private volume.'
}
$entry = Get-Item -LiteralPath $Path -Force
if (-not $entry.PSIsContainer -or ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'Refusing a redirected fixture.'
}
$acl = Get-Acl -LiteralPath $Path
if ($Action -eq 'Deny') {
    $everyone = [Security.Principal.SecurityIdentifier]::new('S-1-1-0')
    $rule = [Security.AccessControl.FileSystemAccessRule]::new(
        $everyone, [Security.AccessControl.FileSystemRights]::ListDirectory,
        [Security.AccessControl.AccessControlType]::Deny)
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $Path -AclObject $acl
} elseif ($Action -eq 'Restore') {
    if ([string]::IsNullOrWhiteSpace($Descriptor)) { throw 'Original descriptor is required.' }
    $acl.SetSecurityDescriptorSddlForm($Descriptor, [Security.AccessControl.AccessControlSections]::Access)
    Set-Acl -LiteralPath $Path -AclObject $acl
}
@{ descriptor = (Get-Acl -LiteralPath $Path).Sddl } | ConvertTo-Json -Compress
