from pathlib import Path

import pytest

from privacylens_analysis.contract import validate_evidence
from privacylens_analysis.static.analyzer import facts_to_evidence
from privacylens_analysis.static.apk_reader import AndroguardReader, ApkFacts, ApkReadError
from privacylens_analysis.static.sdk_signatures import SignatureIndex, Tracker, load_trackers
from privacylens_analysis.static.sensitive_apis import match_sensitive_api, to_dotted

FIX = Path(__file__).parent / "fixtures"


def test_dalvik_name_conversion():
    assert to_dotted("Lcom/foo/Bar$Baz;") == "com.foo.Bar$Baz"
    assert to_dotted("com.foo.Bar") == "com.foo.Bar"


def test_sensitive_api_matching():
    assert match_sensitive_api("Landroid/location/LocationManager;", "getLastKnownLocation") == \
        "android.location.LocationManager.getLastKnownLocation"
    assert match_sensitive_api("Landroid/location/LocationManager;", "isProviderEnabled") is None
    assert match_sensitive_api("Lcom/foo/Other;", "getLastKnownLocation") is None


def test_seed_signatures_load():
    names = {t.name for t in load_trackers()}
    assert {"Google AdMob", "Facebook Ads", "Flurry"} <= names


def test_sdk_matching_prefix_rules():
    idx = SignatureIndex([Tracker("1", "Foo Ads", ("com.foo.ads",), ("Advertisement",))])
    hits = idx.match(["Lcom/foo/ads/Banner$Listener;", "com.foo.ads.Interstitial", "com.foo.adsense.X", "com.foo.Other"])
    assert len(hits) == 1 and hits[0].class_count == 2          # 'adsense' must NOT match 'ads'
    assert hits[0].sample_class == "com.foo.ads.Banner"


def test_nested_exodus_style_signature_cleanup(tmp_path):
    f = tmp_path / "sig.json"
    f.write_text('{"trackers": {"9": {"name": "Esc", "code_signature": "com\\\\.esc\\\\.sdk.|", "categories": []},'
                 ' "10": {"name": "NetOnly", "code_signature": "", "network_signature": "x\\\\.com"}}}')
    ts = load_trackers(f)
    assert [t.name for t in ts] == ["Esc"] and ts[0].code_signatures == ("com.esc.sdk",)


def test_facts_to_evidence_end_to_end():
    facts = ApkFacts.from_json_file(FIX / "sample_facts.json")
    rows = facts_to_evidence(facts)
    for r in rows:
        validate_evidence(r)
    perms = [r["raw_value"] for r in rows if r["raw_type"] == "permission"]
    assert "android.permission.READ_CONTACTS" in perms and len(perms) == 5
    apis = {r["raw_value"]: r["meta"]["call_sites"] for r in rows if r["raw_type"] == "api_call"}
    assert apis["android.location.LocationManager.getLastKnownLocation"] == 3
    sdks = {r["raw_value"]: r for r in rows if r["raw_type"] == "sdk"}
    assert set(sdks) == {"Google Firebase Analytics", "Google AdMob", "Facebook Ads", "Facebook Analytics", "Mixpanel"}
    assert sdks["Google Firebase Analytics"]["meta"]["class_count"] == 2
    assert sdks["Google AdMob"]["meta"]["exodus_categories"] == ["Advertisement"]
    assert all(r["source"] == "sdk" for r in sdks.values())


def test_reader_reports_missing_file_and_missing_androguard(tmp_path):
    with pytest.raises(ApkReadError):
        AndroguardReader().read(tmp_path / "nope.apk")
    apk = tmp_path / "x.apk"
    apk.write_bytes(b"PK")
    try:
        import androguard  # noqa: F401
    except ImportError:
        with pytest.raises(ApkReadError, match="androguard"):
            AndroguardReader().read(apk)
