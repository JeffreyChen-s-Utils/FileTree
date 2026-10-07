param(
    [Parameter(Mandatory=$true)][ValidateRange(1,2147483647)][int]$DiskNumber,
    [Parameter(Mandatory=$true)][ValidatePattern('^FT-[0-9a-f]{12}$')][string]$Label
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$disk = Get-Disk -Number $DiskNumber
if ($disk.IsBoot -or $disk.IsSystem -or $disk.PartitionStyle -ne 'RAW' -or
    $disk.NumberOfPartitions -ne 0 -or $disk.Size -ne 536870912 -or
    $disk.BusType -notin @('File Backed Virtual','FileBackedVirtual','Virtual')) {
    throw 'Refusing a nonempty, host, nonvirtual or incorrectly sized disk'
}
# The Python owner derived this number from its freshly created UUID's live native handle.
# Never search for disks by label/size or reuse an existing disk/partition.
$partition = $disk | Initialize-Disk -PartitionStyle GPT -PassThru |
    New-Partition -UseMaximumSize -AssignDriveLetter
$volume = $partition | Format-Volume -FileSystem NTFS -NewFileSystemLabel $Label -Confirm:$false
if ($volume.FileSystemType -ne 'NTFS' -or $volume.FileSystemLabel -ne $Label -or
    -not $partition.DriveLetter) {
    throw 'The newly formatted private partition did not receive its expected identity'
}
@{root=([string]$partition.DriveLetter + ':\'); label=$volume.FileSystemLabel;
    filesystem=[string]$volume.FileSystemType; volume_id=$volume.UniqueId} | ConvertTo-Json -Compress
