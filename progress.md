# progress.md: FileTree

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed. Priority: **P1** next, **P2** worth doing, **P3** only if wanted.
Suggested order: #99 (native SMB disconnect timeout), then #95 (remaining UI hangs), the native-environment gates in #75/#76 and the P2 items.
Cross-repo and workspace items live in `D:\Codes\progress.md`.

## Open

- **#99** (P1) Obtain an instrumented native timeout trace and identify the wait in `tools/windows_share_probe.py::_disconnect`. Original CI run 38908715123 / job 116998797981 did not complete disconnect/source post-verification. Require the helper's step history, actual exit/timeout and bounded outputs from a reproduced 30-second wait before choosing a fix; preserve bounded execution and exact share/root/mapping ownership checks. Modeled timeouts and successful native retries cannot establish the cause.

- **#96** (P2) Diagnose repeated APFS attachment-refusal before cleanup. Run 38894958709 records five captured-image entities, all unmounted, versus one allowed private mountpoint; obtain native per-attempt results for a reproduced busy/refusal sequence to establish whether a busy command precedes the refusal, then determine how captured device/UUID ownership must be established before any cleanup. The original run 38886523231 lacks these observations. A modeled busy/unmount sequence does not prove the native cause. Preserve ownership checks and require native cleanup evidence for any subsequent change.

- **#95** (P1) Audit remaining wide-folder initial filter-entry mapping/layout, sorting, live layout updates, large-batch completion (including grouped-list expansion and bulk selection), result-table filtered mapping and settings/shell/native GUI calls. Verify the owner's Python-source scan, asynchronous closing and source-operation workflows on the actual hanging paths before claiming all hangs resolved. Held-reader/closing timer tests cannot establish that every native UI hang is resolved.

- **#4** [UNVERIFIED] Verify file-manager selection/fallback, Trash behavior, Finder drag-to-scan source preservation, protected GUI duplicate-link approval and original-path symlink creation after approved Trash on macOS. No Mac or macOS VM is available from the owner for Finder interaction/consent.

### Freeing space

- **#21** (P2) [BLOCKED] macOS bin querying/Finder-wide emptying remains blocked on a native environment; no Mac is available from the owner. Verify native macOS automation consent, APFS/firmlink scope deduplication, multi-volume coverage, active-operation lifetime and failed/partial metadata refresh; fixture/mocked execution does not prove native behavior.
- **#76** (P1) [BLOCKED] Validate actual cloud placeholders with a real provider environment (unavailable from the owner); fixtures do not prove provider allocation. Keep unmeasurable shared extents and directory metadata unknown; Windows no-bin outcomes remain unknown. Drive reconciliation remains #75.

### Scanning

- **#33** (P3) [BLOCKED] Validate successful large-real-drive MFT parity and throughput against ordinary scanning before considering default enablement of `ScanOptions.experimental_mft`. A qualified disposable large-drive/admin validation environment has not been supplied. Preserve ordinary visibility, no-follow path authority, exact metadata and incomplete coverage; fallback timings do not establish MFT throughput. The serial audit makes no speed claim.
- **#35** (P2) [BLOCKED] Measure UNC/mapped-drive worker-count throughput on a genuinely slow remote SMB link before recommending concurrency for that environment. No owner remote share/slow-link validation environment is available; native loopback timings cannot establish remote performance.
- **#75** (P1) [BLOCKED] Verify same-device mount boundaries on macOS/other POSIX with native traversal guards; no disposable environment for that case is available from the owner. FreeBSD nullfs has a distinct st_dev and cannot prove that case. Unmounted APFS peer capacity remains unknown. The GUI and CLI ledger remain estimates; independently unmeasurable shared/reserved/filesystem metadata, omitted bytes and other-volume totals stay unknown. Direct bin labels and Finder emptying remain #21.

### Over time

- **#38** (P3) [BLOCKED] Verify OS-native macOS alert interaction, actual user-login startup and Windows/macOS notification display permission. Native Qt widget/registration fixtures do not prove OS-native interaction or a real login; dispatch does not prove display permission. No owner login/macOS desktop validation environment is available; Windows display capture remains unverified.

### Distribution

- **#47** (P2) [BLOCKED] Configure an owner Azure Artifact Signing Public Trust account/profile and OIDC environment identifiers for the opt-in release signing flow (`docs/windows-signing.md`), then verify real timestamped EXE/MSI signatures and downloaded artifact hashes. No signing certificate/service environment is available. macOS Developer ID signing/notarization also requires unavailable owner credentials; unsigned builds do not establish signing or SmartScreen reputation.
- **#48** (P3) [BLOCKED] Submit reviewed winget/Scoop/Chocolatey drafts for the exact published release artifacts and verify real store installation/upgrades. Store-publishing tokens/accounts remain unavailable from the owner.
