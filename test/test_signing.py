"""Enabled release signing fails closed; credential-free checks never sign or launch an executable."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess

import pytest

from tools.check_signing import signing_enabled

_ROOT = Path(__file__).resolve().parents[1]


def _configuration() -> dict[str, str]:
    return {
        "FILETREE_WINDOWS_SIGNING": "azure-artifact",
        "FILETREE_AZURE_CLIENT_ID": "11111111-1111-4111-8111-111111111111",
        "FILETREE_AZURE_TENANT_ID": "22222222-2222-4222-8222-222222222222",
        "FILETREE_AZURE_SUBSCRIPTION_ID": "33333333-3333-4333-8333-333333333333",
        "FILETREE_SIGNING_ENDPOINT": "https://wus.codesigning.azure.net/",
        "FILETREE_SIGNING_ACCOUNT": "owned-account",
        "FILETREE_SIGNING_PROFILE": "public-profile",
        "FILETREE_SIGNING_PUBLISHER": "CN=Owned Test Publisher, O=Owned Test Publisher, C=US",
    }


def test_signing_requires_explicit_enablement():
    assert not signing_enabled({})
    configuration = _configuration()
    del configuration["FILETREE_WINDOWS_SIGNING"]
    assert not signing_enabled(configuration)
    assert signing_enabled(_configuration())


@pytest.mark.parametrize("key", list(_configuration()))
def test_missing_enabled_configuration_never_falls_back_to_unsigned(key):
    configuration = _configuration()
    configuration[key] = "unsupported" if key == "FILETREE_WINDOWS_SIGNING" else ""
    with pytest.raises(ValueError):
        signing_enabled(configuration)


@pytest.mark.parametrize("endpoint", ["http://wus.codesigning.azure.net", "https://attacker.example",
                                      "https://wus.codesigning.azure.net@attacker.example",
                                      "https://wus.codesigning.azure.net:443", "https://wus.codesigning.azure.net/a",
                                      "https://wus.codesigning.azure.net?x=1"])
def test_enabled_signing_rejects_nonregional_or_rewritten_service_endpoints(endpoint):
    configuration = _configuration()
    configuration["FILETREE_SIGNING_ENDPOINT"] = endpoint
    with pytest.raises(ValueError, match="HTTPS regional"):
        signing_enabled(configuration)


def test_signing_finishes_before_artifact_packaging_upload_and_store_hashes():
    release = (_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    body = release.split("\n  build-exe:", 1)[1].split("\n  build-posix:", 1)[0]
    assert body.index("check_signing.py") < body.index("install_compiler.py")
    assert body.index("Sign and verify the standalone") < body.index("package_standalone.py")
    assert body.index("build_msi.py") < body.index("Sign and verify the MSI") < body.index("filetree-msi")
    assert body.index("Sign and verify the MSI") < body.index("prepare_packages.py")
    assert body.count("if: steps.signing.outputs.enabled == 'true'") == 2
    assert "id-token: write" in body and "environment: windows-signing" in body
    assert "files-folder" not in body


def test_signing_composite_pins_actions_uses_only_oidc_and_verifies_after_signing():
    action = (_ROOT / ".github/actions/sign-windows/action.yml").read_text(encoding="utf-8")
    assert (action.index("-CheckPathsOnly") < action.index("azure/login@")
            < action.index("azure/artifact-signing-action@"))
    assert action.index("azure/artifact-signing-action@") < action.index("Refuse invalid")
    assert "exclude-environment-credential: true" in action
    assert "exclude-azure-cli-credential: false" in action
    assert "cache-dependencies: false" in action and "trace: false" in action
    assert "client-secret" not in action and "files-folder" not in action


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="Native PowerShell 7 unavailable")
def test_actual_verifier_refuses_unsigned_owned_bytes_and_outside_paths_without_changing_sources(tmp_path):
    script = tmp_path / "tools/verify_signatures.ps1"
    script.parent.mkdir()
    shutil.copyfile(_ROOT / "tools/verify_signatures.ps1", script)
    owned = tmp_path / "build/onefile/FileTree.exe"
    owned.parent.mkdir(parents=True)
    owned.write_bytes(b"owned unsigned fixture; never executable")
    before = hashlib.sha256(owned.read_bytes()).digest()
    command = [shutil.which("pwsh"), "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script),
               "-Files", str(owned), "-ExpectedPublisher", "CN=Owned Test Publisher"]
    paths = subprocess.run([*command, "-CheckPathsOnly"],  # noqa: S603 - fixed pwsh and owned script, no shell
                           capture_output=True, check=False, timeout=30)
    assert paths.returncode == 0
    signature = subprocess.run(command, capture_output=True, check=False, timeout=30)  # noqa: S603
    assert signature.returncode != 0
    assert b"verification failed" in signature.stderr or b"not recognized" in signature.stderr
    outside = tmp_path / "keep-source.exe"
    outside.write_bytes(b"owned outside signing scope")
    command[command.index("-Files") + 1] = str(outside)
    refused = subprocess.run([*command, "-CheckPathsOnly"],  # noqa: S603 - fixed program, rejects own outside fixture
                             capture_output=True, check=False, timeout=30)
    assert refused.returncode != 0 and b"Unexpected" in refused.stderr
    assert hashlib.sha256(owned.read_bytes()).digest() == before
    assert outside.read_bytes() == b"owned outside signing scope"
