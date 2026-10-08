"""Validate explicit release-signing configuration without contacting Azure or printing identifiers."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

_IDENTIFIERS = ("FILETREE_AZURE_CLIENT_ID", "FILETREE_AZURE_TENANT_ID", "FILETREE_AZURE_SUBSCRIPTION_ID")
_NAMES = ("FILETREE_SIGNING_ACCOUNT", "FILETREE_SIGNING_PROFILE")
_GUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
_MAX_PUBLISHER = 1024


def signing_enabled(environment: Mapping[str, str]) -> bool:
    """Require a complete opt-in Azure Artifact Signing configuration; an unset mode stays unsigned.

    This validates configuration only. No token, private key, service request or repository setting
    is created. Missing/malformed enabled configuration fails instead of publishing unsigned files.
    """
    mode = environment.get("FILETREE_WINDOWS_SIGNING", "")
    if not mode:
        return False
    if mode != "azure-artifact":
        raise ValueError("FILETREE_WINDOWS_SIGNING must be unset or azure-artifact")
    for key in _IDENTIFIERS:
        if not _GUID.fullmatch(environment.get(key, "")):
            raise ValueError(f"Missing or malformed {key}")
    for key in _NAMES:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,99}", environment.get(key, "")):
            raise ValueError(f"Missing or malformed {key}")
    endpoint = urlsplit(environment.get("FILETREE_SIGNING_ENDPOINT", ""))
    if (endpoint.scheme != "https" or not re.fullmatch(r"[a-z0-9]+\.codesigning\.azure\.net",
                                                      endpoint.netloc)
            or endpoint.path not in ("", "/") or endpoint.query or endpoint.fragment):
        raise ValueError("FILETREE_SIGNING_ENDPOINT must be an HTTPS regional Azure signing endpoint")
    publisher = environment.get("FILETREE_SIGNING_PUBLISHER", "")
    if not publisher or len(publisher) > _MAX_PUBLISHER or any(char in publisher for char in "\r\n\x00"):
        raise ValueError("Missing or malformed FILETREE_SIGNING_PUBLISHER")
    return True


def main() -> None:
    """Write only the enabled boolean to the workflow output; never echo signing configuration."""
    enabled = signing_enabled(os.environ)
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
        stream.write(f"enabled={str(enabled).lower()}\n")


if __name__ == "__main__":
    main()
