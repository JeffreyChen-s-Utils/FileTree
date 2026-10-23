# 程式審核：FileTree

## 審核者

- 審核者：工作區程式審核
- 日期：2026-10-22
- 對象：`FileTree`（`je_file_tree`）
- 範圍：工作樹熱點。路徑穿越、subprocess、多執行緒掃描例外是否被吞、權限錯誤是否處理。排除 `build/`、`test/`、`__pycache__`。
- 原始審核結論：需修正；2026-10-23 修正確認見本文末。

## 審核規範

共通規範在工作區 repo [JE-Chen/Codes](https://github.com/JE-Chen/Codes) 的 `docs/code-review-standard.md`。下面留下 2026-10-22 這次審核所用的條款，讓審核紀錄的依據對得上那一次。之後的審核以工作區那份為準。本專案更嚴的條款仍以本節與本專案的 `CLAUDE.md` 為準。

1. 設計：分層、掃描不跟隨連結、不可讀資料夾必須留下覆蓋紀錄，變更操作不得靠字串前綴冒充已釘選的路徑。
2. 可讀性：循環複雜度 ≤ 15、函式 ≤ 80 行、巢狀 ≤ 4、參數 ≤ 7、行 ≤ 120；專案既有上限更嚴時從嚴。本輪未逐函式機械重算。
3. 錯誤處理：不可裸 `except`、不可把掃描或變更失敗收成成功；權限錯誤要進入結果或明確拒絕。
4. 死碼：熱點路徑上未見已關閉的永久刪除或空殼 subprocess。
5. 型別與 docstring：熱點公開函式有型別與說明；本輪不把缺註解單獨列為缺陷。
6. 安全：無 shell、無 `eval` / `exec` / `pickle` / `yaml.load` / `verify=False`；路徑必須拒絕 `..`、延伸 UNC／裝置路徑不得被改寫成另一條本機路徑。
7. 測試：本輪未執行測試；既有測試檔不在審核範圍。
8. 效能：掃描執行緒數與讓出視窗的設計維持現狀；不因本輪熱點改動建議增減 worker。
9. §6：跨專案邊界（非同步關閉、不把驗證工具當成清理 API）本輪只抽讀；熱點變更路徑不得擴大操作授權。
10. 文件同步：`architecture.md` 所述「不可讀則記入錯誤、不跟隨連結」與一般掃描器一致；實驗 MFT 退回與延伸路徑釘選的落差見下列發現。

嚴重度：缺陷（未關閉即不得通過）、建議、備註。通過＝無未關閉缺陷；有條件通過＝無立即損害；需修正＝有未關閉缺陷。

## 審核紀錄

### 方法

- 讀 `architecture.md` 前段與 §6 開頭、`CLAUDE.md` 程式規則、`progress.md` 前 80 行。
- 在 `je_file_tree`（不含快取目錄）搜尋 `eval(`、`exec(`、`shell=True`、`pickle`、`yaml.load`、`verify=False`、裸 `except:`、`subprocess`。`exec(` 的命中皆為 Qt `dialog.exec()`／`app.exec()`，不是 Python `exec`。
- 每則發現皆先讀過對應原始碼。並抽讀掃描器、掛載點、MFT 列目錄、壓縮釘選、虛擬磁碟壓縮、檔案總管、Git、提升權限與多根掃描的例外路徑。

### 發現

#### CR-01

- 嚴重度：缺陷
- 位置：`D:\Codes\FileTree\je_file_tree\core\scanner.py`（`_work` 309–313、`_read_all` 315–325、`_take` 327–342、`_finish` 344–357）
- 說明：資料夾讀取的 `BaseException` 會寫入 `_failure`，主執行緒 `join` 後重丟，這一段沒有被吞。但 `give_way()` 與 `_finish()` 在該 `try` 之外。`_take` 已把 `_busy` 加一；`_finish` 一進鎖就先減 `_busy`，其後的 `extend` 或祖先累加若失敗，工作執行緒直接結束。失敗不會寫入 `_failure`。`_busy` 已經復原時，其餘工作者仍可把佇列排完並設 `_done`，`scan()` 會當成成功掃描返回。執行緒是 daemon，未捕捉的例外只進預設 excepthook（標準錯誤），視窗使用者看不到。若例外發生在減 `_busy` 之前，`_pending` 已空且 `_busy` 仍大於 0，其他工作者會停在 `wait(0.1)`，直到取消才由主執行緒 `_stop` 叫醒，原本的例外仍然遺失。
- 依據：錯誤處理；專案規則要求不可讀或失敗不得偽裝成掃完。註解寫「交給呼叫端重丟」，實際只覆蓋 `_read_folder`。
- 狀態：未關閉
- 建議：把取得工作之後的 `give_way`、讀取與 `_finish` 放進同一個 `BaseException` 處理；未完成的工作要減回 `_busy`。只要有工作者失敗，就必須重丟，不得發布一般 `ScanResult`。

#### CR-02

- 嚴重度：缺陷
- 位置：`D:\Codes\FileTree\je_file_tree\core\virtual_disk_compaction.py`（`_pin_local` 74–77）；釘選實作在 `D:\Codes\FileTree\je_file_tree\core\compression_ops.py`（`_pinned_path` 147–164）
- 說明：註解寫延伸 UNC／裝置路徑不得變成本機授權，實作卻對任何 `\\?\` 去掉前四個字元。`\\?\C:\...` 會變成磁碟機路徑，這是預期。`\\?\UNC\server\share\...` 與 `\\?\Volume{...}\...` 會變成相對路徑，`os.path.abspath` 再把它掛到處理程序目前工作目錄。`splitdrive` 於是得到本機磁碟機，形式檢查可以通過。該相對路徑若存在且磁碟機型別為固定式，釘選的是另一棵目錄；`OpenVirtualDisk` 仍使用原本的延伸路徑。祖先釘選與實際變更的檔案不是同一個對象，重新命名的競賽不會被這次釘選擋住。相對路徑不存在時 `lstat` 失敗，操作會拒絕，因此不是無條件寫錯檔，但安全檢查已與註解相反。同套件 `virtual_disks._key` 只接受 `\\?\unc\` 與 `\\?\X:\` 兩種改寫，沒有沿用。
- 依據：安全（路徑授權）；錯誤處理。變更前的釘選必須覆蓋即將開啟的那個檔案。
- 狀態：未關閉
- 建議：只剝除 `\\?\` 加磁碟機代號的形式；`\\?\UNC`、`\\?\Volume`、`\\.\` 在 `abspath` 之前直接拒絕。釘選與原生開啟必須使用同一條已檢查路徑。

#### CR-03

- 嚴重度：建議
- 位置：`D:\Codes\FileTree\je_file_tree\core\mft_scan.py`（`_read` 169–176、`build` 227–239）
- 說明：資料夾列舉的 `PermissionError` 會記成 `access denied` 並繼續，沒有整棵中止。其他 `OSError` 與 `ValueError`（例如原生名稱含分隔字元、非拒絕存取的 WinError）不在 `_read` 內處理，落到 `build` 後只以 debug 記錄並回傳 `None`。呼叫端接著做一般掃描，`ScanResult.warnings` 沒有「實驗審查已捨棄」的說明。最終一般掃描仍會記錄權限錯誤，不會把不可讀資料夾顯示成空目錄；被吞的是實驗後端失敗本身。此路徑是選擇性的，預設關閉，設定還原也拒絕 `experimental_mft=True`。
- 依據：錯誤處理。與一般掃描器「單一資料夾失敗只記錯誤」以及文件「退回一般掃描」相比，缺少可見的退回原因。
- 狀態：未關閉
- 建議：資料夾層的 `OSError` 比照 `scanner._read_folder` 記入錯誤後繼續；若仍要整批捨棄候選樹，請在一般掃描結果的 `warnings` 留下固定原因，不要只寫 debug。

#### CR-04

- 嚴重度：建議
- 位置：`D:\Codes\FileTree\je_file_tree\gui\file_actions.py`（`explorer_command` 34–38、`reveal_in_file_manager` 49–50）
- 說明：沒有 `shell=True`。路徑拒絕控制字元與雙引號，Windows 上以命令列字串交給 `CreateProcess`，`&` 不會被殼層解釋。程式名是 `explorer`，沿 `PATH` 搜尋，不同於同套件以系統目錄定位的 `compact.exe`／`wsl.exe`，也不同於 `/usr/bin/open`。磁碟根目錄正規化後仍是 `C:\`，命令列成為 `explorer /select,"C:\"`，結尾反斜線會吃掉關閉引號，根目錄「顯示於檔案總管」可能選錯或失敗。後面沒有其他字元，這不是命令注入。
- 依據：安全（subprocess 應為固定程式）；專案規則已點名 `explorer /select,` 必須自行加引號。
- 狀態：未關閉
- 建議：使用 Windows 目錄下的 `explorer.exe` 絕對路徑；引號內的結尾反斜線要再跳脫，或以參數陣列組出不會把 `\"` 當成結束引號的命令列。

沒有其他未關閉缺陷。裸 `except:`、`shell=True`、`pickle`、`yaml.load`、`verify=False` 與 Python `eval`／`exec` 在 `je_file_tree` 沒有命中。

### 總評

一般掃描的權限失敗有處理：`_read_folder` 捕捉 `OSError`（含 `PermissionError`），`_describe` 把 `EACCES`／`EPERM` 記成 `access denied`，結果留在 `ScanResult.errors`，掃描繼續，且不跟隨 symlink／junction。多執行緒這條契約不完整，工作者在讀取以外失敗時可能被吞掉並仍回傳成功掃描，這是必須修正的缺陷。虛擬磁碟壓縮的延伸路徑釘選會把 UNC／Volume 形式改寫到目前工作目錄，與自身註解衝突，也必須修正。實驗 MFT 的非權限失敗與檔案總管命令列是建議，不單獨構成立即損害，但缺陷未關，結論不能是有條件通過。

### 已核對

- 壓縮檔成員名稱拒絕空段、`.`、`..` 與磁碟機冒號；只讀中繼資料，不解出成員（`core\archives.py`）。
- `MountSurvey` 對根目錄 `PermissionError` 只記在物件上，列舉時再丟出，由掃描器記入錯誤，不穿越（`core\mounts.py`）。
- 多根掃描的單一 `OSError` 留在該根節點與 `errors`，不中止其他根（`core\multi_scan.py`）。
- Git 使用參數陣列、`shell` 維持預設關閉、`-C` 與路徑分開；`abspath` 後不會以 `-` 開頭。程式名仍是 `PATH` 上的 `git`。環境去掉外來 `GIT_*`，並關閉 lazy fetch。這是備註，不另開編號。
- `compact.exe`、`wsl.exe`、`osascript`、`open` 為固定或系統目錄路徑，沒有 shell。提升權限走 `ShellExecuteExW` 的 `runas`，參數先經 `list2cmdline`。
- 連結目標的 `is_dir(follow_symlinks=True)` 在 `OSError` 時回傳 False，不進入掃描佇列（`_points_to_folder`）。權限失敗不會多記一筆錯誤，但連結本身仍列出且不往下走。
- 重複檔雜湊的 `OSError` 計入 `skipped` 並排除該檔，不會把它當成內容相同（`core\duplicates.py`）。
- 單檔 `FileNotFoundError` 在列舉競態時略過、不記錯誤；整資料夾消失仍以 `OSError` 記入。這與掃描器說明一致。
- `progress.md` 開頭的未完成項是原生環境驗證，與本次兩則缺陷不是同一件事，本審核不關閉它們。

### 未涵蓋

- 未執行測試、lint、GUI，也沒有對真實拒絕存取目錄做原生掃描。
- 未審 `build/`、`test/`、`tools/` 的實作品質；只確認實驗 MFT 的套件內入口預設關閉。
- `architecture.md` §6 後半（SMB 驗證、APFS 卸載、MSI、打包）未逐段對照實作。
- 未逐函式測量複雜度、行數與巢狀。`main_window.py` 一類大型 GUI 檔不在本熱點。
- 回收筒、永久清空、硬連結替換與複製的全部分支只沿安全規則抽讀，沒有重審每一條刪除路徑。

### 本專案加嚴

- `je_file_tree.core` 不得匯入 Qt 或 GUI。熱點核心檔沒有這樣的匯入；未重跑分層測試。
- 掃描不得跟隨連結，不可讀資料夾必須進入 `ScanResult.errors`。一般掃描器符合；CR-01 與 CR-03 是這條規則的缺口。
- 不得永久刪除使用者掃描結果。本熱點的 subprocess 沒有刪除命令。
- subprocess 不得使用 shell，且應為固定程式。套件內沒有 `shell=True`；CR-04 的 `explorer` 仍非絕對路徑。
- 可讀性上限與規範第 2 條相同，未見熱點函式以裸 `except` 或 `print` 逃避錯誤。

### 結論

需修正。未關閉缺陷 2 則（CR-01、CR-02），建議 2 則（CR-03、CR-04）。建議不阻擋通過，但缺陷未關，不得視為通過或有條件通過。

## 修正確認（2026-10-23）

以上保留原始審核快照；目前四項程式碼發現均已修正：

- CR-01：工作者完整生命週期保留第一個例外，工作計數於 finally 扣回，全部 join 後重丟。GUI／CLI 終端邊界回報非預期失敗，分析失敗不發布成功訊號。
- CR-02：UNC、裝置與相對路徑在釘選前拒絕；延伸磁碟機前綴保留到原生開啟。非 Windows 平台先行拒絕。
- CR-03：明確要求 MFT 後的退回會加入 ScanResult.warnings，GUI 以五語系掃描注意事項顯示。
- CR-04：透過原生 Windows 目錄 API 定位 explorer.exe，尾端反斜線依命令列引號規則處理。

修正前的回歸案例重現 16 個失敗。完整測試 2695 passed、54 skipped，退出碼 0；最後的平台防線與文件對帳測試 120 passed，Ruff 通過。Windows 原生 CommandLineToArgvW 驗證參數完整，但不代表已目視確認 Explorer 選取結果，該項保留於 progress.md #115。既有原生環境限制仍維持開啟。證據見 U-20261023-01。
