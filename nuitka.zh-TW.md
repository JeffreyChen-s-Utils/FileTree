# 用 Nuitka 編譯 FileTree

[English](nuitka.md) | [繁體中文](nuitka.zh-TW.md) | [简体中文](nuitka.zh-CN.md)

[Nuitka](https://nuitka.net/) 會把 FileTree 編譯成原生程式，沒有安裝 Python 的電腦也能執行。它把 Python 程式碼轉成 C 再編譯，所以程式啟動很快；代價是編譯時間比較長。它編譯的進入點是 repo 根目錄的 `start_file_tree.py`。

> Nuitka 只能編譯出執行它的那個系統的程式：在 Windows 上編 Windows 版、在 macOS 上編 macOS 版、在 Linux 上編 Linux 版，不能交叉編譯。

圖表 SVG 匯出使用 PySide6.QtSvg，Nuitka 會依匯入包含 Qt SVG 程式庫，與視窗使用相同的 PySide6 相依套件。

## 1. 準備

### 1.1 Python 套件（每個系統都要）

用虛擬環境，編出來的程式才只包含 FileTree 需要的東西：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install nuitka ordered-set zstandard
```

在 macOS 與 Linux 上改用 `source .venv/bin/activate` 啟用。

### 1.2 C 編譯器

| 系統 | 要安裝什麼 |
|---|---|
| Windows | Visual Studio Build Tools，勾選「使用 C++ 的桌面開發」工作負載。沒有的話，Nuitka 第一次編譯時會提議下載 MinGW64（加上 `--assume-yes-for-downloads` 會自動同意）。 |
| Linux | `build-essential` 與 `patchelf`（Debian／Ubuntu：`sudo apt install build-essential patchelf`） |
| macOS | 命令列工具：`xcode-select --install` |

## 2. 編譯

在 repo 根目錄、啟用虛擬環境後執行。`tools/build_nuitka.py` 會找出 PySide6 裝在哪裡，再用 §3 的選項執行 Nuitka，也會印出完整的指令。

### 2.1 程式資料夾（建議）

```bash
python tools/build_nuitka.py
```

產物是 `build/standalone/start_file_tree.dist/` 資料夾，裡面有 `FileTree.exe`（Linux 與 macOS 是 `FileTree`）。要給別台電腦用時，複製**整個資料夾**過去，從裡面啟動程式。這種方式啟動最快。

Windows 發版時可打包完整資料夾（請使用發版的版本號）：

```bash
python tools/package_standalone.py --version 0.1.0
```

這會在儲存庫根目錄產生 `FileTree-0.1.0-windows-standalone.zip`，內含帶版本號的資料夾及 EXE、所有程式庫、外掛與翻譯檔。`build/standalone` 下必須恰有一個包含 `FileTree.exe` 的完整 `.dist` 資料夾；工具拒絕連結／接合點，以原子方式寫入壓縮檔。發版流程會從同一個標籤建置兩種形式，同時附上完整資料夾 ZIP 與單檔 EXE。

### 2.2 單一檔案

```bash
python tools/build_nuitka.py --onefile
```

產物只有一個檔案：`build/onefile/FileTree.exe`（其他系統是 `build/onefile/FileTree`）。方便傳送，但每次啟動都要先解壓到暫存資料夾，所以開啟會稍微慢一點。

### 2.3 macOS 應用程式套件

```bash
python tools/build_nuitka.py --app
```

產物是 `build/app/FileTree.app`。

在 Windows 與 Linux 上，程式會帶著 FileTree 自己的圖示（腳本把它畫到 `build/`）。其他選項會原封不動交給 Nuitka，例如換一個圖示：`python tools/build_nuitka.py --windows-icon-from-ico=icon.ico`（Windows）、`--linux-icon=icon.png` 或 `--macos-app-icon=icon.icns`（macOS 否則沒有圖示）。

## 3. 腳本執行的選項

| 選項 | 用途 |
|---|---|
| `--mode=standalone`／`--mode=onefile`／`--mode=app` | 程式資料夾、單一檔案，或（macOS）應用程式套件 |
| `--enable-plugin=pyside6` | 複製視窗需要的 Qt 函式庫與外掛 |
| `--include-data-files=<Qt 翻譯資料夾>/qtbase_zh_TW.qm=<編譯結果裡的同一個位置>`（以及 `qtbase_zh_CN.qm`） | Nuitka 不會複製 Qt 自己的翻譯檔；少了它們，「是／否／關閉」按鈕會停在英文。這個資料夾隨安裝方式而不同（Windows 是 `PySide6/translations`，Linux 是 `PySide6/Qt/translations`），這就是用腳本來編譯的原因 |
| `--windows-console-mode=disable` | Windows 上不會在 FileTree 旁邊多開一個黑色主控台視窗（其他系統會忽略） |
| `--output-dir=build/standalone`（或 `build/onefile`、`build/app`） | Nuitka 產生的東西都放在 `build/`，Git 會忽略這個資料夾；每種形式各有自己的資料夾，編其中一種不會刪掉另一種 |
| `--output-filename=FileTree` | 程式叫 FileTree，而不是 start_file_tree |
| `--assume-yes-for-downloads` | 讓 Nuitka 不經詢問就下載它需要的輔助工具 |
| `--windows-icon-from-ico=build/FileTree.ico`／`--linux-icon=build/FileTree.png` | FileTree 的圖示，由腳本畫出來（你自己指定圖示時就不加） |
| `--macos-app-name=FileTree`（只在 `--app` 時） | 在 Finder 與 Dock 顯示的名稱 |

進入點是 `start_file_tree.py`，和 `python -m je_file_tree` 是同一個程式。

## 4. 檢查編譯結果

1. 從編譯出來的資料夾啟動程式，掃描一個資料夾。
2. 在「檢視 → 語言」切換到另一種語言，然後把某個項目移到資源回收筒並按取消：「是／否」按鈕也要是那種語言。如果還是英文，表示編譯結果裡少了 Qt 的翻譯檔。
3. 開啟「說明 → 使用說明」。

## 5. 常見問題

| 看到什麼 | 怎麼處理 |
|---|---|
| 編譯出來的程式「是／否／關閉」還是英文 | 是直接手動執行 Nuitka、少了翻譯檔。請改用 `python tools/build_nuitka.py` 編譯，它會把翻譯檔加進去。 |
| Nuitka 因為沒有 C 編譯器而停止 | 照 §1.2 安裝編譯器。在 Windows 上沒有 Visual Studio 時，Nuitka 會自己下載 MinGW64（腳本已經替你同意）。 |
| 編譯時其他程式變得很慢 | Nuitka 會用上所有 CPU 核心。加上 `--jobs=2`（`python tools/build_nuitka.py --jobs=2`）就能留下餘裕給其他程式。 |
| 第一次編譯很久 | 正常：Nuitka 第一次會把 Qt 的 Python 綁定編譯好並重複使用，之後就會快很多。 |
| 防毒軟體把新的 `.exe` 隔離了 | 新的、沒有簽章的執行檔有時會被誤判。把編譯資料夾加入例外，或幫程式簽章。 |
| 找不到 `patchelf`（Linux） | `sudo apt install patchelf` 之後再編譯一次。 |
