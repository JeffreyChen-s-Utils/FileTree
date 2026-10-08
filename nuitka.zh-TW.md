# 用 Nuitka 編譯 FileTree

[English](nuitka.md) | [繁體中文](nuitka.zh-TW.md) | [简体中文](nuitka.zh-CN.md) | [日本語](nuitka.ja.md) | [한국어](nuitka.ko.md)

macOS arm64 原生編譯與套件打包已通過 Desktop builds [37788683269](https://github.com/JeffreyChen-s-Utils/FileTree/actions/runs/37788683269)：167 個來源項目全部保留，解壓內容一致。這份證據確認該提交的編譯與打包，未啟動或發佈程式。Finder／同意驗證與 Developer ID／公證仍缺環境，因此 POSIX 發行閘門維持關閉。

Windows 發行版可明確啟用 Azure Artifact Signing 的 OIDC 簽章；已啟用但設定缺漏，或簽章、時間戳、發行者驗證失敗時會停止發佈。單檔與獨立資料夾執行檔在打包前驗證，MSI 在上傳與套件清單雜湊前驗證。開發建置維持未簽署。目前仍缺帳號與原生成功簽署驗證，請參閱 [Windows 簽章設定](docs/windows-signing.md)。

[Nuitka](https://nuitka.net/) 會把 FileTree 編譯成原生程式，沒有安裝 Python 的電腦也能執行。它把 Python 程式碼轉成 C 再編譯，所以程式啟動很快；代價是編譯時間比較長。它編譯的進入點是 repo 根目錄的 `start_file_tree.py`。

> Nuitka 只能編譯出執行它的那個系統的程式：在 Windows 上編 Windows 版、在 macOS 上編 macOS 版、在 Linux 上編 Linux 版，不能交叉編譯。

圖表 SVG 匯出使用 PySide6.QtSvg，Nuitka 會依匯入包含 Qt SVG 程式庫，與視窗使用相同的 PySide6 相依套件。

列印與畫面 PDF 匯出使用 PySide6.QtPrintSupport，由既有的 PySide6 外掛收集。原生列印需要系統印表機服務，PDF 輸出使用 Qt 的 PDF 引擎。

## 1. 準備

Excel 報告在僅使用標準程式庫的核心之外匯入 `openpyxl`。編譯前先安裝 `requirements.txt`，Nuitka 會收集此匯入與其 `et-xmlfile` 相依套件。執行檔發行依 `.github/requirements/reports.txt` 的已驗證雜湊安裝通用 wheel，與發布工作使用的工具鎖定檔獨立。HTML 內嵌 Qt 編碼的 PNG，不需要瀏覽器或影像相依套件。

壓縮檔預覽在僅使用標準程式庫的核心之外，按需匯入 `py7zr` 與 `rarfile`。編譯前安裝 `requirements.txt`，Nuitka 會依配接器匯入收集解碼相依套件。原生 Windows／Linux／macOS Python 3.12 發行 wheel 依 `.github/requirements/archives.txt` 的已驗證雜湊鎖定。未附帶外部 RAR 工具：PATH 須有 `unrar` 或 `bsdtar`；預覽不會執行這些工具或解壓縮。

相似照片搜尋只在需要時於僅使用標準程式庫的核心之外匯入 `Pillow`。Nuitka 會依影像配接器匯入收集原生解碼程式庫。原生 Windows／Linux／macOS Python 3.12 建置依 `.github/requirements/photos.txt` 的已驗證二進位 wheel 鎖定；本機編譯前先安裝 `requirements.txt`。未附帶外部影像程式或模型資產。

使用 py -3 tools/lock_compiler_wheels.py 重產編譯執行階段雜湊：保留全部固定相依套件版本，已發布 wheel 雜湊涵蓋原生平台，排除原始碼與已撤回產物。不變更獨立的 PyPI 發布鎖定檔。

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

在具有 .NET 8 SDK 的 Windows 上，可從同一份完整獨立程式輸出建置 x64 MSI：

```bash
dotnet tool install wix --global --version 6.0.2
python tools/build_msi.py --version 0.1.0
python tools/prepare_packages.py --version 0.1.0
```

這會產生 `FileTree-0.1.0-windows-x64.msi`。工具會核對編譯器版本；程式內容有連結、不支援的 MSI 版本、執行階段檔案清單變動或建置失敗時，都拒絕發布。WiX 驗證保持啟用。為所有使用者安裝的套件包含全部執行階段檔案與開始功能表捷徑，支援主要版本升級，不使用自訂動作／啟動登錄。安裝需要系統管理員核准；建置工具只編譯。發版流程會附上同一個標籤的 MSI。Desktop builds 流程透過 `tools/install_compiler.py` 共用發版流程釘選的工具，實際編譯獨立程式，並保留 ZIP／MSI 及原生安裝／升級／移除證據。套件版本升級驗證將編譯內容複製到主機新建暫存區，只新增自有標記；原始輸出會保留且不啟動。原生安裝／升級／移除核對已通過全部 104 個升級後檔案；這些檢查不能證明介面啟動或系統授權。草稿指令需要目前目錄中的相符 MSI 與獨立程式 ZIP，建立全新 `package-drafts` 資料夾，包含實際雜湊／ProductCode、winget 資訊清單、Scoop 資訊清單與 Chocolatey 套件原始碼。唯讀 MSI 檢查不安裝任何內容。原生 winget 驗證已通過，不提交商店。CI 保留草稿，發版附上草稿 ZIP；仍需要商店帳號與相符的已發布產物網址。

### 2.2 單一檔案

```bash
python tools/build_nuitka.py --onefile
```

產物只有一個檔案：`build/onefile/FileTree.exe`（其他系統是 `build/onefile/FileTree`）。方便傳送，但每次啟動都要先解壓到暫存資料夾，所以開啟會稍微慢一點。

### 2.3 macOS 應用程式套件

```bash
python tools/build_nuitka.py --app
python tools/package_posix.py --platform macos --source build/app/start_file_tree.app --version 0.1.0
```

編譯套件是 `build/app/start_file_tree.app`；打包在 ZIP 內建立獨立 `FileTree.app`，封裝前及解壓後都核對完整內容。打包指令將完整 ZIP 與證據寫入全新 `desktop-package` 資料夾。原生 ditto 解壓必須保留每個一般檔案與內部 framework 連結，並核對套件識別碼／版本／執行檔；拒絕外部連結。

在 Windows、Linux 與 macOS 上，程式會帶著 FileTree 自己的圖示（腳本把它畫到 `build/`）。其他選項會原封不動交給 Nuitka，例如換一個圖示：`python tools/build_nuitka.py --windows-icon-from-ico=icon.ico`（Windows）、`--linux-icon=icon.png` 或 `--macos-app-icon=icon.icns`。macOS 腳本透過 Qt 的 PNG 編碼器直接產生原生多尺寸 ICNS，無須 Nuitka 的選用 PNG 轉換相依套件。

### 2.4 Linux AppImage

```bash
python tools/build_nuitka.py --jobs=2
python tools/package_posix.py --platform linux --source build/standalone/start_file_tree.dist --version 0.1.0
```

若資料夾名稱不同，請改用實際唯一的 `.dist`。原生 x86_64 Linux 打包保留完整 Qt 執行階段與翻譯，並加入固定參數的 AppRun 與產生的圖示。封裝工具 1.9.1 與 runtime 20251108 釘選 SHA-256；明確指定 runtime，不下載最新版本。封裝不需要 FUSE 掛載。原生解壓必須符合完整執行階段，來源雜湊／識別碼也須保持不變。AppImage 與證據一起發布至全新 `desktop-package`，拒絕覆寫既有或新到達項目。

Desktop builds CI 使用 Ubuntu 22.04 x86_64 與 macOS 15 arm64，保留開發產物七天，不使用發版權杖或啟動程式。發版重用受儲存庫變數 `FILETREE_POSIX_RELEASE_VERIFIED=true` 控制，只能在進度項目 #4 驗證後設定。本次變更不設定變數，也不提供 Developer ID 簽章／公證或證明 Finder／系統授權。AppImage 登入登錄使用掛載外的原始執行檔。

## 3. 腳本執行的選項

| 選項 | 用途 |
|---|---|
| `--mode=standalone`／`--mode=onefile`／`--mode=app` | 程式資料夾、單一檔案，或（macOS）應用程式套件 |
| `--enable-plugin=pyside6` | 複製視窗需要的 Qt 函式庫與外掛 |
| `--include-data-files=<Qt 翻譯資料夾>/qtbase_zh_TW.qm=<編譯結果裡的同一個位置>`（以及 `qtbase_zh_CN.qm`, `qtbase_ja.qm`, `qtbase_ko.qm`） | Nuitka 不會複製 Qt 自己的翻譯檔；少了它們，「是／否／關閉」按鈕會停在英文。這個資料夾隨安裝方式而不同（Windows 是 `PySide6/translations`，Linux 是 `PySide6/Qt/translations`），這就是用腳本來編譯的原因 |
| `--windows-console-mode=disable` | Windows 上不會在 FileTree 旁邊多開一個黑色主控台視窗（其他系統會忽略） |
| `--output-dir=build/standalone`（或 `build/onefile`、`build/app`） | Nuitka 產生的東西都放在 `build/`，Git 會忽略這個資料夾；每種形式各有自己的資料夾，編其中一種不會刪掉另一種 |
| `--output-filename=FileTree` | 程式叫 FileTree，而不是 start_file_tree |
| `--assume-yes-for-downloads` | 讓 Nuitka 不經詢問就下載它需要的輔助工具 |
| `--windows-icon-from-ico=build/FileTree.ico`／`--linux-icon=build/FileTree.png`／`--macos-app-icon=build/FileTree.icns` | FileTree 的圖示，由腳本畫出來（你自己指定圖示時就不加） |
| `--macos-app-name=FileTree`（只在 `--app` 時） | 在 Finder 與 Dock 顯示的名稱 |
| `--macos-signed-app-name=io.github.jechen.FileTree`（只在 `--app` 時） | 固定套件識別碼，不提供 Developer ID 憑證 |
| `--macos-app-version=<儲存庫版本>`（只在 `--app` 時） | 套件版本符合程式，不手動更新版本 |

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
