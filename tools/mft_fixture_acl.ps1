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
$original = $acl.Sddl
if ($Action -eq 'Deny') {
    $everyone = [Security.Principal.SecurityIdentifier]::new('S-1-1-0')
    $rule = [Security.AccessControl.FileSystemAccessRule]::new(
        $everyone, [Security.AccessControl.FileSystemRights]::ListDirectory,
        [Security.AccessControl.AccessControlType]::Deny)
    $acl.AddAccessRule($rule)
} elseif ($Action -eq 'Restore') {
    if ([string]::IsNullOrWhiteSpace($Descriptor)) { throw 'Original descriptor is required.' }
    $original = $Descriptor
    $acl.SetSecurityDescriptorSddlForm($Descriptor, [Security.AccessControl.AccessControlSections]::Access)
}
if ($Action -ne 'Read') {
    $captured = [Security.AccessControl.RawSecurityDescriptor]::new($original)
    if ($captured.ControlFlags -band [Security.AccessControl.ControlFlags]::DiscretionaryAclAutoInherited) {
        Set-Acl -LiteralPath $Path -AclObject $acl
    } else {
        # Set-Acl converts legacy DACLs to automatic inheritance. Keep this owned fixture's original model.
        # The legacy API writes only this directory's DACL and never propagates it to children.
        Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class OwnedFixtureDacl {
    [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true, ExactSpelling = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetFileSecurityW(string path, uint information, byte[] descriptor);
    public static void Write(string path, byte[] descriptor) {
        if (!SetFileSecurityW(path, 4, descriptor)) {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }
    }
}
'@
        [OwnedFixtureDacl]::Write($Path, $acl.GetSecurityDescriptorBinaryForm())
    }
}
@{ descriptor = (Get-Acl -LiteralPath $Path).Sddl } | ConvertTo-Json -Compress
