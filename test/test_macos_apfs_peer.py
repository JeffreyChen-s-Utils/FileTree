"""APFS peer mutations derive a container only from the newly owned image's checked physical store."""

from types import SimpleNamespace

import pytest

from tools import macos_apfs_peer as peer


def _image(metadata):
    return SimpleNamespace(device="/dev/disk5", check=lambda: metadata)


def test_peer_container_requires_its_owned_physical_store():
    metadata = {"APFSContainerReference": "disk6", "APFSPhysicalStores": [{"APFSPhysicalStore": "disk5s1"}]}
    assert peer.owned_container(_image(metadata)) == "/dev/disk6"
    metadata["APFSPhysicalStores"][0]["APFSPhysicalStore"] = "disk50s1"
    with pytest.raises(RuntimeError, match="another image"):
        peer.owned_container(_image(metadata))


@pytest.mark.parametrize("metadata", [{}, {"APFSContainerReference": "disk6", "APFSPhysicalStores": []},
                                      {"APFSContainerReference": "/dev/disk6", "APFSPhysicalStores": [{}]},
                                      {"APFSContainerReference": "disk6", "APFSPhysicalStores": [{}, {}]}])
def test_unknown_or_multiple_physical_stores_never_grant_peer_mutation(metadata):
    with pytest.raises(RuntimeError, match="mapping unavailable"):
        peer.owned_container(_image(metadata))


def test_native_usage_is_bounded_and_does_not_guess_missing_options(monkeypatch):
    def run(args, **_kwargs):
        assert args == ["/usr/sbin/diskutil", "apfs", "addVolume"]
        return SimpleNamespace(returncode=1, stdout=b"Usage: -reserve -quota -nomount", stderr=b"")

    monkeypatch.setattr(peer.subprocess, "run", run)
    assert "-quota" in peer.native_usage()
    monkeypatch.setattr(peer.subprocess, "run", lambda *_a, **_k:
                        SimpleNamespace(returncode=1, stdout=b"Usage: addVolume", stderr=b""))
    with pytest.raises(RuntimeError, match="options unavailable"):
        peer.native_usage()


def test_unmounted_peer_device_must_belong_to_its_owned_container(monkeypatch):
    image = _image({})
    image.volume_uuid = "primary-uuid"
    monkeypatch.setattr(peer, "owned_container", lambda owner: "/dev/disk6")
    metadata = {"Containers": [{"ContainerReference": "disk6", "Volumes": [
        {"Name": "owned-peer", "DeviceIdentifier": "disk9s1", "APFSVolumeUUID": "peer-uuid",
         "CapacityReserve": peer._RESERVE, "CapacityQuota": peer._QUOTA}]}]}
    calls = []

    def query(args):
        calls.append(args)
        return metadata

    monkeypatch.setattr(peer, "plist", query)
    with pytest.raises(RuntimeError, match="unmounted owned-container"):
        peer.peer_metadata(image, "owned-peer", "/dev/disk6")
    assert len(calls) == 1, "a foreign device must never be queried as owned"


def test_unmounted_peer_cross_checks_uuid_without_inventing_capacity(monkeypatch):
    image = _image({})
    image.volume_uuid = "primary-uuid"
    monkeypatch.setattr(peer, "owned_container", lambda owner: "/dev/disk6")
    metadata = {"Containers": [{"ContainerReference": "disk6", "Volumes": [
        {"Name": "owned-peer", "DeviceIdentifier": "disk6s2", "APFSVolumeUUID": "peer-uuid",
         "CapacityReserve": peer._RESERVE, "CapacityQuota": peer._QUOTA}]}]}
    info = {"VolumeName": "owned-peer", "DeviceIdentifier": "disk6s2", "VolumeUUID": "peer-uuid",
            "APFSContainerReference": "disk6", "FilesystemType": "apfs"}
    monkeypatch.setattr(peer, "plist", lambda args: metadata if args[1] == "apfs" else info)
    assert peer.peer_metadata(image, "owned-peer", "/dev/disk6") == (info, metadata)
    info["VolumeUUID"] = "changed-uuid"
    with pytest.raises(RuntimeError, match="identity unavailable"):
        peer.peer_metadata(image, "owned-peer", "/dev/disk6")
