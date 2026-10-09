"""Install the shared pinned desktop compiler/runtime tools without release credentials."""

from __future__ import annotations

from pathlib import Path
import subprocess  # nosec B404 - fixed pip arguments through this interpreter
import sys

_ROOT = Path(__file__).resolve().parents[1]
_INSTALLS = (
    ("--upgrade", "--only-binary", ":all:", "pip==26.1.2", "wheel==0.47.0"),
    ("--only-binary", ":all:", "PySide6==6.11.2"),
    *(("--require-hashes", "--only-binary", ":all:", "-r", f".github/requirements/{name}.txt")
      for name in ("reports", "archives", "photos")),
    ("--only-binary", ":all:", "--no-binary", "nuitka",
     "nuitka==4.2.2", "ordered-set==4.1.0", "zstandard==0.25.0"),
)


def install() -> None:
    """Install fixed native versions and cross-platform wheel hash locks; only Nuitka may use an sdist."""
    for arguments in _INSTALLS:
        subprocess.run([sys.executable, "-m", "pip", "install", *arguments], cwd=_ROOT,  # noqa: S603 # nosec B603
                       check=True, timeout=900)


if __name__ == "__main__":
    install()
