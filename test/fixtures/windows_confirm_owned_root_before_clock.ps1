function Confirm-OwnedRoot([string]$root) {
    Write-DisconnectStep 'root-scope' 'started'
    $resolved = [IO.Path]::GetFullPath($root)
    $parent = [IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\')
    if ([IO.Path]::GetDirectoryName($resolved) -ne $parent -or
        [IO.Path]::GetFileName($resolved) -notmatch '^filetree-smb-[0-9a-f]{32}$') {
        throw 'Refusing an unowned SMB fixture root.'
    }
    Write-DisconnectStep 'root-scope' 'completed'
    $entryNumber = 0
    foreach ($path in @($parent, $resolved, (Join-Path $resolved 'owner.json'), (Join-Path $resolved 'sources'))) {
        $entryNumber += 1
        Write-DisconnectStep ('owned-entry-' + $entryNumber) 'started'
        $entry = Get-Item -LiteralPath $path -Force
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Redirected SMB fixture refused.' }
        Write-DisconnectStep ('owned-entry-' + $entryNumber) 'completed'
    }
    Write-DisconnectStep 'owner-receipt' 'started'
    $receipt = Get-Content -LiteralPath (Join-Path $resolved 'owner.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($receipt.root -ne $resolved -or $receipt.sid -ne $identity.User.Value -or
        $receipt.share -ne ('ftscan-' + [IO.Path]::GetFileName($resolved).Substring(13))) {
        throw 'SMB fixture receipt differs.'
    }
    Write-DisconnectStep 'owner-receipt' 'completed'
    return $receipt
}
