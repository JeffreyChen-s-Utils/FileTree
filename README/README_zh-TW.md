# FileTree

**快速找出磁碟空間都被什麼占用了。**

FileTree 會掃描資料夾或磁碟，列出最占空間的檔案與資料夾。
透過資料夾樹、彩色方塊圖和最大檔案清單，幫你決定哪些要保留、哪些可以清理。

[English](../README.md) | [繁體中文](README_zh-TW.md) | [简体中文](README_zh-CN.md) | [日本語](README_ja.md) | [한국어](README_ko.md)

![FileTree：左側顯示資料夾大小，右側用方塊圖呈現空間分布](../docs/images/main_window_zh-TW.png)

## 可以做什麼

- **找出大檔案、大資料夾**：從最大的項目開始看，用圖表了解空間占比。
- **搜尋與篩選**：依名稱、類型、大小或修改時間找檔案。
- **查看清理建議**：檢視快取、暫存檔和重複檔案，再決定是否處理。
- **找出變大的資料夾**：比較前後兩次掃描，看看空間增加在哪裡。
- **匯出報表**：將結果存成 CSV、JSON 或 Excel。
- **切換語言**：支援英文、繁體中文、簡體中文、日文和韓文。

## 安裝

### Windows：免安裝 Python

1. 到 [Releases](https://github.com/JeffreyChen-s-Utils/FileTree/releases) 下載 `FileTree-<version>-windows-standalone.zip`。
2. **完整解壓縮** ZIP 檔。
3. 執行資料夾內的 `FileTree.exe`，其他檔案請一起保留。

也提供 MSI 安裝程式，可透過 Windows 安裝。

### Windows、macOS、Linux：使用 Python

需要 **Python 3.10 以上**：

```bash
python -m pip install je_file_tree
je-file-tree
```

Windows 可以用 `py -3` 代替 `python`。
從原始碼執行或編譯成獨立程式，請看[完整說明](../docs/guide_zh-TW.md)與[編譯指南](../nuitka.zh-TW.md)。

## 開始使用

1. **選擇資料夾或磁碟**，也可以直接把資料夾拖進視窗。
2. **等待掃描完成**，查看最大的資料夾和檔案。圖上的方塊越大，表示占用空間越多。
3. **確認不需要的項目**，按右鍵 → **移到資源回收筒**。程式會先詢問確認。

掃描途中可以隨時停止；已讀取的結果會保留，並標示為不完整。

## 使用前知道這些就好

- 檔案移到資源回收筒後，**要清空資源回收筒才會釋出空間**。
- 清理建議需要自行檢查。背景監視預設關閉，也不會自動清理。
- 沒有讀取權限的資料夾會列在**無法讀取**分頁中，裡面的內容不會計入總大小。
- 掃描不會跟隨符號連結或接合點。檔案大小與實際占用磁碟空間可能不同。
- Windows 啟動時可能詢問系統管理員權限；拒絕後仍可掃描有權限讀取的資料夾。
- 清空資源回收筒、將重複檔案改成硬連結等進階操作，有各自的確認步驟與影響；使用前請看[完整說明](../docs/guide_zh-TW.md)。

## 常用快速鍵

| 按鍵 | 功能 |
|---|---|
| Ctrl+O | 選擇資料夾 |
| F5 | 重新掃描 |
| Esc | 停止掃描 |
| Ctrl+F | 搜尋 |
| Delete | 將選取項目移到資源回收筒 |
| F1 | 開啟說明 |
| Ctrl+Q | 結束程式 |

macOS 請用 ⌘ 代替 Ctrl，重新掃描則用 ⌘R。

## 更多說明

- [完整使用說明與技術細節](../docs/guide_zh-TW.md)：所有功能、命令列範例、設定與限制。
- [編譯指南](../nuitka.zh-TW.md)：用 Nuitka 建立獨立程式。
- [核心 API](../docs/core-api.md)與[專案架構](../architecture.md)：串接或開發 FileTree。
- [更新紀錄](../docs/updates/README.md)：功能變更與驗證紀錄。

## 授權

[MIT](../LICENSE)。
