# progress.md: FileTree

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed. Priority: **P1** next, **P2** worth doing, **P3** only if wanted.
Suggested order: #75 (account for the space), #76 (finish savings validation), then the P2 items.
Cross-repo and workspace items live in `D:\Codes\progress.md`.

## Open

- **#4** [UNVERIFIED] Verify file-manager selection/fallback, Trash behavior, Finder drag-to-scan source preservation, protected GUI duplicate-link approval and original-path symlink creation after approved Trash on macOS. No Mac or macOS VM is available from the owner for Finder interaction/consent.

### Safety


### Freeing space

- **#21** (P2) macOS bin querying/Finder-wide emptying remains blocked on a native environment; no Mac is available from the owner. Verify native macOS automation consent, APFS/firmlink scope deduplication, multi-volume coverage, active-operation lifetime and failed/partial metadata refresh; fixture/mocked execution does not prove native behavior.
- **#76** (P1) [BLOCKED] Validate actual cloud placeholders with a real provider environment (unavailable from the owner); fixtures do not prove provider allocation. Keep unmeasurable shared extents and directory metadata unknown; Windows no-bin outcomes remain unknown. Drive reconciliation remains #75.

### Finding things



### Windows space explained


### Scanning

- **#33** (P3) Validate the off-by-default `ScanOptions.experimental_mft` audit with native DACL/Node/options/cancellation/fallback parity and same-folder/full-drive performance baselines before default enabling. Raw records never override ordinary directory visibility or no-follow path authority; preserve allocation estimates, hard links, reparse boundaries and incomplete coverage. The serial audit makes no speed claim.
- **#35** (P2) [BLOCKED] Validate real UNC and mapped-drive scans: compare worker counts on slow links, allocation units on share roots, access-denied branches and a share disconnecting midway. No UNC share or mapped-drive test environment is available from the owner. Preserve incomplete coverage and confirm failures never create empty-folder clean-up proposals.
- **#75** (P1) Verify same-device mount boundaries on macOS/other POSIX with native traversal guards; FreeBSD nullfs has a distinct st_dev and cannot prove that case. Unmounted APFS peer capacity remains unknown. The GUI and CLI ledger remain estimates; independently unmeasurable shared/reserved/filesystem metadata, omitted bytes and other-volume totals stay unknown. Direct bin labels and Finder emptying remain #21.


### Over time

- **#38** (P3) [UNVERIFIED] Verify actual user-login startup and Windows/macOS notification display permission. Native registration fixtures do not prove a real login launch; notification dispatch does not prove OS permission. No owner login/macOS desktop validation environment is available; Windows display capture remains unverified.

### Everyday use


### Distribution


- **#47** (P2) [BLOCKED] Sign `FileTree.exe`: an unsigned one-file executable triggers SmartScreen and some antivirus programs. Waits on the owner getting a code-signing certificate or an Azure Trusted Signing account; then the release workflow's `build-exe` job signs the exe (`signtool` or the Trusted Signing action, pinned) with the credentials as repository secrets before uploading it.
- **#48** (P3) [BLOCKED] Submit reviewed winget/Scoop/Chocolatey drafts for the exact published release artifacts and verify real store installation/upgrades. Store-publishing tokens/accounts remain unavailable from the owner.
- **#49** (P2) Inspect complete native macOS bundle compilation and extraction/source-preservation evidence after the ICNS conversion fix in Desktop builds CI. Release attachment remains gated by #4 verification and `FILETREE_POSIX_RELEASE_VERIFIED`; owner Finder/consent validation is unavailable. Developer ID signing/notarization remains unavailable.
- **#74** (P3) More languages: Japanese and Korean, each a table in `je_file_tree/gui/strings.py`, an entry in `i18n.LANGUAGES`, a Qt catalogue in `qt_translation.CATALOGUES`, a README translation and screenshots, if there are readers for them.

