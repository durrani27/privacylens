"""
Watch-list of privacy-relevant Android API calls looked for in the disassembled code.

This list answers "which calls do we look for?". It deliberately carries NO privacy category;
turning an API into a taxonomy category (location, identifiers, ...) is the job of Member 3's
normalisation layer, so the two members never edit the same mapping.

LIMITATION (documented, planned for Iteration 5): only METHOD calls are detected. Field reads
such as ContactsContract.Contacts.CONTENT_URI are not, so contact access is covered through the
READ_CONTACTS permission instead.
"""
from __future__ import annotations

from typing import Optional

SENSITIVE_APIS: dict[str, frozenset[str]] = {
    "android.location.LocationManager": frozenset(
        {"getLastKnownLocation", "requestLocationUpdates", "requestSingleUpdate"}),
    "com.google.android.gms.location.FusedLocationProviderClient": frozenset(
        {"getLastLocation", "getCurrentLocation", "requestLocationUpdates"}),
    "android.net.wifi.WifiManager": frozenset({"getScanResults", "getConnectionInfo"}),
    "android.hardware.Camera": frozenset({"open"}),
    "android.hardware.camera2.CameraManager": frozenset({"openCamera"}),
    "android.media.AudioRecord": frozenset({"startRecording"}),
    "android.media.MediaRecorder": frozenset({"setAudioSource"}),
    "android.telephony.TelephonyManager": frozenset(
        {"getDeviceId", "getImei", "getMeid", "getSubscriberId", "getLine1Number", "getSimSerialNumber"}),
    "com.google.android.gms.ads.identifier.AdvertisingIdClient": frozenset({"getAdvertisingIdInfo"}),
    "android.telephony.SmsManager": frozenset({"sendTextMessage", "sendMultipartTextMessage"}),
}


def to_dotted(dalvik_name: str) -> str:
    """'Lcom/foo/Bar$Baz;' -> 'com.foo.Bar$Baz'; dotted names pass through."""
    name = dalvik_name
    if name.startswith("L") and name.endswith(";"):
        name = name[1:-1]
    return name.replace("/", ".")


def match_sensitive_api(class_name: str, method_name: str) -> Optional[str]:
    """Return 'pkg.Class.method' when the (class, method) pair is on the watch-list."""
    cls = to_dotted(class_name)
    if method_name in SENSITIVE_APIS.get(cls, ()):
        return f"{cls}.{method_name}"
    return None
