# progress.md: FileTree

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed. Priority: **P1** next, **P2** worth doing, **P3** only if wanted.
Suggested order: #75 (account for the space), #76 (finish savings validation), then the P2 items.
Cross-repo and workspace items live in `D:\Codes\progress.md`.

## Open

- **#4** [BLOCKED] Verify file-manager selection/fallback, Trash behavior, drag-to-scan source preservation, CJK rendering, native duplicate hard-link execution/metadata and cross-volume fcopyfile/resource-fork verification and original-path symlink creation after approved Trash on macOS; no Mac or macOS VM is available from the owner.

### Safety


### Freeing space

- **#21** (P2) macOS bin querying/Finder-wide emptying remains blocked on a native environment; no Mac is available from the owner. Verify native macOS automation consent, APFS/firmlink scope deduplication, multi-volume coverage, active-operation lifetime and failed/partial metadata refresh; fixture/mocked execution does not prove native behavior.
- **#76** (P1) Finish actual per-case free recovery on isolated NTFS/APFS volumes for one/all hard-link names, compression and sparse files, plus real cloud placeholders (fixtures do not prove actual placeholder allocation). Keep unmeasurable shared extents and directory metadata unknown. Extend `tools/validate_windows_volume.py` on the administrator Windows CI runner; local administrator access is unavailable. APFS needs a Mac and actual cloud placeholders need a provider environment. Drive reconciliation remains #75.

### Finding things



### Windows space explained

- **#59** (P2) Integrate `core.virtual_disk_compaction` with explicit default-No GUI review, durable approval/outcome audit, existing administrator restart, joined lifetime and fresh rescan after every attempted writable operation. Explain the literal path, fixed native zero-block backend, stopped-machine requirement and partial/unknown/zero savings; guest-used bytes stay unknown. Unsupported VMDK/VDI/QCOW2 need a suitable fixed backend before execution. Verify populated owned private disks and guest-data preservation on an administrator Windows CI runner without touching existing user disks.

### Scanning

- **#31** (P2) Several folders in one scan: scan a list of roots (for example every drive) under one virtual root, so the charts and lists cover them together; the welcome page (`je_file_tree/gui/welcome.py:22` lists the drives already) gets *Scan all drives*. The virtual root has no path: `Node.path`, the exports and the saved-scan format (`core/compare.py`) must handle it.
- **#33** (P3) Read the NTFS master file table directly (as WizTree does) when FileTree runs as administrator on a local NTFS volume: parse the `$MFT` (file records, attribute lists, `$FILE_NAME`, `$DATA` sizes and allocation, hard links, reparse points) in a new `je_file_tree/core/mft.py` and build the same `Node` tree, falling back to the normal scan on any other volume, without administrator rights, or on a parse error. Start after #36 has measured the normal scan on a full drive, and test against the normal scan of the same folders.
- **#34** (P2) Follow changes: watch the scanned tree and rescan only the folders that changed, so the numbers stay true without a full rescan. `QFileSystemWatcher` watches each folder separately and does not scale to a whole drive; the USN change journal (Windows) or inotify/fanotify (Linux) do. Reuses the branch rescan (`FolderTreeModel.replace`).
- **#35** (P2) [BLOCKED] Validate real UNC and mapped-drive scans: compare worker counts on slow links, allocation units on share roots, access-denied branches and a share disconnecting midway. No UNC share or mapped-drive test environment is available from the owner. Preserve incomplete coverage and confirm failures never create empty-folder clean-up proposals.
- **#75** (P1) Finish capacity-ledger validation on isolated APFS volumes against OS capacity/bin attribution, allocation estimates, shared extents and reserved capacity. Verify same-device mount boundaries on other POSIX systems. APFS requires a Mac. The GUI and CLI ledger remain estimates; independently unmeasurable shared/reserved/filesystem metadata, omitted bytes and other-volume totals stay unknown. Reconcile macOS bin attribution with OS queries; direct bin labels and emptying remain #21.


### Over time

- **#38** (P3) Background monitor, off until turned on in Options: a tray icon that stays when the window closes, warns (a system notification) when a drive falls below a free-space threshold (10 % by default) and runs scheduled scans of chosen folders for #37 (gentle priority, #63). Optionally starts with the system (Windows `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, a Linux autostart `.desktop` file, a macOS LaunchAgent), always removable from the same place.
- **#86** (P2) Reviewable recurring clean-up: combine #37's scan history with the policy in #81 to show “new junk since last scan” and “largest new growth” per drive; a scheduled scan may prepare a dated proposal but never move anything automatically. The proposal records the scan coverage and rule version, expires when paths change, and opens the same review queue as #77. Test that a missed schedule, stale scan or changed rule cannot silently turn an old proposal into an action.

### Everyday use

- **#69** (P3) Several scans at once: result tabs, each its own scan, to look at two drives side by side; the window's single `ResultsView` becomes one per tab, with the scan worker per tab.

### Distribution


- **#47** (P2) [BLOCKED] Sign `FileTree.exe`: an unsigned one-file executable triggers SmartScreen and some antivirus programs. Waits on the owner getting a code-signing certificate or an Azure Trusted Signing account; then the release workflow's `build-exe` job signs the exe (`signtool` or the Trusted Signing action, pinned) with the credentials as repository secrets before uploading it.
- **#48** (P3) Updates and store listings. Update check: once a day at most, ask PyPI (`https://pypi.org/pypi/je_file_tree/json`) for the latest version and show a notice with a link; can be turned off in Options, and it is FileTree's first network call, so the README says so. Store listings, now that the repository and its release files are public: a winget manifest (`wingetcreate` from the release workflow, with a token as a repository secret), a Scoop bucket and a Chocolatey package (an API key as a secret), plus an MSI built with WiX.
- **#49** (P2) Linux and macOS builds: an AppImage (or Flatpak) and a macOS `.app` from `tools/build_nuitka.py --app` built on CI runners and attached to the release, after #4 is verified.
- **#74** (P3) More languages: Japanese and Korean, each a table in `je_file_tree/gui/strings.py`, an entry in `i18n.LANGUAGES`, a Qt catalogue in `qt_translation.CATALOGUES`, a README translation and screenshots, if there are readers for them.

