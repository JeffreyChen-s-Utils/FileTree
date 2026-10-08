# progress.md: FileTree

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed. Priority: **P1** next, **P2** worth doing, **P3** only if wanted.
Suggested order: #75 (account for the space), #76 (finish savings validation), then the P2 items.
Cross-repo and workspace items live in `D:\Codes\progress.md`.

## Open

- **#4** [UNVERIFIED] Verify file-manager selection/fallback, Trash behavior, Finder drag-to-scan source preservation, protected GUI duplicate-link approval, cross-volume fcopyfile/resource-fork verification and original-path symlink creation after approved Trash on macOS. No Mac or macOS VM is available from the owner for Finder interaction/consent.

### Safety

- **#89** (P2) [UNVERIFIED] Confirm complete wrapped recovery-summary text on native cocoa after estimate/width changes (`je_file_tree/gui/cleanup_review.py`) and inspect its CI screenshot evidence.

### Freeing space

- **#21** (P2) macOS bin querying/Finder-wide emptying remains blocked on a native environment; no Mac is available from the owner. Verify native macOS automation consent, APFS/firmlink scope deduplication, multi-volume coverage, active-operation lifetime and failed/partial metadata refresh; fixture/mocked execution does not prove native behavior.
- **#76** (P1) Confirm native phase evidence from `tools/validate_macos_volume.py` for APFS one/last/all hard-link names, compression, sparse files and clones, plus real cloud placeholders (fixtures do not prove actual placeholder allocation). Keep unmeasurable shared extents and directory metadata unknown; Windows no-bin outcomes remain unknown. Actual cloud placeholders need an unavailable provider environment. Drive reconciliation remains #75.

### Finding things



### Windows space explained


### Scanning

- **#33** (P3) Read the NTFS master file table directly (as WizTree does) when FileTree runs as administrator on a local NTFS volume: parse the `$MFT` (file records, attribute lists, `$FILE_NAME`, `$DATA` sizes and allocation, hard links, reparse points) in a new `je_file_tree/core/mft.py` and build the same `Node` tree, falling back to the normal scan on any other volume, without administrator rights, or on a parse error. Start after #36 has measured the normal scan on a full drive, and test against the normal scan of the same folders.
- **#35** (P2) [BLOCKED] Validate real UNC and mapped-drive scans: compare worker counts on slow links, allocation units on share roots, access-denied branches and a share disconnecting midway. No UNC share or mapped-drive test environment is available from the owner. Preserve incomplete coverage and confirm failures never create empty-folder clean-up proposals.
- **#75** (P1) Confirm native phase evidence from `tools/validate_macos_volume.py` on fresh APFS images, then finish shared-container/reservation cases and same-device mount boundaries on other POSIX systems. The GUI and CLI ledger remain estimates; independently unmeasurable shared/reserved/filesystem metadata, omitted bytes and other-volume totals stay unknown. Direct bin labels and Finder emptying remain #21.


### Over time

- **#38** (P3) [UNVERIFIED] Verify actual user-login startup and Windows/macOS notification display permission. Native registration fixtures do not prove a real login launch; notification dispatch does not prove OS permission. No owner login/macOS desktop validation environment is available; Windows display capture remains unverified.

### Everyday use


### Distribution


- **#47** (P2) [BLOCKED] Sign `FileTree.exe`: an unsigned one-file executable triggers SmartScreen and some antivirus programs. Waits on the owner getting a code-signing certificate or an Azure Trusted Signing account; then the release workflow's `build-exe` job signs the exe (`signtool` or the Trusted Signing action, pinned) with the credentials as repository secrets before uploading it.
- **#48** (P3) Finish store listings: a winget manifest (`wingetcreate` from the release workflow, with a token as a repository secret), a Scoop bucket and a Chocolatey package (an API key as a secret), plus an MSI built with WiX. Store-publishing tokens/accounts remain unavailable.
- **#49** (P2) Linux and macOS builds: an AppImage (or Flatpak) and a macOS `.app` from `tools/build_nuitka.py --app` built on CI runners and attached to the release, after #4 is verified.
- **#74** (P3) More languages: Japanese and Korean, each a table in `je_file_tree/gui/strings.py`, an entry in `i18n.LANGUAGES`, a Qt catalogue in `qt_translation.CATALOGUES`, a README translation and screenshots, if there are readers for them.

