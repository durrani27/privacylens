from consistency.contract import make_evidence as ev
from consistency.normalizer import categories_for, normalize


def cats(row):
    return [c for c, _ in categories_for(row)]


def test_permission_and_api_mapping():
    assert cats(ev("static", "permission", "android.permission.ACCESS_COARSE_LOCATION")) == ["location"]
    assert cats(ev("static", "permission", "android.permission.INTERNET")) == []          # not privacy-relevant
    assert cats(ev("static", "api_call", "android.media.AudioRecord.startRecording")) == ["microphone"]
    assert cats(ev("static", "permission", "com.google.android.gms.permission.AD_ID")) == ["identifiers"]


def test_one_sdk_can_map_to_several_categories():
    row = ev("sdk", "sdk", "Flurry", meta={"exodus_categories": ["Analytics", "Advertisement"]})
    assert cats(row) == ["analytics", "advertising"]
    assert cats(ev("sdk", "sdk", "X", meta={"exodus_categories": ["Crash reporting", "Analytics"]})) == ["analytics"]


def test_data_safety_type_and_purpose_mapping():
    row = ev("datasafety", "data_safety_field", "Location > Approximate location",
             meta={"ds_category": "Location", "purposes": ["App functionality", "Advertising or marketing", "Analytics"]})
    assert cats(row) == ["location", "advertising", "analytics"]
    assert cats(ev("datasafety", "data_safety_field", "Financial info > Purchase history",
                   meta={"ds_category": "Financial info", "purposes": []})) == []


def test_preclassified_policy_rows_pass_through_and_normalize_keeps_ids():
    pol = ev("policy", "policy_sentence", "We collect location.", category="location")
    pol["id"] = "p1"
    perm = ev("static", "permission", "android.permission.CAMERA")
    perm["id"] = "p2"
    out = normalize([pol, perm, ev("static", "permission", "android.permission.INTERNET")])
    assert [(r["id"], r["category"]) for r in out] == [("p1", "location"), ("p2", "camera")]
    assert out[1]["meta"]["normalized_via"] == "permission_map"
