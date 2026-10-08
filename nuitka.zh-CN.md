# 用 Nuitka 编译 FileTree

[English](nuitka.md) | [繁體中文](nuitka.zh-TW.md) | [简体中文](nuitka.zh-CN.md) | [日本語](nuitka.ja.md) | [한국어](nuitka.ko.md)

macOS arm64 原生编译与打包已通过 Desktop builds [37788683269](https://github.com/JeffreyChen-s-Utils/FileTree/actions/runs/37788683269)：167 个源项目全部保留，解压内容一致。该证据确认此提交的编译与打包，未启动或发布程序。Finder／同意验证与 Developer ID／公证仍缺环境，因此 POSIX 发布门控保持关闭。

Windows 发行版可显式启用 Azure Artifact Signing 的 OIDC 签名；已启用但配置缺失，或签名、时间戳、发布者验证失败时会停止发布。单文件与独立文件夹可执行文件在打包前验证，MSI 在上传与软件包清单哈希前验证。开发构建保持未签名。目前仍缺账号与原生成功签署验证，请参阅 [Windows 签名设置](docs/windows-signing.md)。

[Nuitka](https://nuitka.net/) 会把 FileTree 编译成原生程序，没有安装 Python 的电脑也能运行。它把 Python 代码转成 C 再编译，所以程序启动很快；代价是编译时间比较长。它编译的入口是仓库根目录的 `start_file_tree.py`。

> Nuitka 只能编译出运行它的那个系统的程序：在 Windows 上编 Windows 版、在 macOS 上编 macOS 版、在 Linux 上编 Linux 版，不能交叉编译。

图表 SVG 导出使用 PySide6.QtSvg，Nuitka 会按导入包含 Qt SVG 库，与窗口使用相同的 PySide6 依赖包。

打印与视图 PDF 导出使用 PySide6.QtPrintSupport，由现有的 PySide6 插件收集。原生打印需要系统打印机服务，PDF 输出使用 Qt 的 PDF 引擎。

## 1. 准备

Excel 报告在仅使用标准库的核心之外导入 `openpyxl`。编译前先安装 `requirements.txt`，Nuitka 会收集此导入与其 `et-xmlfile` 依赖包。可执行文件发布按 `.github/requirements/reports.txt` 的已验证哈希安装通用 wheel，与发布任务使用的工具锁定文件独立。HTML 内嵌 Qt 编码的 PNG，不需要浏览器或图像依赖包。

压缩文件预览在仅使用标准库的核心之外，按需导入 `py7zr` 与 `rarfile`。编译前安装 `requirements.txt`，Nuitka 会按适配器导入收集解码依赖包。原生 Windows／Linux／macOS Python 3.12 发布 wheel 按 `.github/requirements/archives.txt` 的已验证哈希锁定。未附带外部 RAR 工具：PATH 须有 `unrar` 或 `bsdtar`；预览不会运行这些工具或解压。

相似照片搜索只在需要时于仅使用标准库的核心之外导入 `Pillow`。Nuitka 会按图像适配器导入收集原生解码库。原生 Windows／Linux／macOS Python 3.12 构建按 `.github/requirements/photos.txt` 的已验证二进制 wheel 锁定；本地编译前先安装 `requirements.txt`。未附带外部图像程序或模型资源。

使用 py -3 tools/lock_compiler_wheels.py 重新生成编译运行时哈希：保留全部固定依赖版本，已发布 wheel 哈希覆盖原生平台，排除源代码与已撤回产物。不变更独立的 PyPI 发布锁文件。

### 1.1 Python 包（每个系统都要）

使用虚拟环境，编出来的程序才只包含 FileTree 需要的东西：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install nuitka ordered-set zstandard
```

在 macOS 与 Linux 上改用 `source .venv/bin/activate` 激活。

### 1.2 C 编译器

| 系统 | 要安装什么 |
|---|---|
| Windows | Visual Studio Build Tools，勾选“使用 C++ 的桌面开发”工作负载。没有的话，Nuitka 第一次编译时会提议下载 MinGW64（加上 `--assume-yes-for-downloads` 会自动同意）。 |
| Linux | `build-essential` 与 `patchelf`（Debian／Ubuntu：`sudo apt install build-essential patchelf`） |
| macOS | 命令行工具：`xcode-select --install` |

## 2. 编译

在仓库根目录、激活虚拟环境后运行。`tools/build_nuitka.py` 会找出 PySide6 装在哪里，再用 §3 的选项运行 Nuitka，也会打印完整的命令。

### 2.1 程序文件夹（推荐）

```bash
python tools/build_nuitka.py
```

产物是 `build/standalone/start_file_tree.dist/` 文件夹，里面有 `FileTree.exe`（Linux 与 macOS 是 `FileTree`）。要给别的电脑用时，复制**整个文件夹**过去，从里面启动程序。这种方式启动最快。

Windows 发布时可打包完整文件夹（请使用发布的版本号）：

```bash
python tools/package_standalone.py --version 0.1.0
```

这会在仓库根目录生成 `FileTree-0.1.0-windows-standalone.zip`，内含带版本号的文件夹及 EXE、所有程序库、插件与翻译文件。`build/standalone` 下必须恰有一个包含 `FileTree.exe` 的完整 `.dist` 文件夹；工具拒绝链接／联接点，以原子方式写入压缩包。发布流程会从同一个标签构建两种形式，同时附上完整文件夹 ZIP 与单文件 EXE。

在具有 .NET 8 SDK 的 Windows 上，可从同一份完整独立程序输出构建 x64 MSI：

```bash
dotnet tool install wix --global --version 6.0.2
python tools/build_msi.py --version 0.1.0
python tools/prepare_packages.py --version 0.1.0
```

这会生成 `FileTree-0.1.0-windows-x64.msi`。工具会核对编译器版本；程序内容有链接、不支持的 MSI 版本、运行时文件清单变化或构建失败时，都拒绝发布。WiX 验证保持启用。为所有用户安装的包包含全部运行时文件与开始菜单快捷方式，支持主要版本升级，不使用自定义操作／启动注册。安装需要管理员批准；构建工具只编译。发布流程会附上同一个标签的 MSI。Desktop builds 流程通过 `tools/install_compiler.py` 共用发布流程锁定的工具，实际编译独立程序，并保留 ZIP／MSI 及原生安装／升级／移除证据。包版本升级验证将编译内容复制到主机新建临时目录，只添加自有标记；原始输出会保留且不启动。原生安装／升级／移除核对已通过全部 104 个升级后文件；这些检查不能证明界面启动或系统授权。草稿命令需要当前目录中的匹配 MSI 与独立程序 ZIP，创建全新 `package-drafts` 文件夹，包含实际哈希／ProductCode、winget 清单、Scoop 清单与 Chocolatey 包源代码。只读 MSI 检查不安装任何内容。原生 winget 验证已通过，不提交商店。CI 保留草稿，发布附上草稿 ZIP；仍需要商店账号与匹配的已发布产物网址。

### 2.2 单个文件

```bash
python tools/build_nuitka.py --onefile
```

产物只有一个文件：`build/onefile/FileTree.exe`（其他系统是 `build/onefile/FileTree`）。方便传送，但每次启动都要先解压到临时文件夹，所以打开会稍微慢一点。

### 2.3 macOS 应用程序包

```bash
python tools/build_nuitka.py --app
python tools/package_posix.py --platform macos --source build/app/start_file_tree.app --version 0.1.0
```

编译包是 `build/app/start_file_tree.app`；打包在 ZIP 内建立独立 `FileTree.app`，封装前及解压后都核对完整内容。打包命令将完整 ZIP 与证据写入全新 `desktop-package` 文件夹。原生 ditto 解压必须保留每个普通文件与内部 framework 链接，并核对包标识／版本／可执行文件；拒绝外部链接。

在 Windows、Linux 与 macOS 上，程序会带着 FileTree 自己的图标（脚本把它画到 `build/`）。其他选项会原样交给 Nuitka，例如换一个图标：`python tools/build_nuitka.py --windows-icon-from-ico=icon.ico`（Windows）、`--linux-icon=icon.png` 或 `--macos-app-icon=icon.icns`。macOS 脚本通过 Qt 的 PNG 编码器直接生成原生多尺寸 ICNS，无需 Nuitka 的可选 PNG 转换依赖包。

### 2.4 Linux AppImage

```bash
python tools/build_nuitka.py --jobs=2
python tools/package_posix.py --platform linux --source build/standalone/start_file_tree.dist --version 0.1.0
```

若文件夹名称不同，请改用实际唯一的 `.dist`。原生 x86_64 Linux 打包保留完整 Qt 运行时与翻译，并加入固定参数的 AppRun 与生成的图标。封装工具 1.9.1 与 runtime 20251108 锁定 SHA-256；明确指定 runtime，不下载最新版本。封装不需要 FUSE 挂载。原生解压必须符合完整运行时，来源哈希／标识也须保持不变。AppImage 与证据一起发布至全新 `desktop-package`，拒绝覆盖既有或新到达的项目。

Desktop builds CI 使用 Ubuntu 22.04 x86_64 与 macOS 15 arm64，保留开发产物七天，不使用发布令牌或启动程序。发布复用受仓库变量 `FILETREE_POSIX_RELEASE_VERIFIED=true` 控制，只能在进度项目 #4 验证后设置。本次变更不设置变量，也不提供 Developer ID 签名／公证或证明 Finder／系统授权。AppImage 登录注册使用挂载外的原始可执行文件。

## 3. 脚本运行的选项

| 选项 | 用途 |
|---|---|
| `--mode=standalone`／`--mode=onefile`／`--mode=app` | 程序文件夹、单个文件，或（macOS）应用程序包 |
| `--enable-plugin=pyside6` | 复制窗口需要的 Qt 库与插件 |
| `--include-data-files=<Qt 翻译文件夹>/qtbase_zh_TW.qm=<编译结果里的同一个位置>`（以及 `qtbase_zh_CN.qm`, `qtbase_ja.qm`, `qtbase_ko.qm`） | Nuitka 不会复制 Qt 自己的翻译文件；缺了它们，“是／否／关闭”按钮会停在英文。这个文件夹随安装方式而不同（Windows 是 `PySide6/translations`，Linux 是 `PySide6/Qt/translations`），这就是用脚本来编译的原因 |
| `--windows-console-mode=disable` | Windows 上不会在 FileTree 旁边多开一个黑色控制台窗口（其他系统会忽略） |
| `--output-dir=build/standalone`（或 `build/onefile`、`build/app`） | Nuitka 生成的东西都放在 `build/`，Git 会忽略这个文件夹；每种形式各有自己的文件夹，编其中一种不会删掉另一种 |
| `--output-filename=FileTree` | 程序叫 FileTree，而不是 start_file_tree |
| `--assume-yes-for-downloads` | 让 Nuitka 不经询问就下载它需要的辅助工具 |
| `--windows-icon-from-ico=build/FileTree.ico`／`--linux-icon=build/FileTree.png`／`--macos-app-icon=build/FileTree.icns` | FileTree 的图标，由脚本画出来（你自己指定图标时就不加） |
| `--macos-app-name=FileTree`（只在 `--app` 时） | 在 Finder 与 Dock 显示的名称 |
| `--macos-signed-app-name=io.github.jechen.FileTree`（只在 `--app` 时） | 固定包标识，不提供 Developer ID 证书 |
| `--macos-app-version=<仓库版本>`（只在 `--app` 时） | 包版本符合程序，不手动更新版本 |

入口是 `start_file_tree.py`，和 `python -m je_file_tree` 是同一个程序。

## 4. 检查编译结果

1. 从编译出来的文件夹启动程序，扫描一个文件夹。
2. 在“视图 → 语言”切换到另一种语言，然后把某个项目移到回收站并点取消：“是／否”按钮也要是那种语言。如果还是英文，表示编译结果里缺了 Qt 的翻译文件。
3. 打开“帮助 → 使用说明”。

## 5. 常见问题

| 看到什么 | 怎么处理 |
|---|---|
| 编译出来的程序“是／否／关闭”还是英文 | 是直接手动运行 Nuitka、缺了翻译文件。请改用 `python tools/build_nuitka.py` 编译，它会把翻译文件加进去。 |
| Nuitka 因为没有 C 编译器而停止 | 按 §1.2 安装编译器。在 Windows 上没有 Visual Studio 时，Nuitka 会自己下载 MinGW64（脚本已经替你同意）。 |
| 编译时其他程序变得很慢 | Nuitka 会用上所有 CPU 核心。加上 `--jobs=2`（`python tools/build_nuitka.py --jobs=2`）就能给其他程序留出余量。 |
| 第一次编译很久 | 正常：Nuitka 第一次会把 Qt 的 Python 绑定编译好并重复使用，之后就会快很多。 |
| 杀毒软件把新的 `.exe` 隔离了 | 新的、没有签名的可执行文件有时会被误判。把编译文件夹加入例外，或给程序签名。 |
| 找不到 `patchelf`（Linux） | `sudo apt install patchelf` 之后再编译一次。 |
