FROM python:3.12-slim-bookworm@sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d

RUN apt-get update && apt-get install -y --no-install-recommends \
    dbus dbus-x11 xvfb xdg-utils fonts-noto-cjk libegl1 libgl1 libfontconfig1 \
    libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-image0 \
    libxcb-render-util0 libxcb-xinerama0 libglib2.0-0 libdbus-1-3 thunar xdotool openbox
WORKDIR /workspace
COPY requirements.txt /tmp/filetree-requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/filetree-requirements.txt
ENTRYPOINT ["python", "/workspace/tools/linux_desktop/run.py"]
