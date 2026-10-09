# Nuitka で FileTree を構築

[English](nuitka.md) | [繁體中文](nuitka.zh-TW.md) | [简体中文](nuitka.zh-CN.md) | [日本語](nuitka.ja.md) | [한국어](nuitka.ko.md)

Windows ビルドには `--product-name=FileTree` と `--file-description=FileTree` を明示的に埋め込み、`--product-version` と `--file-version` はパッケージのバージョンから取得します。昇格時はその実行ファイルを再起動します。Python ソースでは Python/pythonw を昇格するため、UAC はそのインタープリターを識別します。ウィンドウ名では変更できません。このリソース設定は発行元の検証や署名済みビルドを証明しません。

macOS arm64 のネイティブコンパイルとバンドル作成は Desktop builds [37788683269](https://github.com/JeffreyChen-s-Utils/FileTree/actions/runs/37788683269) に合格しました。167 個の元の項目をすべて保持し、解凍結果も一致しました。この証拠は検証したコミットのコンパイルとパッケージ作成に限られ、アプリは起動・公開していません。Finder の操作・同意検証と Developer ID・公証の環境は未提供のため、POSIX リリースのゲートは無効のままです。

Windows リリースでは Azure Artifact Signing と OIDC による署名を明示的に有効化できます。有効時に設定が不足した場合や、署名・タイムスタンプ・発行者の検証に失敗した場合は Windows 成果物と GitHub リリースの公開を停止します。最初にバージョンのコミットとタグを作成し、その後 PyPI へのアップロードと Windows のコンパイルを独立して実行します。後続の Windows の失敗でバージョンや成功済みの PyPI アップロードは取り消されません。独立フォルダー版の実行ファイルはパッケージ作成前、MSI はアップロードとマニフェストのハッシュ計算前に検証します。開発ビルドは未署名です。アカウントとネイティブ署名の成功検証はまだ利用できません。[Windows 署名の設定](docs/windows-signing.md)を参照してください。

リリース PR が `main` にマージされるたびに、GitHub Actions は Windows 上で新しいバージョンタグから完全なプログラムフォルダーを一度だけコンパイルします。リリースには `FileTree-<version>-windows-standalone.zip` と同じフォルダーから作成した MSI が含まれます。ZIP 全体を展開して中の `FileTree.exe` を実行し、ライブラリ、プラグイン、翻訳ファイルをすべて保持してください。必要なファイルをすべてアップロードし、名前・サイズ・アップロード状態を確認するまで GitHub リリースはドラフトのままです。PyPI へのアップロードは独立して実行され、トークンの不足やアップロード失敗は報告されますが、Windows リリースの公開を妨げません。失敗した `publish-release` ジョブを再実行するとドラフトへのアップロードを再開できます。公開済みリリースは上書きしません。

[Nuitka](https://nuitka.net/) は、FileTree を、Python を使用しないコンピューター上で実行されるネイティブ プログラムに変換します。 Python コードを C に変換してコンパイルするため、プログラムはすぐに開始されます。その分、ビルドには時間がかかります。コンパイルされるエントリ ポイントは、リポジトリ ルートの `start_file_tree.py` です。

> Nuitka は、実行されるシステムに合わせてビルドします。Windows の場合は Windows、macOS の場合は macOS、Linux の場合は Linux にビルドします。クロスコンパイルはできません。

チャート SVG エクスポーターは PySide6.QtSvg をインポートします。 Nuitka はこのインポートに従っており、Qt SVG ライブラリが含まれています。ウィンドウと同じ PySide6 依存関係を使用します。

既存の PySide6 プラグインによって収集された PDF エクスポート インポート PySide6.QtPrintSupport の印刷と表示。ネイティブ印刷にはシステム プリンター サービスが必要です。 PDF 出力には、Qt の PDF エンジンが使用されます。

## 1.準備する

Excel レポートは、stdlib のみのコアの外で `openpyxl` をインポートします。コンパイル前に `requirements.txt` をインストールします。 Nuitka は、このインポートとその `et-xmlfile` 依存関係に従います。実行可能リリースは、公開ジョブのツール ロックとは関係なく、`.github/requirements/reports.txt` の検証済みハッシュにユニバーサル ホイールをインストールします。 HTML には Qt でエンコードされた PNG が埋め込まれており、ブラウザーや画像への依存は必要ありません。

アーカイブ プレビューは、stdlib 専用コアの外側に `py7zr` と `rarfile` を遅延インポートします。コンパイル前に `requirements.txt` をインストールします。 Nuitka はアダプターのインポートとそのデコーダーの依存関係に従います。ネイティブ Windows/Linux/macOS Python 3.12 リリース ホイールは、`.github/requirements/archives.txt` の検証済みハッシュで固定されています。外部 RAR ツールはバンドルされていません。`unrar` または `bsdtar` は PATH 上にある必要があります。プレビューでは決して実行したり、ファイルを抽出したりすることはありません。

類似写真検索は、stdlib 専用コアの外で、要求された場合にのみ `Pillow` をインポートします。 Nuitka はイメージ アダプターとそのネイティブ デコーダーに従います。ネイティブ Windows/Linux/macOS Python 3.12 ビルドは、検証済みのバイナリ ホイールを `.github/requirements/photos.txt` に固定します。ローカルでコンパイルする前に `requirements.txt` をインストールしてください。外部の画像プログラムやモデル アセットはバンドルされていません。

py -3 tools/lock_compiler_wheels.py を使用してコンパイラ ランタイム ハッシュを再生成します。すべての正確な依存関係バージョンが保持され、公開されたホイール ハッシュはネイティブ プラットフォームをカバーし、ソース/ヤンクされたディストリビューションは除外されます。これにより、分離された PyPI パブリッシング ロックは変更されません。

### 1.1 Python パッケージ (すべてのシステム)

仮想環境を使用して、FileTree に必要なものだけがビルドに含まれるようにします。

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install nuitka ordered-set zstandard
```

macOS および Linux では、代わりに `source .venv/bin/activate` を使用してアクティブ化します。

### 1.2 C コンパイラ

| システム | インストールするもの |
|---|---|
| Windows | 「C++ によるデスクトップ開発」ワークロードを備えた Visual Studio ビルド ツール。それがなければ、Nuitka は最初のビルドで MinGW64 をダウンロードすることを提案します (`--assume-yes-for-downloads` は「はい」と答えます)。 |
| Linux | `build-essential` および `patchelf` (Debian / Ubuntu: `sudo apt install build-essential patchelf`) |
| macOS | コマンド ライン ツール: `xcode-select --install` |

## 2.ビルドする

仮想環境をアクティブにして、リポジトリ ルートからこれらを実行します。 `tools/build_nuitka.py` は、PySide6 がインストールされている場所を見つけ、§3 のオプションを使用して Nuitka を実行します。また、完全なコマンドも出力されます。

### 2.1 プログラム フォルダー (推奨)

```bash
python tools/build_nuitka.py
```

結果は、`FileTree.exe` (Linux および macOS `FileTree` 上) を含むフォルダー `build/standalone/start_file_tree.dist/` になります。 **フォルダー全体**を別のコンピューターにコピーし、そこからプログラムを起動します。このフォームは最も速く開始されます。

Windows リリースの場合は、完全なフォルダーをパッケージ化します (リリースのバージョンを使用します)。

```bash
python tools/package_standalone.py --version 0.1.0
```

これにより、リポジトリのルートに `FileTree-0.1.0-windows-standalone.zip` が作成されます。バージョン付きフォルダーには EXE、すべてのライブラリ、プラグイン、翻訳ファイルが含まれます。`build/standalone` の下に `FileTree.exe` を含む完全な `.dist` フォルダーが一つだけ必要です。ツールはリンクやジャンクションを拒否し、アーカイブをアトミックに書き込みます。リリースワークフローはこのフォルダーを一度だけコンパイルし、同じ出力から ZIP と MSI を作成します。

.NET 8 SDK を使用した Windows 上で、同じ完全なスタンドアロン出力から x64 MSI をビルドします。

```bash
dotnet tool install wix --global --version 6.0.2
python tools/build_msi.py --version 0.1.0
python tools/prepare_packages.py --version 0.1.0
```

これにより、`FileTree-0.1.0-windows-x64.msi` と書き込まれます。コンパイラのバージョンがチェックされます。ペイロード リンク、サポートされていない MSI バージョン、変更されたランタイム インベントリ、失敗したビルドは公開を拒否します。 WiX 検証は有効のままです。マシンごとのパッケージには、すべてのランタイム ファイルと [スタート] メニューのショートカットが含まれており、メジャー アップグレードをサポートし、カスタム アクション/スタートアップ登録は使用しません。そのインストーラーには管理者の承認が必要です。ビルダーはコンパイルのみを行います。リリース ワークフローでは、同じタグから添付されます。デスクトップ ビルド ワークフローは、`tools/install_compiler.py` を通じてリリースの固定ツールを共有します。スタンドアロン プログラムをコンパイルし、その ZIP/MSI とネイティブのインストール/アップグレード/削除の証拠を保持します。パッケージ バージョンのアップグレード検証では、コンパイルされたペイロードが新しいランナー スクラッチにコピーされ、所有マーカーのみが追加されます。元の出力は保存され、決して起動されません。 104 個のアップグレードされたファイルすべてについて、ネイティブのインストール/アップグレード/削除チェックに合格しました。これらのチェックは、GUI の起動や OS の同意を証明するものではありません。ドラフト コマンドでは、現在のディレクトリに一致する MSI とスタンドアロン ZIP が必要です。実際のハッシュ/ProductCode、winget マニフェスト、Scoop マニフェスト、および Chocolatey パッケージ ソースを含む新しい `package-drafts` フォルダーが作成されます。読み取り専用の MSI インスペクションでは、何もインストールされません。ネイティブ winget 検証に合格しました。ストアは登録されていません。 CI はドラフトを保持し、リリースには ZIP が添付されます。ストア アカウントと一致する公開リリース URL は引き続き必要です。

### 2.2 単一のファイル

```bash
python tools/build_nuitka.py --onefile
```

結果は 1 つのファイル、`build/onefile/FileTree.exe` (他の場所では `build/onefile/FileTree`) になります。持ち運びは簡単ですが、起動するたびに最初に一時フォルダーに解凍されるため、開くのが少し遅くなります。 これは任意のローカルビルドです。Windows の自動リリースでは、セクション 2.1 のプログラムフォルダーを使用します。

### 2.3 macOS アプリ バンドル

```bash
python tools/build_nuitka.py --app
python tools/package_posix.py --platform macos --source build/app/start_file_tree.app --version 0.1.0
```

コンパイラ バンドルは `build/app/start_file_tree.app` です。パッケージ化では、ZIP 内に個別の `FileTree.app` が格納され、抽出の前後にその完全な内容が検証されます。 package コマンドは、完全な ZIP とプルーフを新しい `desktop-package` フォルダーに書き込みます。同様にネイティブ抽出では、すべての通常のファイルと内部フレームワーク リンクを保存する必要があります。バンドルの ID、バージョン、実行可能ファイルがチェックされます。外部リンクは拒否されます。

プログラムは、Windows、Linux、macOS 上で FileTree の独自のアイコンを取得します (スクリプトはそれを `build/` に描画します)。他のオプションは変更されずに Nuitka に渡されます。たとえば、別のアイコン: `python tools/build_nuitka.py --windows-icon-from-ico=icon.ico` (Windows)、`--linux-icon=icon.png`、または `--macos-app-icon=icon.icns` です。このスクリプトは、Qt の PNG エンコーダーを使用して、macOS 用のネイティブ マルチサイズ ICNS を生成し、Nuitka のオプションの PNG 変換依存関係を回避します。

### 2.4A Linux アプリイメージ

```bash
python tools/build_nuitka.py --jobs=2
python tools/package_posix.py --platform linux --source build/standalone/start_file_tree.dist --version 0.1.0
```

名前が異なる場合は、ビルドの実際の唯一の `.dist` フォルダーを使用してください。ネイティブ x86_64 Linux パッケージ化では、Qt ランタイム全体と翻訳がリテラルの AppRun ランチャーと生成されたアイコンとともに AppDir に保存されます。パッケージ化ツール 1.9.1 とランタイム 20251108 は SHA-256 固定されています。ランタイムは、最新のものをダウンロードするのではなく、明示的に提供されます。パッケージ化中に FUSE マウントは必要ありません。ネイティブ イメージの抽出では、完全なランタイムを再現する必要があり、ソースのハッシュ/アイデンティティは変更されないままでなければなりません。 AppImage とプルーフは一緒に新しい `desktop-package` として公開されます。既存の到着は拒否されます。

デスクトップ ビルド CI は、Ubuntu 22.04 x86_64 および macOS 15 arm64 を使用し、リリース トークンやアプリケーションの起動を行わずに、これらの開発成果物を 7 日間保持します。リリースの再利用はリポジトリ変数 `FILETREE_POSIX_RELEASE_VERIFIED=true` によって制御され、進行状況項目 #4 が確認された後にのみ設定されます。この変更では、その変数の設定、開発者 ID の署名/公証の提供、または Finder/OS の同意の証明は行われません。 AppImage のログイン登録は、マウント外の元の実行可能ファイルを使用します。

## 3.スクリプトが実行する内容

| オプション | 理由 |
|---|---|
| `--mode=standalone` / `--mode=onefile` / `--mode=app` | フォルダー、1 つのファイル、または (macOS 上の) アプリ バンドル |
| `--enable-plugin=pyside6` | ウィンドウに必要な Qt ライブラリとプラグインをコピーします |
| `--include-data-files=<Qt translations>/qtbase_zh_TW.qm=<same place in the build>`（および `qtbase_zh_CN.qm`, `qtbase_ja.qm`, `qtbase_ko.qm`） | Nuitka は Qt の翻訳を自動ではコピーしません。ない場合、はい・いいえ・閉じるボタンが英語になります。配置場所はインストール環境により異なるため（Windows: `PySide6/translations`、Linux: `PySide6/Qt/translations`）、スクリプトでビルドします |
| `--windows-console-mode=disable` | Windows の FileTree の隣に黒いコンソール ウィンドウがありません (他の場所では無視されます) |
| `--output-dir=build/standalone` (または `build/onefile`、`build/app`) | Nuitka が作成したものはすべて `build/` に入りますが、Git はこれを無視します。各フォームには独自のフォルダーがあるため、フォームを構築しても別のフォルダーは削除されません |
| `--output-filename=FileTree` | 実行ファイル名を start_file_tree から FileTree に変更します |
| `--assume-yes-for-downloads` | Nuitka が要求せずに必要なヘルパー ツールを取得できるようにします |
| `--windows-icon-from-ico=build/FileTree.ico` / `--linux-icon=build/FileTree.png` / `--macos-app-icon=build/FileTree.icns` | FileTree のアイコン、スクリプトによって描画されます (自分でアイコンを渡す場合は省略されます) |
| `--macos-app-name=FileTree`（`--app` のみ） | Finder と Dock に表示する名前 |
| `--macos-signed-app-name=io.github.jechen.FileTree`（`--app` のみ） | 安定したバンドル識別子。Developer ID 証明書は含まれません |
| `--macos-app-version=<checked-in version>` (`--app` のみ) | バンドルのバージョンは手動による変更なしでプログラムと一致します |

エントリ ポイントは `start_file_tree.py` で、`python -m je_file_tree` と同じプログラムです。

## 4.ビルドを確認する

1. ビルド フォルダーからプログラムを起動し、フォルダーをスキャンします。
2. **View → Language** で別の言語に切り替え、何かをごみ箱に移動してキャンセルします。Yes / No ボタンもその言語である必要があります。英語のままの場合、Qt の翻訳ファイルがビルドに含まれません。
3. **ヘルプ→**の使用方法を開きます。

## 5.問題点

| 表示される内容 | 対処方法 |
|---|---|
| はい / いいえ / 閉じる ビルドされたプログラムでは英語のままです | Nuitka は翻訳ファイルを使用せずに手動で実行されました。 `python tools/build_nuitka.py` を使用してビルドし、それらを追加します。 |
| C コンパイラがないため Nuitka が停止します | §1.2 のコンパイラをインストールします。 Windows では、Visual Studio を使用しないと、Nuitka が MinGW64 を単独でダウンロードします (スクリプトは「はい」と答えます)。 |
| ビルド中にほかのプログラムが遅くなる | Nuitka は全 CPU コアを使用します。`--jobs=2`（`python tools/build_nuitka.py --jobs=2`）で並列数を制限し、ほかの処理に余裕を残します |
| 最初のビルドには長い時間がかかります | 通常: Nuitka は Qt の Python バインディングを 1 回コンパイルし、その結果を再利用するため、後のビルドは高速になります。 |
| ウイルス対策ソフトが新しい `.exe` を隔離する | 新しい未署名の実行ファイルは検出対象になることがあります。ビルドフォルダーを許可するか、プログラムに署名します |
| `patchelf` が見つからない（Linux） | `sudo apt install patchelf` を実行してから再ビルドします |
