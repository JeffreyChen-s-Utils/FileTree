"""Bounded release notices from the fixed PyPI endpoint; never download or install a package."""

from __future__ import annotations

import http.client
import json
import math
import re
import threading
import time
from http import HTTPStatus

CHECK_INTERVAL = 24 * 60 * 60
MAX_RESPONSE = 2 * 1024 * 1024
PROJECT_URL = "https://pypi.org/project/je-file-tree/"
_VERSION = re.compile(r"[0-9]{1,10}\.[0-9]{1,10}\.[0-9]{1,10}\Z")
_TIMEOUT = 8
_DEADLINE = 20
_CHUNK = 64 * 1024


def check_due(last_attempt: object, now: float) -> bool:
    """Allow one attempt per elapsed day, including failures; a backward clock never accelerates checks."""
    if not math.isfinite(now) or now < 0:
        return False
    try:
        previous = float(last_attempt) if not isinstance(last_attempt, bool) else math.nan
    except (ValueError, TypeError, OverflowError):
        previous = math.nan
    return not math.isfinite(previous) or previous < 0 or now - previous >= CHECK_INTERVAL


def newer_release(payload: bytes, current: str) -> str | None:
    """Validate project metadata and compare FileTree's stable x.y.z releases; ignore other release forms."""
    if len(payload) > MAX_RESPONSE or not _VERSION.fullmatch(current):
        raise ValueError("Invalid release metadata size or installed version")
    document = json.loads(payload.decode("utf-8"))
    info = document.get("info") if isinstance(document, dict) else None
    if not isinstance(info, dict) or not isinstance(info.get("name"), str):
        raise ValueError("Missing PyPI project metadata")
    if re.sub(r"[-_.]+", "-", info["name"]).lower() != "je-file-tree":
        raise ValueError("Unexpected PyPI project")
    version = info.get("version")
    if not isinstance(version, str) or not isinstance(info.get("yanked"), bool):
        raise ValueError("Invalid PyPI release metadata")
    if info["yanked"] or not _VERSION.fullmatch(version):
        return None
    installed = tuple(map(int, current.split(".")))
    return version if tuple(map(int, version.split("."))) > installed else None


def _read(response: http.client.HTTPResponse, cancel: threading.Event) -> bytes:
    if (response.status != HTTPStatus.OK or
            response.getheader("Content-Type", "").split(";")[0].strip() != "application/json"):
        raise ValueError("Unexpected PyPI response")
    length = response.getheader("Content-Length")
    if length is not None and (not length.isascii() or not length.isdecimal() or int(length) > MAX_RESPONSE):
        raise ValueError("PyPI response exceeds the metadata bound")
    if response.getheader("Content-Encoding", "identity") != "identity":
        raise ValueError("Unexpected PyPI content encoding")
    body = bytearray()
    deadline = time.monotonic() + _DEADLINE
    while not cancel.is_set():
        if time.monotonic() >= deadline:
            raise TimeoutError("PyPI metadata read timed out")
        chunk = response.read(min(_CHUNK, MAX_RESPONSE + 1 - len(body)))
        body.extend(chunk)
        if len(body) > MAX_RESPONSE:
            raise ValueError("PyPI response exceeds the metadata bound")
        if not chunk:
            if length is not None and len(body) != int(length):
                raise ValueError("Incomplete PyPI metadata response")
            return bytes(body)
    raise InterruptedError("Update check canceled")


def fetch_release(current: str, cancel: threading.Event) -> str | None:
    """Make one verified-TLS request to PyPI, with bounded reads; no redirects, paths or installation."""
    if not _VERSION.fullmatch(current):
        raise ValueError("Invalid installed version")
    if cancel.is_set():
        raise InterruptedError("Update check canceled")
    connection = http.client.HTTPSConnection("pypi.org", timeout=_TIMEOUT)
    try:
        connection.request("GET", "/pypi/je_file_tree/json", headers={"Accept": "application/json",
                            "User-Agent": f"FileTree/{current}"})
        with connection.getresponse() as response:
            return newer_release(_read(response, cancel), current)
    finally:
        connection.close()
