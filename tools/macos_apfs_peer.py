"""Fresh image-only APFS reservation/quota evidence; no existing container selector is accepted."""

from __future__ import annotations

import re
import subprocess
import uuid

from tools.macos_owned_image import OwnedImage, command, plist, require

_MIB = 1024 * 1024
_RESERVE = 16 * _MIB
_QUOTA = 64 * _MIB
_MAX_USAGE = 65536
_CONTAINER = re.compile(r"disk[0-9]+\Z")


def owned_container(image: OwnedImage) -> str:
    """Derive authority solely from this image's checked native mounted volume and physical store."""
    info = image.check()
    name = info.get("APFSContainerReference")
    stores = info.get("APFSPhysicalStores")
    require(isinstance(name, str) and _CONTAINER.fullmatch(name)
            and isinstance(stores, list) and len(stores) == 1 and isinstance(stores[0], dict),
            "Owned APFS container mapping unavailable")
    store = stores[0].get("APFSPhysicalStore")
    require(isinstance(store, str) and re.fullmatch(re.escape(image.device.removeprefix("/dev/")) + r"s[0-9]+", store),
            "APFS physical store belongs to another image")
    return "/dev/" + name


def native_usage() -> str:
    """Verify reserve/quota/no-mount options from the installed native command's own usage text."""
    arguments = ["/usr/sbin/diskutil", "apfs", "addVolume"]
    result = subprocess.run(arguments, check=False, timeout=30, capture_output=True)  # noqa: S603 # nosec B603
    text = result.stdout + result.stderr
    require(result.returncode in (0, 1) and len(text) <= _MAX_USAGE, "Unexpected native APFS usage response")
    usage = text.decode("utf-8")
    require(all(option in usage.casefold() for option in ("-reserve", "-quota", "-nomount")),
            "Installed native APFS reservation options unavailable")
    return usage


def peer_metadata(image: OwnedImage, name: str, container: str) -> tuple[dict, dict]:
    """Check the unmounted fresh peer through its owned container before querying its derived device."""
    require(owned_container(image) == container, "Owned APFS container changed")
    native = plist(["/usr/sbin/diskutil", "apfs", "list", "-plist", container])
    containers = native.get("Containers")
    require(isinstance(containers, list) and len(containers) == 1 and isinstance(containers[0], dict),
            "Private APFS container list unavailable")
    require(containers[0].get("ContainerReference") == container.removeprefix("/dev/"),
            "Private APFS container list changed")
    volumes = containers[0].get("Volumes")
    require(isinstance(volumes, list) and all(isinstance(entry, dict) for entry in volumes),
            "Private APFS volume list unavailable")
    peers = [entry for entry in volumes if entry.get("Name") == name]
    require(len(peers) == 1 and peers[0].get("CapacityReserve") == _RESERVE
            and peers[0].get("CapacityQuota") == _QUOTA, "Native configured APFS reserve/quota not verified")
    peer = peers[0]
    device = peer.get("DeviceIdentifier")
    require(isinstance(device, str) and re.fullmatch(re.escape(container.removeprefix("/dev/")) + r"s[0-9]+", device)
            and not peer.get("MountPoint"), "Fresh APFS peer is not an unmounted owned-container device")
    info = plist(["/usr/sbin/diskutil", "info", "-plist", "/dev/" + device])
    require(info.get("VolumeName") == name and not info.get("MountPoint")
            and info.get("APFSContainerReference") == container.removeprefix("/dev/")
            and info.get("FilesystemType") == "apfs" and info.get("DeviceIdentifier") == device
            and isinstance(info.get("VolumeUUID"), str) and bool(info["VolumeUUID"])
            and info["VolumeUUID"] != image.volume_uuid and peer.get("APFSVolumeUUID") == info["VolumeUUID"],
            "Private APFS peer identity unavailable")
    return info, native


def reservation_proof(image: OwnedImage) -> dict[str, object]:
    """Add only one freshly named peer in the already owned image; retain all actual native values."""
    from tools.validate_macos_volume import os_capacity  # noqa: PLC0415
    from je_file_tree.core.capacity import capacity_ledger  # noqa: PLC0415
    from je_file_tree.core.scanner import ScanOptions, scan  # noqa: PLC0415
    from tools.volume_evidence import ledger_record  # noqa: PLC0415

    usage = native_usage()
    container = owned_container(image)
    name = "FileTree-quota-" + uuid.uuid4().hex
    before = os_capacity(image.root)
    require(owned_container(image) == container, "Private image container changed before peer creation")
    command(["/usr/sbin/diskutil", "apfs", "addVolume", container, "APFS", name,
             "-reserve", str(_RESERVE), "-quota", str(_QUOTA), "-nomount"])
    info, native = peer_metadata(image, name, container)
    command(["/bin/sync"])
    tree = scan(image.root, options=ScanOptions(workers=1)).root
    ledger = capacity_ledger(tree)
    after_primary = os_capacity(image.root)
    require(ledger.total == after_primary["total"] and ledger.metadata_bytes is None
            and ledger.other_volumes_bytes is None, "Quota ledger invented independent filesystem buckets")
    current, current_native = peer_metadata(image, name, container)
    require(current["VolumeUUID"] == info["VolumeUUID"], "Owned quota peer changed")
    return {"configured_reserve": _RESERVE, "configured_quota": _QUOTA, "native_usage": usage,
            "native_initial": native, "native_after": current_native, "peer_volume": current,
            "primary_before": before, "primary_after": after_primary, "primary_ledger": ledger_record(ledger),
            "peer_capacity": None, "peer_ledger": None, "peer_mounted": False,
            "independent_reserved_bytes": None, "independent_shared_extent_bytes": None,
            "capacity_rows_are_not_additive": True, "host_containers_modified": False}
