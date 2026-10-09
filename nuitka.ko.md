# Nuitka로 FileTree 건물 만들기

[English](nuitka.md) | [繁體中文](nuitka.zh-TW.md) | [简体中文](nuitka.zh-CN.md) | [日本語](nuitka.ja.md) | [한국어](nuitka.ko.md)

macOS arm64의 실제 컴파일과 번들 패키징은 Desktop builds [37788683269](https://github.com/JeffreyChen-s-Utils/FileTree/actions/runs/37788683269)에서 통과했습니다. 원본 항목 167개가 모두 보존되었으며 압축 해제 결과도 일치했습니다. 이는 검증한 커밋의 컴파일과 패키징에 대한 증거이며 앱을 실행하거나 게시하지 않았습니다. Finder 작업·동의 검증 및 Developer ID·공증 환경이 없어 POSIX 릴리스 게이트는 비활성 상태를 유지합니다.

Windows 릴리스에서 Azure Artifact Signing과 OIDC 서명을 명시적으로 활성화할 수 있습니다. 활성화된 설정이 누락되거나 서명·타임스탬프·게시자 검증에 실패하면 Windows 산출물과 GitHub 릴리스 게시를 중지합니다. 버전 커밋·태그와 PyPI 업로드가 먼저 완료되며 이후 Windows 작업 실패로 취소되지 않습니다. 단일 파일 및 독립 폴더 실행 파일은 패키징 전에, MSI는 업로드와 매니페스트 해시 계산 전에 검증합니다. 개발 빌드는 서명되지 않습니다. 계정과 실제 운영체제 서명 성공 검증은 아직 사용할 수 없습니다. [Windows 서명 설정](docs/windows-signing.md)을 참조하세요.

[Nuitka](https://nuitka.net/)는 FileTree를 Python 없이 컴퓨터에서 실행되는 기본 프로그램으로 바꿉니다. Python 코드를 C로 변환하고 컴파일하므로 프로그램이 빠르게 시작됩니다. 가격은 더 긴 빌드입니다. 컴파일하는 진입점은 저장소 루트의 `start_file_tree.py`입니다.

> Nuitka는 실행되는 시스템을 위해 빌드합니다. Windows의 경우 Windows, macOS의 경우 macOS, > Linux의 경우 Linux에 빌드합니다. 크로스 컴파일할 수 없습니다.

차트 SVG 내보내기는 PySide6.QtSvg를 가져옵니다. Nuitka는 이 가져오기를 따르며 Qt SVG 라이브러리를 포함합니다. 창과 동일한 PySide6 종속성을 사용합니다.

인쇄 및 보기 PDF 내보내기 가져오기 PySide6.QtPrintSupport는 기존 PySide6 플러그인으로 수집됩니다. 기본 인쇄에는 시스템 프린터 서비스가 필요합니다. PDF 출력은 Qt의 PDF 엔진을 사용합니다.

## 1. 준비하다

Excel 보고서는 stdlib 전용 코어 외부에서 `openpyxl`을 가져옵니다. 컴파일하기 전에 `requirements.txt`을 설치하십시오. Nuitka는 이 가져오기 및 `et-xmlfile` 종속성을 따릅니다. 실행 가능한 릴리스는 게시 작업의 도구 잠금과 관계없이 `.github/requirements/reports.txt`의 확인된 해시에 범용 휠을 설치합니다. HTML은 Qt로 인코딩된 PNG를 포함하며 브라우저나 이미지 종속성이 필요하지 않습니다.

아카이브 미리보기는 stdlib 전용 코어 외부에서 `py7zr` 및 `rarfile`을 느리게 가져옵니다. 컴파일하기 전에 `requirements.txt`을 설치하십시오. Nuitka는 어댑터 가져오기 및 해당 디코더 종속성을 따릅니다. 네이티브 Windows/Linux/macOS Python 3.12 릴리스 휠은 `.github/requirements/archives.txt`의 확인된 해시로 고정되어 있습니다. 외부 RAR 도구는 번들로 제공되지 않습니다. `unrar` 또는 `bsdtar`은 PATH에 있어야 합니다. 미리보기에서는 실행하거나 파일을 추출하지 않습니다.

유사한 사진 검색은 요청된 경우에만 stdlib 전용 코어 외부에서 `Pillow`을 가져옵니다. Nuitka는 이미지 어댑터와 해당 기본 디코더를 따릅니다. 네이티브 Windows/Linux/macOS Python 3.12 빌드는 검증된 바이너리 휠을 `.github/requirements/photos.txt`에 고정합니다. 로컬 컴파일 전에 `requirements.txt`을 설치하세요. 외부 이미지 프로그램이나 모델 자산은 번들로 제공되지 않습니다.

py -3 tools/lock_compiler_wheels.py를 사용하여 컴파일러 런타임 해시를 재생성합니다. 모든 정확한 종속성 버전이 유지되고 게시된 휠 해시는 기본 플랫폼을 포괄하며 소스/끌어온 배포판은 제외됩니다. 격리된 PyPI 게시 잠금은 변경되지 않습니다.

### 1.1 Python 패키지(모든 시스템)

FileTree에 필요한 것만 빌드에 포함되도록 가상 환경을 사용합니다.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install nuitka ordered-set zstandard
```

macOS 및 Linux에서는 대신 `source .venv/bin/activate`을 사용하여 활성화합니다.

### 1.2 C 컴파일러

| 시스템 | 설치할 항목 |
|---|---|
| Windows | "C++를 사용한 데스크톱 개발" 워크로드가 포함된 Visual Studio 빌드 도구입니다. 이것이 없으면 Nuitka는 첫 번째 빌드에서 MinGW64를 다운로드할 것을 제안합니다(`--assume-yes-for-downloads`이 yes로 대답함). |
| Linux | `build-essential` 및 `patchelf` (Debian / Ubuntu: `sudo apt install build-essential patchelf`) |
| macOS | 명령줄 도구: `xcode-select --install` |

## 2. 빌드

가상 환경이 활성화된 리포지토리 루트에서 이를 실행합니다. `tools/build_nuitka.py`은 PySide6이 설치된 위치를 찾고 §3의 옵션을 사용하여 Nuitka를 실행합니다. 또한 전체 명령을 인쇄합니다.

### 2.1 프로그램 폴더(권장)

```bash
python tools/build_nuitka.py
```

결과는 내부에 `FileTree.exe`(Linux 및 macOS `FileTree`)이 포함된 `build/standalone/start_file_tree.dist/` 폴더입니다. **전체 폴더**을 다른 컴퓨터에 복사하고 해당 컴퓨터에서 프로그램을 시작하세요. 이 양식이 가장 빠르게 시작됩니다.

Windows 릴리스의 경우 전체 폴더를 패키지합니다(릴리스 버전 사용).

```bash
python tools/package_standalone.py --version 0.1.0
```

그러면 EXE, 모든 라이브러리, 플러그인 및 번역 카탈로그가 포함된 버전 폴더가 포함된 저장소 루트에 `FileTree-0.1.0-windows-standalone.zip`이 기록됩니다. `build/standalone` 아래에 `FileTree.exe`이 있는 완성된 `.dist` 폴더가 하나만 필요하며 링크/접합을 거부하고 아카이브를 원자적으로 작성합니다. 릴리스 워크플로우는 동일한 태그에서 두 양식을 모두 작성하고 독립형 ZIP과 단일 EXE를 모두 첨부합니다.

.NET 8 SDK를 사용하는 Windows에서 동일한 완전한 독립 실행형 출력에서 x64 MSI을 빌드합니다.

```bash
dotnet tool install wix --global --version 6.0.2
python tools/build_msi.py --version 0.1.0
python tools/prepare_packages.py --version 0.1.0
```

`FileTree-0.1.0-windows-x64.msi`을 씁니다. 컴파일러 버전이 확인됩니다. 페이로드 링크, 지원되지 않는 MSI 버전, 런타임 인벤토리 변경 및 실패한 빌드는 게시를 거부합니다. WiX 검증은 활성화된 상태로 유지됩니다. 컴퓨터별 패키지에는 모든 런타임 파일과 시작 메뉴 바로 가기가 포함되어 있으며 주요 업그레이드를 지원하고 사용자 지정 작업/시작 등록을 사용하지 않습니다. 설치 프로그램에는 관리자 승인이 필요합니다. 빌더는 컴파일만 합니다. 릴리스 워크플로는 동일한 태그에서 이를 연결합니다. 데스크탑 빌드 워크플로는 `tools/install_compiler.py`을 통해 릴리스의 고정 도구를 공유합니다. 독립형 프로그램을 컴파일하고 ZIP/MSI과 기본 설치/업그레이드/제거 증거를 유지합니다. 패키지 버전 업그레이드 유효성 검사는 컴파일된 페이로드를 새로운 러너 스크래치에 복사하고 소유한 마커만 추가합니다. 원본 출력은 보존되며 실행되지 않습니다. 업그레이드된 파일 104개 모두에 대해 기본 설치/업그레이드/제거 검사가 통과되었습니다. 이러한 검사는 GUI 실행이나 OS 동의를 입증하지 않습니다. 초안 명령을 사용하려면 현재 디렉터리에 일치하는 MSI 및 독립 실행형 ZIP이 필요합니다. 실제 해시/ProductCode, Winget 매니페스트, Scoop 매니페스트 및 Chocolatey 패키지 소스가 포함된 새로운 `package-drafts` 폴더를 만듭니다. 읽기 전용 MSI 검사는 아무것도 설치하지 않습니다. 기본 Winget 검증이 통과되었습니다. 제출된 매장이 없습니다. CI는 초안을 유지하고 릴리스에는 ZIP을 첨부합니다. 스토어 계정과 일치하는 게시 릴리스 URL이 여전히 필요합니다.

### 2.2 단일 파일

```bash
python tools/build_nuitka.py --onefile
```

결과는 `build/onefile/FileTree.exe`(다른 곳에서는 `build/onefile/FileTree`)이라는 하나의 파일입니다. 넘겨주기는 더 쉽지만 시작할 때마다 먼저 임시 폴더에 압축을 풀기 때문에 조금 더 느리게 열립니다.

### 2.3 macOS 앱 번들

```bash
python tools/build_nuitka.py --app
python tools/package_posix.py --platform macos --source build/app/start_file_tree.app --version 0.1.0
```

컴파일러 번들은 `build/app/start_file_tree.app`입니다. 패키징은 ZIP에 별도의 `FileTree.app`을 준비하고 추출 전후에 전체 내용을 확인합니다. package 명령은 전체 ZIP과 증명을 새로운 `desktop-package` 폴더에 기록합니다. 기본 Ditto 추출은 모든 일반 파일과 내부 프레임워크 링크를 보존해야 합니다. 번들 ID/버전/실행 파일이 확인됩니다. 외부 링크는 거부됩니다.

프로그램은 Windows, Linux 및 macOS에서 FileTree의 자체 아이콘을 가져옵니다(스크립트는 이를 `build/`에 그립니다). 다른 옵션은 변경되지 않고 Nuitka에 전달됩니다(예: `python tools/build_nuitka.py --windows-icon-from-ico=icon.ico` (Windows), `--linux-icon=icon.png` 또는 `--macos-app-icon=icon.icns`). 이 스크립트는 Nuitka의 선택적 PNG 변환 종속성을 방지하면서 Qt의 PNG 인코더를 사용하여 macOS에 대한 기본 다중 크기 ICNS를 생성합니다.

### 2.4 A Linux 앱 이미지

```bash
python tools/build_nuitka.py --jobs=2
python tools/package_posix.py --platform linux --source build/standalone/start_file_tree.dist --version 0.1.0
```

이름이 다른 경우 빌드에서 실제 단독 `.dist` 폴더를 사용하세요. 기본 x86_64 Linux 패키징은 리터럴 AppRun 시작 관리자 및 생성된 아이콘을 사용하여 AppDir에서 전체 Qt 런타임 및 번역을 보존합니다. 패키징 도구 1.9.1 및 런타임 20251108은 SHA-256 고정되어 있습니다. 최신 버전을 다운로드하는 대신 런타임이 명시적으로 제공됩니다. 패키징 중에는 FUSE 마운트가 필요하지 않습니다. 기본 이미지 추출은 전체 런타임을 재현해야 하며 소스 해시/ID는 변경되지 않은 상태로 유지되어야 합니다. AppImage와 증명은 새로운 `desktop-package`로 함께 게시됩니다. 기존 도착은 거부됩니다.

데스크톱 빌드 CI는 Ubuntu 22.04 x86_64 및 macOS 15 arm64를 사용하며 릴리스 토큰이나 애플리케이션 시작 없이 7일 동안 이러한 개발 아티팩트를 유지합니다. 릴리스 재사용은 진행 항목 #4가 확인된 후에만 설정되는 리포지토리 변수 `FILETREE_POSIX_RELEASE_VERIFIED=true`에 의해 제어됩니다. 이 변경 사항은 해당 변수를 설정하거나 개발자 ID 서명/공증을 제공하거나 Finder/OS 동의를 증명하지 않습니다. AppImage 로그인 등록은 마운트 외부의 원래 실행 파일을 사용합니다.

## 3. 스크립트가 실행되는 내용

| 옵션 | 왜 |
|---|---|
| `--mode=standalone` / `--mode=onefile` / `--mode=app` | 폴더, 파일 하나 또는 (macOS에서) 앱 번들 |
| `--enable-plugin=pyside6` | 창에 필요한 Qt 라이브러리 및 플러그인을 복사합니다. |
| `--include-data-files=<Qt translations>/qtbase_zh_TW.qm=<same place in the build>`(및 `qtbase_zh_CN.qm`, `qtbase_ja.qm`, `qtbase_ko.qm`) | Nuitka는 Qt 번역을 자동으로 복사하지 않습니다. 번역이 없으면 예·아니요·닫기 버튼이 영어로 표시됩니다. 설치 환경에 따라 위치가 다르므로(Windows: `PySide6/translations`, Linux: `PySide6/Qt/translations`) 스크립트로 빌드합니다 |
| `--windows-console-mode=disable` | Windows의 FileTree 옆에 검은색 콘솔 창이 없습니다(다른 곳에서는 무시됨) |
| `--output-dir=build/standalone`(또는 `build/onefile`, `build/app`) | 모든 빌드 결과는 Git에서 제외하는 `build/`에 저장됩니다. 각 형식에 별도 폴더를 사용하므로 다른 형식의 빌드 결과를 삭제하지 않습니다 |
| `--output-filename=FileTree` | 프로그램은 start_file_tree 대신 FileTree이라고 합니다. |
| `--assume-yes-for-downloads` | Nuitka가 요청하지 않고 필요한 도우미 도구를 가져올 수 있습니다. |
| `--windows-icon-from-ico=build/FileTree.ico` / `--linux-icon=build/FileTree.png` / `--macos-app-icon=build/FileTree.icns` | FileTree의 아이콘, 스크립트로 그린 것(아이콘을 직접 전달할 때 생략됨) |
| `--macos-app-name=FileTree`(`--app`만 해당) | Finder 및 도크에 표시된 이름 |
| `--macos-signed-app-name=io.github.jechen.FileTree`(`--app`만 사용) | 고정된 번들 식별자입니다. Developer ID 인증서는 포함되지 않습니다 |
| `--macos-app-version=<checked-in version>`(`--app`만 사용) | 번들 버전은 수동 범프 없이 프로그램과 일치합니다. |

진입점은 `start_file_tree.py`이며, `python -m je_file_tree`과 동일한 프로그램입니다.

## 4. 빌드 확인

1. 빌드 폴더에서 프로그램을 시작하고 폴더를 스캔합니다.
2. **보기 → 언어**에서 다른 언어로 전환한 다음 항목을 휴지통으로 이동하고 취소합니다. 예/아니요 버튼도 해당 언어로 되어 있어야 합니다. 영어로 유지되면 Qt의 번역 파일이 빌드에서 누락됩니다.
3. **도움말 → 사용 방법**을 엽니다.

## 5. 문제

| 표시되는 내용 | 수행할 작업 |
|---|---|
| 예 / 아니요 / 내장된 프로그램에서 영어로 유지 | Nuitka는 번역 파일 없이 직접 실행되었습니다. 이를 추가하는 `python tools/build_nuitka.py`로 빌드하세요. |
| C 컴파일러가 없기 때문에 Nuitka가 중지됩니다. | §1.2에서 컴파일러를 설치합니다. Windows에서 Visual Studio 없이 Nuitka는 MinGW64를 자체적으로 다운로드합니다(스크립트가 yes로 응답함). |
| 빌드 중 다른 프로그램이 느려짐 | Nuitka는 모든 CPU 코어를 사용합니다. `--jobs=2`(`python tools/build_nuitka.py --jobs=2`)로 병렬 작업 수를 제한하여 다른 프로그램에 여유를 남깁니다 |
| 첫 번째 빌드에는 오랜 시간이 걸립니다. | 일반: Nuitka는 Qt의 Python 바인딩을 한 번 컴파일하고 결과를 재사용하므로 이후 빌드가 더 빠릅니다. |
| 바이러스 백신이 새 `.exe`를 격리함 | 새로 만든 서명되지 않은 실행 파일이 탐지될 수 있습니다. 빌드 폴더를 허용하거나 프로그램에 서명합니다 |
| `patchelf` 찾을 수 없음(Linux) | `sudo apt install patchelf`, 그런 다음 다시 빌드하세요. |
