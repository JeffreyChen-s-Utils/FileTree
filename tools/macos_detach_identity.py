"""Strict immutable APFS bindings for a normal detach retry of an already owned image."""

from __future__ import annotations

from dataclasses import dataclass
import re
import uuid

_DEVICE = re.compile(r"/dev/disk[0-9]+(?:s[0-9]+)*\Z")
_WHOLE = re.compile(r"/dev/disk[0-9]+\Z")
_ENTRIES = 64
_STORES = 8
_TEXT = 512
_DEVICE_TEXT = 128


@dataclass(frozen=True, slots=True)
class VolumeBinding:
    """Complete device topology and canonical volume identity captured while mounted and owned."""

    volume: str
    uuid: str
    name: str
    container: str
    stores: tuple[str, ...]
    registration: tuple[tuple[str, str], ...]


def registration(entries: list[dict]) -> tuple[tuple[str, str], ...] | None:
    """Freeze every unique native device/hint; malformed or truncated topology is never authority."""
    if not 1 <= len(entries) <= _ENTRIES:
        return None
    result = []
    for entry in entries:
        device, hint = entry.get("dev-entry"), entry.get("content-hint", "")
        if (not isinstance(device, str) or len(device) > _DEVICE_TEXT or not _DEVICE.fullmatch(device)
                or not isinstance(hint, str) or len(hint) > _TEXT or "\0" in hint):
            return None
        result.append((device, hint))
    return tuple(sorted(result)) if len({device for device, _hint in result}) == len(result) else None


def _stores(info: dict, devices: set[str], image: str) -> tuple[str, ...] | None:
    values = info.get("APFSPhysicalStores")
    if not isinstance(values, list) or not 1 <= len(values) <= _STORES:
        return None
    stores = []
    for item in values:
        identifier = item.get("APFSPhysicalStore") if isinstance(item, dict) else None
        device = "/dev/" + identifier if isinstance(identifier, str) else ""
        if (len(device) > _DEVICE_TEXT or not re.fullmatch(re.escape(image) + r"s[0-9]+", device)
                or device not in devices):
            return None
        stores.append(device)
    return tuple(sorted(stores)) if len(set(stores)) == len(stores) else None


def _uuid(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > _TEXT:
        return None
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return None
    return str(parsed) if parsed.int else None


def volume_binding(info: dict, entries: tuple[tuple[str, str], ...] | None,
                   name: str, image: str) -> VolumeBinding | None:
    """Require exact primary/container/store relationships in the complete owned registration."""
    if entries is None:
        return None
    devices = {device for device, _hint in entries}
    identifier, container_id = info.get("DeviceIdentifier"), info.get("APFSContainerReference")
    volume = "/dev/" + identifier if isinstance(identifier, str) else ""
    container = "/dev/" + container_id if isinstance(container_id, str) else ""
    stores = _stores(info, devices, image)
    volume_uuid = _uuid(info.get("VolumeUUID"))
    if (info.get("FilesystemType") != "apfs" or info.get("VolumeName") != name
            or len(name) > _TEXT or "\0" in name or volume_uuid is None or stores is None
            or len(volume) > _DEVICE_TEXT or len(container) > _DEVICE_TEXT
            or not _WHOLE.fullmatch(image) or image not in devices
            or not _WHOLE.fullmatch(container) or container == image or container not in devices
            or not re.fullmatch(re.escape(container) + r"s[0-9]+", volume) or volume not in devices
            or info.get("DeviceNode") != volume or info.get("ParentWholeDisk") != container_id):
        return None
    return VolumeBinding(volume, volume_uuid, name, container, stores, entries)
