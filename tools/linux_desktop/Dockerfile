FROM python:3.12-slim-bookworm@sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d

ARG DESKTOP_UID=1001
ARG DESKTOP_GID=1001
RUN if ! getent group "$DESKTOP_GID"; then groupadd --gid "$DESKTOP_GID" filetree; fi \
    && if ! getent passwd "$DESKTOP_UID"; then useradd --no-create-home --uid "$DESKTOP_UID" --gid "$DESKTOP_GID" filetree; fi
RUN apt-get update && apt-get install -y --no-install-recommends \
    dbus dbus-x11 xvfb xdg-utils fonts-noto-cjk libegl1 libgl1 libfontconfig1 \
    libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-image0 \
    libxcb-render-util0 libxcb-xinerama0 libxcb-shape0 libxcb-sync1 libxcb-randr0 \
    libxcb-xfixes0 libsm6 libice6 libglib2.0-0 libdbus-1-3 thunar xdotool openbox trayer
WORKDIR /workspace
COPY requirements.txt /tmp/filetree-requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/filetree-requirements.txt
RUN python -c 'from PySide6.QtCore import QLibraryInfo; import subprocess; from pathlib import Path; p = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)) / "platforms/libqxcb.so"; r = subprocess.run(["/usr/bin/ldd", str(p)], capture_output=True, text=True, check=True); print(r.stdout); assert "not found" not in r.stdout'
ENTRYPOINT ["python", "/workspace/tools/linux_desktop/run.py"]
