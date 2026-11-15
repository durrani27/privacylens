"""
Evidence normalisation layer: ONE shared taxonomy for all four witnesses.

Input rows come from Member 1 (Data Safety) and Member 2 (permissions, API calls, SDKs, policy
sentences). Every mapping table lives here, so a location permission, a location API call, a
location Data Safety field and a location policy sentence all end up with category="location".

A single raw row can map to several categories (e.g. the Flurry SDK is Analytics AND
Advertisement), so normalisation may return MORE rows than it was given. Rows that cannot be
mapped (e.g. Data Safety "Financial info", which is outside the taxonomy) are dropped.
"""
from __future__ import annotations

from typing import Iterable

from .contract import TAXONOMY

PERMISSION_MAP: dict[str, str] = {
    "android.permission.ACCESS_FINE_LOCATION": "location",
    "android.permission.ACCESS_COARSE_LOCATION": "location",
    "android.permission.ACCESS_BACKGROUND_LOCATION": "location",
    "android.permission.CAMERA": "camera",
    "android.permission.RECORD_AUDIO": "microphone",
    "android.permission.READ_CONTACTS": "contacts",
    "android.permission.WRITE_CONTACTS": "contacts",
    "android.permission.GET_ACCOUNTS": "identifiers",
    "android.permission.READ_PHONE_STATE": "identifiers",
    "com.google.android.gms.permission.AD_ID": "identifiers",
    "android.permission.READ_PHONE_NUMBERS": "phone_sms",
    "android.permission.READ_CALL_LOG": "phone_sms",
    "android.permission.WRITE_CALL_LOG": "phone_sms",
    "android.permission.CALL_PHONE": "phone_sms",
    "android.permission.SEND_SMS": "phone_sms",
    "android.permission.RECEIVE_SMS": "phone_sms",
    "android.permission.READ_SMS": "phone_sms",
    "android.permission.READ_CALENDAR": "calendar",
    "android.permission.WRITE_CALENDAR": "calendar",
    "android.permission.READ_EXTERNAL_STORAGE": "storage",
    "android.permission.WRITE_EXTERNAL_STORAGE": "storage",
    "android.permission.MANAGE_EXTERNAL_STORAGE": "storage",
    "android.permission.READ_MEDIA_IMAGES": "storage",
    "android.permission.READ_MEDIA_VIDEO": "storage",
    "android.permission.READ_MEDIA_AUDIO": "storage",
}

# keyed by the class part of 'pkg.Class.method' (the method does not change the category)
API_CLASS_MAP: dict[str, str] = {
    "android.location.LocationManager": "location",
    "com.google.android.gms.location.FusedLocationProviderClient": "location",
    "android.net.wifi.WifiManager": "location",
    "android.hardware.Camera": "camera",
    "android.hardware.camera2.CameraManager": "camera",
    "android.media.AudioRecord": "microphone",
    "android.media.MediaRecorder": "microphone",
    "android.telephony.TelephonyManager": "identifiers",
    "com.google.android.gms.ads.identifier.AdvertisingIdClient": "identifiers",
    "android.telephony.SmsManager": "phone_sms",
}

EXODUS_CATEGORY_MAP: dict[str, str] = {
    "analytics": "analytics",
    "crash reporting": "analytics",
    "profiling": "analytics",
    "advertisement": "advertising",
    "location": "location",
    "identification": "identifiers",
}

DATA_SAFETY_CATEGORY_MAP: dict[str, str] = {
    "location": "location",
    "contacts": "contacts",
    "photos and videos": "camera",
    "audio": "microphone",
    "audio files": "microphone",
    "calendar": "calendar",
    "device or other ids": "identifiers",
    "app activity": "analytics",
    "app info and performance": "analytics",
    "messages": "phone_sms",
    "files and docs": "storage",
}
# A Data Safety PURPOSE also implies a purpose-category, whatever data type it was declared for.
DATA_SAFETY_PURPOSE_MAP: dict[str, str] = {
    "advertising or marketing": "advertising",
    "analytics": "analytics",
}


def _api_class(raw_value: str) -> str:
    return raw_value.rsplit(".", 1)[0]


def categories_for(row: dict) -> list[tuple[str, str]]:
    """Return [(category, how)] for one raw evidence row."""
    existing = row.get("category")
    if existing:  # policy / review rows are classified by Member 2's NLP already
        return [(existing, "classifier")] if existing in TAXONOMY else []

    raw_type, value = row.get("raw_type"), row.get("raw_value", "")
    meta = row.get("meta") or {}
    found: list[tuple[str, str]] = []

    if raw_type == "permission" and value in PERMISSION_MAP:
        found.append((PERMISSION_MAP[value], "permission_map"))
    elif raw_type == "api_call" and _api_class(value) in API_CLASS_MAP:
        found.append((API_CLASS_MAP[_api_class(value)], "api_map"))
    elif raw_type == "sdk":
        for c in meta.get("exodus_categories") or []:
            cat = EXODUS_CATEGORY_MAP.get(str(c).lower())
            if cat:
                found.append((cat, "exodus_map"))
    elif raw_type == "data_safety_field":
        cat = DATA_SAFETY_CATEGORY_MAP.get(str(meta.get("ds_category", value.split(" > ")[0])).lower())
        if cat:
            found.append((cat, "data_safety_map"))
        for purpose in meta.get("purposes") or []:
            pcat = DATA_SAFETY_PURPOSE_MAP.get(str(purpose).lower())
            if pcat:
                found.append((pcat, "data_safety_purpose"))

    seen, unique = set(), []
    for item in found:  # de-duplicate (same category reached twice from one row)
        if item[0] not in seen:
            seen.add(item[0])
            unique.append(item)
    return unique


def normalize(rows: Iterable[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        for category, how in categories_for(row):
            new = dict(row)
            new["category"] = category
            new["meta"] = {**(row.get("meta") or {}), "normalized_via": how}
            out.append(new)
    return out
