# FileTree → 完整磁碟管理與垃圾清除工具規劃

> 目標：將目前以「磁碟空間分析」為核心的 FileTree，逐步升級為一套跨平台、以安全為優先的完整磁碟管理工具。
>
> Repository: `JeffreyChen-s-Utils/FileTree`
>
> 本文件是產品、架構與實作 roadmap；不要求一次完成，建議以 Phase 為單位逐步合併。

---

## 1. 產品定位

FileTree 最終應從：

> **「告訴我什麼東西佔了硬碟空間」**

升級成：

> **「告訴我硬碟發生了什麼、哪些東西可以安全處理、我能釋放多少空間，以及如何持續維持健康的磁碟狀態。」**

核心體驗：

1. 掃描磁碟 / 資料夾
2. 分析空間使用情況
3. 自動辨識可清理項目
4. 顯示清理風險與原因
5. 使用者確認
6. 優先移到回收筒 / Trash，而非永久刪除
7. 即時重新計算可用空間
8. 提供清理前後報告
9. 提供重複檔、大檔、舊檔與應用程式資料管理
10. 提供磁碟健康、SMART、容量趨勢與維護建議

---

# 2. 目前基礎

目前 FileTree 已具備相當完整的空間分析基礎：

- 多執行緒掃描
- Folder Tree
- Treemap
- Sunburst
- Largest Files
- Search
- Duplicate detection
- File type analysis
- Age analysis
- Saved scan / Compare
- CSV / JSON export
- Recycle Bin / Trash 安全刪除
- Windows administrator elevation
- Windows / macOS / Linux
- English / 繁體中文 / 简体中文
- PySide6 GUI
- Nuitka standalone build

因此不建議重新設計 scanner，而是新增一層：

```text
                 ┌─────────────────────────┐
                 │       FileTree GUI       │
                 └────────────┬────────────┘
                              │
             ┌────────────────┼────────────────┐
             │                │                │
       Disk Explorer      Cleanup Center    Health Center
             │                │                │
       ┌─────┴─────┐    ┌─────┴──────┐    ┌───┴────────┐
       │ Scanner   │    │ Detectors   │    │ Disk Info  │
       │ Analysis  │    │ Cleaner     │    │ SMART      │
       │ Compare   │    │ Safety      │    │ Free Space │
       └───────────┘    │ Restore     │    │ Trends     │
                        └─────────────┘    └────────────┘
```

---

# 3. 最終功能地圖

## 3.1 Dashboard

新增首頁 Dashboard：

- 磁碟容量
- 已使用空間
- 可用空間
- 使用率
- 最大資料夾
- 最大檔案
- 重複檔可釋放空間
- 垃圾檔可釋放空間
- 暫存檔可釋放空間
- 舊檔可釋放空間
- 最近一次掃描
- 最近一次清理
- 磁碟健康狀態
- 清理建議

例如：

```text
C:  1 TB

██████████████████████░░░░░░  73%

使用中      731 GB
可用        293 GB

可安全清理：
  暫存檔            12.4 GB
  Cache              8.7 GB
  回收筒             4.1 GB
  重複檔             3.2 GB
  舊下載             6.8 GB
  ─────────────────────────
  預估可釋放        35.2 GB

[開始清理] [深入分析]
```

---

# 4. Cleanup Center

新增主要功能頁：

## 4.1 Smart Cleanup

自動掃描常見垃圾：

### 系統暫存

Windows：

- `%TEMP%`
- `%WINDIR%\Temp`
- Windows temporary files
- Delivery Optimization cache
- Windows Update cache
- thumbnail cache
- crash dump
- Windows Error Reporting
- DirectX shader cache

macOS：

- user cache
- system cache（僅列出安全範圍）
- temporary files
- application cache
- diagnostic reports
- logs

Linux：

- `/tmp`
- user cache
- application cache
- thumbnail cache
- package cache
- crash reports
- journal logs（依權限與策略）

---

## 4.2 Application Cache

偵測常見應用程式：

- Chrome
- Edge
- Firefox
- Brave
- VS Code
- JetBrains IDE
- Discord
- Steam
- Epic Games
- npm
- pnpm
- yarn
- pip
- uv
- Poetry
- Cargo
- Gradle
- Maven
- Docker
- Podman

每個清理項目必須顯示：

```text
VS Code cache

大小：2.4 GB
路徑：...
最後使用：3 天前

風險：低
用途：編輯器快取，可由 VS Code 重新建立

[檢視] [清理]
```

---

# 5. Cleanup Detector Framework

不要把所有垃圾規則硬編碼在 GUI。

新增：

```text
je_file_tree/core/cleanup/
```

建議：

```text
cleanup/
├── __init__.py
├── models.py
├── detector.py
├── registry.py
├── scanner.py
├── policy.py
├── cleaner.py
├── restore.py
├── history.py
├── rules/
│   ├── __init__.py
│   ├── temp.py
│   ├── cache.py
│   ├── logs.py
│   ├── crash_dumps.py
│   ├── thumbnails.py
│   ├── browser.py
│   ├── package_managers.py
│   ├── development.py
│   ├── recycle_bin.py
│   └── old_files.py
└── platform/
    ├── __init__.py
    ├── windows.py
    ├── macos.py
    └── linux.py
```

Detector interface：

```python
class CleanupDetector(Protocol):
    id: str
    name: str
    category: CleanupCategory

    def detect(self, context: CleanupContext) -> list[CleanupCandidate]:
        ...

    def estimate(self, candidate: CleanupCandidate) -> CleanupEstimate:
        ...

    def safety(self, candidate: CleanupCandidate) -> SafetyLevel:
        ...
```

---

# 6. Cleanup Candidate Model

每個候選清理項目至少包含：

```text
id
category
path
display_name
size
file_count
last_modified
last_accessed
detector
reason
risk_level
confidence
reclaimable
requires_admin
reversible
dependencies
warnings
```

風險：

```text
SAFE
LOW
MEDIUM
HIGH
BLOCKED
```

建議預設只自動選：

```text
SAFE
LOW
```

`HIGH` 永遠不得進入一鍵清理。

---

# 7. Safety Model

這是整個產品最重要的部分。

## 7.1 永遠禁止自動清理

以下內容不可由 Smart Cleanup 自動刪除：

- 使用者文件
- Desktop
- Documents
- Pictures
- Videos
- Music
- Downloads 中的未知檔案
- Git repository
- SSH keys
- browser profile
- application database
- password manager data
- cloud sync root
- system directories
- boot files
- executable files
- unknown file types

---

## 7.2 刪除策略

目前 FileTree 已採：

> Move to Recycle Bin / Trash

應保留並擴充：

```text
Cleanup Action
      │
      ├── Move to Trash
      │
      ├── Delete permanently
      │      └── 必須進階設定 + 明確確認
      │
      └── Ignore
```

預設永遠：

```text
Move to Trash
```

---

# 8. Cleanup Preview

清理前必須有 Preview：

```text
即將清理 27 個項目

Temporary files       8.2 GB
Browser cache         3.7 GB
Thumbnails             1.1 GB
Crash dumps             820 MB
Old logs                430 MB
──────────────────────────────
Total                 14.25 GB

[查看全部項目]

風險：
✓ 低風險：25
! 中風險：2
✕ 高風險：0

[取消] [移至回收筒]
```

如果候選包含中風險項目：

- 預設不勾選
- 顯示原因
- 要求額外確認

---

# 9. Undo / Restore

清理歷史：

```text
Cleanup History

2026-10-06  14:32
27 items
14.25 GB
[View] [Restore]
```

如果檔案被移至 Recycle Bin / Trash：

- 記錄原始路徑
- 記錄 cleanup session
- 記錄時間
- 記錄候選規則
- 可嘗試 Restore

新增：

```text
core/cleanup/restore.py
```

注意：

- 不應自行實作系統 Trash
- 優先使用 OS API
- 如果 OS 不支援可靠 restore，UI 不提供 Restore 按鈕

---

# 10. Duplicate Manager

目前已有 duplicates，升級成獨立功能。

## 10.1 Duplicate categories

- Exact duplicate
- Same filename
- Same size
- Same content
- Similar images（Phase 4）
- Similar videos（Phase 4）

---

## 10.2 Smart Selection

提供：

```text
Keep newest
Keep oldest
Keep shortest path
Keep outside backup directory
Keep file with newest modification
Keep file with shortest path
```

但任何 Smart Selection 都只能：

> 預選

不能直接刪除。

---

# 11. Large File Manager

目前 Largest Files 升級成 File Manager：

篩選：

- > 1 GB
- > 5 GB
- > 10 GB
- > 50 GB
- custom size

分類：

- Videos
- ISOs
- Archives
- VM images
- Disk images
- Game files
- Development artifacts
- Installer files

支援：

```text
Open
Show in Explorer/Finder/File Manager
Copy path
Move
Move to Trash
Compress
Export
```

---

# 12. Old Files Analyzer

提供「長時間未使用」分析：

```text
Last modified:

> 2 years
> 1 year
> 6 months
> 3 months
> 1 month
```

重要：

- `mtime` 不代表真正的「最後使用時間」
- 不應直接把 `atime` 當成可靠依據
- UI 必須寫成「最後修改」
- 如果平台有可靠 access time，再額外顯示

提供：

```text
Old Downloads
Old Installers
Old Archives
Old Videos
Old Projects
```

---

# 13. Downloads Analyzer

Downloads 特別處理：

分類：

```text
Installers
Archives
Videos
Images
Documents
Disk Images
Executables
Unknown
```

建議：

```text
Downloaded 428 days ago
2.8 GB
Looks like an installer

[Open] [Move to Trash]
```

不得因為檔名看起來像垃圾就自動刪除。

---

# 14. Development Cleanup

這會是 FileTree 很有價值的差異化功能。

## 14.1 Python

偵測：

- `__pycache__`
- `.pytest_cache`
- `.mypy_cache`
- `.ruff_cache`
- `.tox`
- `.nox`
- `.coverage`
- build artifacts
- `dist`
- `*.egg-info`
- virtual environments

Virtualenv 必須：

```text
偵測
↓
顯示大小
↓
確認專案位置
↓
禁止 Smart Cleanup
```

---

## 14.2 Node.js

偵測：

- `node_modules`
- npm cache
- pnpm store
- yarn cache
- build output
- `.next`
- `.nuxt`
- `dist`
- `coverage`

`node_modules`：

- 可以列為大型可清理項目
- 不能列為 SAFE
- 顯示「刪除後可由 package manager 重新安裝」

---

## 14.3 Rust

- `target`
- Cargo cache
- registry cache
- git checkouts

---

## 14.4 Java / JVM

- Gradle cache
- Maven repository
- build output
- IDE indexes

---

## 14.5 Docker

只做「分析」，不要第一版直接刪：

```text
Docker images
Containers
Volumes
Build cache
```

如果 Docker CLI 可用：

```text
docker system df
```

顯示：

```text
Reclaimable
Potentially reclaimable
Active
```

真正 prune 必須明確顯示 Docker 資源名稱與影響。

---

# 15. Browser Cleanup

支援：

- Chrome
- Edge
- Firefox
- Brave

可清：

- HTTP cache
- image cache
- code cache
- service worker cache
- temporary downloads

不可預設清：

- cookies
- passwords
- history
- autofill
- sessions

如果 browser 正在執行：

```text
Browser is running.

Close it before cleaning this cache.
```

不要強制終止 browser。

---

# 16. Recycle Bin / Trash Manager

獨立頁面：

```text
Trash

Windows Recycle Bin
macOS Trash
Linux Trash

Items: 2,831
Size: 38.2 GB

[Empty Trash]
```

功能：

- 大小
- 項目數
- oldest item
- largest items
- empty
- restore（平台支援時）

Empty Trash 是高影響操作：

- 明確二次確認
- 顯示總容量
- 顯示不可復原警告

---

# 17. Disk Manager

新增 Disk 頁。

## 17.1 Volume

顯示：

```text
C:
NTFS
1 TB

Used: 731 GB
Free: 293 GB
Usage: 73%

Health: Good
```

支援：

- Windows
- macOS
- Linux

---

## 17.2 Disk information

如果 OS 能提供：

- filesystem
- block size
- total capacity
- free capacity
- mount point
- removable
- read-only
- SSD/HDD/NVMe
- model
- serial（若允許且不需要顯示給外部服務）

---

# 18. SMART / Disk Health

建議作為 optional capability。

優先：

```text
Windows → PowerShell / WMI
Linux   → smartctl
macOS   → diskutil
```

架構：

```text
core/health/
├── models.py
├── detector.py
├── smart.py
└── platform/
```

健康：

```text
GOOD
WARNING
CRITICAL
UNKNOWN
```

不可因 SMART API 缺失而讓主程式失敗。

---

# 19. Disk Health Dashboard

顯示：

- health
- temperature（若可取得）
- power-on hours（若可取得）
- reallocated sectors
- pending sectors
- percentage used（SSD 若可取得）
- media errors
- last checked

所有不可取得欄位：

```text
Not available on this platform
```

而不是猜測。

---

# 20. Capacity Trend

每次完成完整掃描後可保存摘要：

```text
Date        Used       Free
Oct 01      701 GB     299 GB
Oct 03      718 GB     282 GB
Oct 06      731 GB     269 GB
```

提供：

- 7 days
- 30 days
- 90 days
- 1 year

估算：

```text
Current growth: +5.2 GB/day
Estimated full: ~52 days
```

注意：

> 這只是線性估計，不代表實際會在該日期滿碟。

---

# 21. Storage Alerts

提供設定：

```text
Notify when free space below:

20%
10%
5%
Custom
```

或：

```text
Free space below 50 GB
```

通知：

```text
Disk C: is running low.

Free: 38 GB

Top space users:
Videos       180 GB
Games        142 GB
Downloads     41 GB

[Analyze] [Dismiss]
```

---

# 22. Storage Rules

新增使用者規則：

```text
Rules

IF disk free < 50 GB
THEN suggest cleanup

IF Downloads file > 5 GB and older than 180 days
THEN suggest review

IF duplicate reclaimable > 10 GB
THEN notify

IF cache > 20 GB
THEN suggest cleanup
```

第一階段只做：

> Suggestion

不要自動刪除。

---

# 23. Cleanup Scheduler

Phase 4 才加入。

允許：

```text
Every week
Every month
When free space < X
```

但 scheduler 只能：

```text
scan
detect
notify
```

第一版禁止背景自動刪除。

未來若加入：

```text
Auto cleanup
```

只能針對：

```text
SAFE
```

且必須有：

- global enable
- per-rule enable
- activity log
- kill switch

---

# 24. File Classification Engine

將檔案從單純 extension 分析升級成 classification：

```text
Document
Image
Video
Audio
Archive
Installer
Disk Image
Database
Development
Cache
Temporary
Log
Backup
Game
Unknown
```

分類優先順序：

```text
special path
↓
filename
↓
extension
↓
magic bytes（可選）
```

不要只靠副檔名判斷安全性。

---

# 25. Cleanup Scoring

每個候選可計算：

```text
cleanup_score =

size_weight
+ age_weight
+ known_cache_weight
+ reclaimability_weight
- risk_weight
- active_use_weight
```

例如：

```text
Chrome Cache
Size: 8 GB
Age: 30 days
Known cache: yes
Rebuildable: yes
Risk: low

Score: 96/100
```

UI 顯示：

```text
Recommended
```

但分數不等於自動刪除權限。

---

# 26. Scan Cache

目前每次掃描都會建立完整 Node tree。

未來增加：

```text
Scan Snapshot Cache
```

用途：

- Dashboard 快速啟動
- capacity trend
- compare
- cleanup analysis
- recent folders

需要：

- schema version
- OS
- filesystem
- root path
- scan timestamp
- incomplete flag

禁止把 cache 當作目前檔案系統真實狀態。

---

# 27. Incremental Scan

Phase 4：

利用：

- mtime
- size
- inode / file ID
- filesystem metadata

降低重新掃描成本。

策略：

```text
previous snapshot
       ↓
detect changed directories
       ↓
rescan changed branches
       ↓
merge
```

任何偵測不可靠時：

```text
fallback to full scan
```

---

# 28. GUI 結構

建議 MainWindow 最終頁面：

```text
Dashboard
Storage
Explorer
Cleanup
Duplicates
Large Files
Old Files
Applications
Development
Trash
Health
History
Settings
```

---

# 29. Explorer

目前 ResultsView 改名或重新定位為 Explorer：

```text
Explorer
├── Folder Tree
├── Treemap
├── Sunburst
├── Bars
├── Largest Files
├── File Types
├── Age
├── Search
└── Problems
```

保留目前核心 UI，避免 breaking change。

---

# 30. Cleanup UI

新增：

```text
Cleanup

[Scan for cleanup]

Potentially reclaimable: 35.2 GB

Recommended
────────────────────────
Temporary files       12.4 GB
Browser cache          8.7 GB
Thumbnails             3.1 GB

Review
────────────────────────
Old downloads          6.8 GB
Large installers        2.2 GB
Duplicate files         2.0 GB

Protected / ignored
────────────────────────
System files
User documents
Active applications

[Review] [Clean selected]
```

---

# 31. Cleanup Details

點擊任何 detector：

```text
Browser Cache

8.7 GB
4,381 files

Why:
These files are generated by the browser and can
usually be recreated.

Risk:
Low

Affected:
Chrome
Edge

Excluded:
Cookies
Passwords
History
Sessions

[View files]
[Clean]
```

---

# 32. Settings

新增：

```text
Cleanup

☑ Show low-risk suggestions
☐ Show medium-risk suggestions
☐ Include development caches
☐ Include browser caches
☐ Include old files
☐ Include Downloads
☐ Empty Trash suggestions

Deletion
● Always move to Trash
○ Allow permanent deletion

Privacy
☑ Do not send file names anywhere
☑ Do not send file contents anywhere
```

---

# 33. Privacy

產品原則：

> FileTree 應完全 local-first。

預設：

- 不上傳檔名
- 不上傳路徑
- 不上傳檔案內容
- 不上傳使用者資料
- 不需要 cloud account
- 不需要 telemetry

如果未來加入 telemetry：

- opt-in
- 清楚說明
- 不包含路徑 / 檔名
- 可完全關閉

---

# 34. Permissions

平台能力表：

| 功能 | Windows | macOS | Linux |
|---|---:|---:|---:|
| Space scan | ✓ | ✓ | ✓ |
| Trash | ✓ | ✓ | ✓ |
| Duplicate scan | ✓ | ✓ | ✓ |
| Temp cleanup | ✓ | ✓ | ✓ |
| Browser cleanup | ✓ | ✓ | ✓ |
| Package cache | ✓ | ✓ | ✓ |
| SMART | optional | optional | optional |
| Admin/root scan | ✓ | optional | optional |
| Disk health | optional | optional | optional |

任何 capability 不可用時：

```text
Unavailable
```

而不是 error。

---

# 35. Core API

建議新增：

```python
je_file_tree.core.cleanup
je_file_tree.core.health
je_file_tree.core.storage
je_file_tree.core.history
```

Cleanup API：

```python
detect_cleanup(
    roots,
    *,
    options,
    progress,
    cancel,
) -> CleanupResult
```

Preview：

```python
build_cleanup_plan(
    candidates,
    policy,
) -> CleanupPlan
```

Execution：

```python
execute_cleanup(
    plan,
    *,
    trash=True,
    progress=None,
    cancel=None,
) -> CleanupResult
```

Restore：

```python
restore_cleanup(session_id) -> RestoreResult
```

---

# 36. Cleanup Plan

所有刪除操作都先建立 immutable plan：

```text
Detection
   ↓
Candidates
   ↓
User selection
   ↓
CleanupPlan
   ↓
Validation
   ↓
Confirmation
   ↓
Execution
```

Execution 前重新驗證：

- path exists
- path is still same file
- size unchanged（可選）
- file ID unchanged（可選）
- permission
- safety policy

避免掃描後檔案被替換導致誤刪。

---

# 37. Race Condition Protection

清理前：

```text
scan candidate
↓
file changed?
↓ yes
invalidate candidate
↓
ask user to rescan
```

例如：

```text
This file changed since the cleanup scan.

Path:
...

The item will not be deleted.

[Rescan]
```

---

# 38. Symlink / Junction Safety

延續現有設計：

- 不 follow symlink
- 不 follow junction
- 不 follow mount unintentionally
- 顯示 link target（若安全可取得）
- cleanup 不得透過 link 進入另一個 tree

---

# 39. Cloud Files

針對：

- OneDrive
- iCloud
- Dropbox
- Google Drive

第一版只做：

```text
Analyze
```

不可自動判斷：

> 「online-only = 可刪除」

需要特別顯示：

```text
Cloud-managed file

Removing this entry may affect synchronization.
```

---

# 40. Application Detection

新增 application registry：

```text
core/apps/
├── registry.py
├── models.py
├── detector.py
└── definitions/
    ├── browsers.py
    ├── development.py
    ├── games.py
    └── system.py
```

每個 application 定義：

```python
ApplicationDefinition(
    id="vscode",
    names=[...],
    cache_paths=[...],
    safe_cleanup=[...],
)
```

---

# 41. Game Storage

第二階段可支援：

- Steam
- Epic
- Battle.net
- Xbox
- other launchers

分析：

```text
Installed games
Game size
Shader cache
Workshop content
Unused games
```

「Unused game」只做建議：

```text
Last launch: unknown
```

不能因為沒有 launcher metadata 就宣稱「未使用」。

---

# 42. Installer Cleanup

偵測：

- `.exe`
- `.msi`
- `.dmg`
- `.pkg`
- `.deb`
- `.rpm`
- `.AppImage`
- `.iso`

顯示：

```text
Installer
Downloaded 240 days ago
Installed application may already exist
```

不要自動刪除。

---

# 43. Log Cleanup

可清：

- application logs
- old crash logs
- rotated logs
- temporary logs

不可：

- 正在寫入的 active logs
- security/audit logs
- system logs unless platform policy explicitly allows

---

# 44. Empty Directory Cleanup

新增：

```text
Empty folders
```

但預設只：

```text
Show
```

不自動刪除。

原因：

空資料夾可能有：

- application marker
- Git metadata
- mount point
- synchronization semantics
- user organization purpose

---

# 45. Broken Shortcut / Link Analyzer

Phase 4：

- Windows `.lnk`
- Unix symlink
- macOS alias（視 API）

顯示 broken links。

預設：

```text
Review only
```

---

# 46. Export / Reporting

新增：

```text
Cleanup Report
Disk Report
Health Report
Duplicate Report
```

格式：

- JSON
- CSV
- HTML

HTML 報告：

```text
Disk summary
Top directories
Cleanup candidates
Reclaimed space
Health
Warnings
```

---

# 47. Cleanup History Schema

```json
{
  "schema": "file-tree/cleanup/1",
  "session_id": "...",
  "started": "...",
  "finished": "...",
  "root": "...",
  "candidate_count": 27,
  "planned_bytes": 15234123456,
  "reclaimed_bytes": 14981234567,
  "failed": [],
  "items": []
}
```

---

# 48. Logging

Application log 與 cleanup audit 分離：

```text
logs/
cleanup history/
```

Cleanup audit 必須記：

- timestamp
- detector
- original path
- size
- action
- result
- error

敏感資料不要送到外部服務。

---

# 49. Performance Targets

延續目前 scanner 的效能目標。

新增：

### Cleanup detection

10 萬候選：

```text
< 2 sec
```

不包含：

- full hashing
- external CLI
- SMART query

### Duplicate

維持 streaming hash：

- 不一次讀入記憶體
- hash worker pool
- cancellation

### UI

任何 cleanup scan：

> 不得 block GUI thread。

---

# 50. Testing Strategy

新增：

```text
test/test_cleanup.py
test/test_cleanup_detectors.py
test/test_cleanup_policy.py
test/test_cleanup_plan.py
test/test_cleanup_restore.py
test/test_health.py
test/test_storage.py
test/test_history.py
```

每個 detector 都要有：

```text
positive case
negative case
permission error
missing path
changed file
symlink
empty directory
large file
unicode path
```

---

# 51. Dangerous-operation Tests

永遠加入：

```text
test_never_deletes_outside_root
test_never_follows_symlink
test_never_deletes_protected_path
test_changed_file_is_rejected
test_cancel_is_safe
test_failed_item_is_reported
test_partial_cleanup_is_consistent
```

Windows：

```text
test_recycle_bin
test_admin_required
```

Linux：

```text
test_trash_spec
```

macOS：

```text
test_trash
```

---

# 52. Internationalization

新增所有字串到：

```text
je_file_tree/gui/strings.py
```

至少同步：

- English
- 繁體中文
- 简体中文

Cleanup UI 特別需要避免模糊翻譯：

```text
Delete
Move to Trash
Permanently Delete
Clean
Preview
Reclaimable
Protected
Risk
```

---

# 53. Accessibility

所有 Cleanup 操作：

- keyboard navigable
- visible focus
- screen reader labels
- no colour-only warning
- risk icon + text
- confirmation dialog keyboard safe

---

# 54. CLI

GUI 完整後可增加 CLI：

```bash
je-file-tree cleanup scan C:\
je-file-tree cleanup list
je-file-tree cleanup preview
je-file-tree cleanup execute
je-file-tree duplicates scan C:\
je-file-tree health
je-file-tree report
```

第一階段 CLI：

```bash
je-file-tree cleanup scan
```

只輸出分析，不執行刪除。

真正執行：

```bash
je-file-tree cleanup execute --confirm
```

仍需安全 policy。

---

# 55. Configuration

設定檔：

```text
QSettings
```

不建議第一階段引入額外 config dependency。

可保存：

- enabled detectors
- cleanup preferences
- excluded paths
- size thresholds
- age thresholds
- notification settings
- scan history location

---

# 56. Exclusion Rules

使用者可以設定：

```text
Never scan:
D:\VMs
D:\Games
D:\Backups
```

Cleanup exclusion 優先級最高：

```text
Global exclusion
    >
Detector exclusion
    >
Candidate
```

即使 detector 認為 SAFE，也不能越過 exclusion。

---

# 57. Protected Paths

建立平台 protected path registry：

```text
core/cleanup/policy.py
```

例如：

```text
Windows:
C:\Windows
C:\Program Files
C:\Program Files (x86)
C:\ProgramData

macOS:
/System
/Library
/private/var

Linux:
/boot
/etc
/usr
/bin
/sbin
/lib
```

注意：

> Protected path 不是永遠不可操作的絕對真理，而是 Smart Cleanup 的安全邊界。

---

# 58. Architecture Evolution

目標：

```text
je_file_tree/
├── core/
│   ├── scanner.py
│   ├── analysis.py
│   ├── duplicates.py
│   ├── compare.py
│   ├── export.py
│   │
│   ├── cleanup/
│   ├── health/
│   ├── storage/
│   ├── history/
│   └── apps/
│
└── gui/
    ├── dashboard.py
    ├── cleanup_panel.py
    ├── disk_panel.py
    ├── health_panel.py
    ├── history_panel.py
    ├── applications_panel.py
    └── ...
```

保持：

```text
core → standard library / optional platform adapters
gui  → PySide6
```

Core 不可 import GUI。

---

# 59. Release Strategy

不要一次把所有功能合併。

建議：

## Phase 1 — Cleanup Foundation

目標：

- Cleanup model
- detector registry
- temp detector
- cache detector
- cleanup preview
- safety policy
- trash execution
- history
- tests

---

## Phase 2 — Smart Cleanup

加入：

- browser caches
- thumbnails
- logs
- crash dumps
- recycle bin
- Downloads analyzer
- old files
- cleanup scoring

---

## Phase 3 — Storage Manager

加入：

- Dashboard
- Disk Manager
- capacity trend
- storage alerts
- disk health
- SMART
- health report

---

## Phase 4 — Power User

加入：

- development cleanup
- Docker analysis
- package manager caches
- game storage
- advanced duplicate selection
- incremental scan
- CLI cleanup
- HTML reports

---

## Phase 5 — Automation

加入：

- scheduled scans
- notifications
- rules
- SAFE-only auto cleanup
- background monitoring

---

# 60. Recommended GitHub Issues / Milestones

建議建立以下 milestones：

### M1 — Cleanup Core

- [ ] Cleanup candidate model
- [ ] Detector interface
- [ ] Cleanup policy
- [ ] Protected paths
- [ ] Cleanup plan
- [ ] Trash executor
- [ ] Cleanup history
- [ ] Tests

### M2 — Smart Cleanup

- [ ] Temp detector
- [ ] Cache detector
- [ ] Browser detector
- [ ] Log detector
- [ ] Crash dump detector
- [ ] Thumbnail detector
- [ ] Recycle Bin detector
- [ ] Cleanup dashboard

### M3 — Storage Manager

- [ ] Disk information
- [ ] Volume dashboard
- [ ] Health abstraction
- [ ] SMART adapters
- [ ] Capacity history
- [ ] Alerts

### M4 — Power User

- [ ] Development cache detection
- [ ] Docker analyzer
- [ ] Package manager analyzer
- [ ] Game storage
- [ ] Incremental scanning
- [ ] HTML reports
- [ ] CLI

### M5 — Automation

- [ ] Scheduler
- [ ] Rules
- [ ] Notifications
- [SAFE-only automation
- [ ] Background monitor

---

# 61. Definition of Done

一個 cleanup feature 只有在以下條件全部滿足才算完成：

- [ ] Core implementation
- [ ] GUI
- [ ] i18n
- [ ] safety policy
- [ ] permission handling
- [ ] cancellation
- [ ] error handling
- [ ] unit tests
- [ ] GUI test
- [ ] Windows behaviour verified
- [ ] macOS behaviour verified where available
- [ ] Linux behaviour verified where available
- [ ] architecture.md updated
- [ ] README updated
- [ ] release/update notes added

---

# 62. 最終產品體驗

最終啟動 FileTree 後，使用者看到的應該不是單純：

> 「這個資料夾有多大？」

而是：

```text
┌───────────────────────────────────────────────────────┐
│ FileTree                                               │
├───────────────────────────────────────────────────────┤
│                                                       │
│  C:                                                   │
│  1 TB                                                 │
│                                                       │
│  ███████████████████████░░░░░  73%                   │
│                                                       │
│  731 GB used       293 GB free                        │
│                                                       │
│  ───────────────────────────────────────────────────  │
│                                                       │
│  Can safely reclaim                                   │
│                                                       │
│  Temporary files              12.4 GB   Low           │
│  Browser cache                 8.7 GB   Low           │
│  Old downloads                 6.8 GB   Review        │
│  Duplicates                    3.2 GB   Review        │
│                                                       │
│  Potentially reclaimable: 31.1 GB                     │
│                                                       │
│  [ Review & Clean ]                                   │
│                                                       │
│  ───────────────────────────────────────────────────  │
│                                                       │
│  Storage                                               │
│  Largest folders                                      │
│  Largest files                                        │
│  File types                                           │
│                                                       │
│  Health: ● Good                                       │
│  Growth: +5.2 GB/day                                  │
│                                                       │
└───────────────────────────────────────────────────────┘
```

這樣 FileTree 就會從：

> **Disk Usage Analyzer**

真正進化成：

> **Local-first Disk Management & Cleanup Suite**

---

# 63. 最重要的產品原則

最後整個專案應遵守以下 10 條：

1. **分析優先於清理**
2. **Preview 優先於 Delete**
3. **Trash 優先於 Permanent Delete**
4. **SAFE 才能進入 Smart Cleanup**
5. **任何不確定的檔案都視為不可自動清理**
6. **永遠不 follow symlink / junction 進行清理**
7. **清理前重新驗證檔案狀態**
8. **所有清理動作都有 audit history**
9. **Core 與 GUI 分離**
10. **所有平台差異透過 capability / adapter 處理**

---

## 建議第一個實作 PR

第一個 PR 不應直接做完整 Smart Cleanup。

建議先做：

```text
feat: add cleanup engine foundation

新增：
- core/cleanup/models.py
- core/cleanup/detector.py
- core/cleanup/registry.py
- core/cleanup/policy.py
- core/cleanup/cleaner.py
- core/cleanup/history.py
- core/cleanup/rules/temp.py
- gui/cleanup_panel.py
- cleanup preview dialog
- cleanup history
- safety tests
```

完成後再以 detector 為單位逐步擴充。

這樣可以最大限度利用目前 FileTree 已有的 scanner、Node、file actions、elevation、i18n、worker 與測試架構，同時避免把「清理檔案」這種高風險能力直接塞進現有 `file_actions.py`。
