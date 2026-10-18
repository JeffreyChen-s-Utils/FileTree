# progress.md: FileTree

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed. Priority: **P1** next, **P2** worth doing, **P3** only if wanted.
Suggested order: #96 (DiskArbitration dissenter for the remaining APFS refusal), #95 (remaining UI hangs), #113 (warm-up confirmation on hosted runs), then the native-environment gates in #75/#76 and the P2 items.
Cross-repo and workspace items live in `D:\Codes\progress.md`.

## Open

- **#113** (P2) Confirm on hosted runs that the Windows PowerShell warm-up (U-20261017-64) removes the share helpers' 20/30-second timeouts (two hosted runs so far: warm-ups of 3.3 and 10.7 s, then 1.7 and 1.3 s helpers; U-20261017-71). If a `powershell.exe` helper still times out after a completed `powershell_warmup`, keep its thread-state samples and investigate that warm wait as a new cause; do not lengthen the deadlines.

- **#96** (P1) Identify who holds the owned APFS image's whole disk after unmount. Original cleanup and unmounted-binding recovery are verified natively (U-20261017-60: 134 first-attempt and 3 recovered samples of 143; no failure in the 64 samples after run 39000091134). The remaining refusal is a short whole-disk `Resource busy` with the volume already unmounted and only the normal `diskimages-helper` visible to `lsof`. Obtain a refusal carrying the new DiskArbitration `refusal_log` and identify the dissenter. The 27 hosted samples since that capture (runs 39063310689 attempts 1–7, 39064116568 and the 00f4e77 run) all detached on the first attempt, so the refusal is rarer than the earlier 9 in 143. Preserve complete UUID/device/container/store binding, fresh registrations, image/mountpoint checks, three-attempt/60-second command bounds and failed-fixture evidence. No force detach, guessed device, relaxed ownership check, extra retry or unverified deletion.

- **#95** (P1) Audit the remaining Qt pauses while preserving complete rows, native notifications and accessibility: remaining failure/confirmation prompts and remaining settings/native GUI calls, including Properties. Grouped header titles no longer relayout the tree (U-20261017-73); result-table filtering is done (U-20261017-74); tree sorting was audited and its relayout callbacks made cheaper (U-20261017-75); live ticks repaint instead of relaying out and grouped fill was audited (U-20261017-76); duplicate membership rebuilds build paths only for ties (U-20261017-77); the clipboard pause is Qt rendering text for the pasting program (U-20261018-79).

- **#114** [BLOCKED] Owner verification on real interactions: Windows UAC consent and cancel for the owned administrator-restart worker (mocked Shell execution and COM apartment checks do not establish it), and the owner's Python-source scan, asynchronous closing and source-operation workflows on the actual hanging paths before claiming all hangs resolved. Needs the owner at the machine.

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
