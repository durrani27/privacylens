"""
Thin Androguard adapter: APK file -> ApkFacts (plain data).

Keeping Androguard behind this single class means everything downstream is pure Python,
unit-testable without an APK, and the analysis can be demoed from a facts JSON file.
Androguard is imported lazily so the rest of the package works without it.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .sensitive_apis import match_sensitive_api, to_dotted


class ApkReadError(RuntimeError):
    pass


@dataclass
class ApkFacts:
    package: str = ""
    version_name: str = ""
    permissions: list[str] = field(default_factory=list)
    class_names: list[str] = field(default_factory=list)       # dotted, bundled (non-framework) classes
    api_calls: dict[str, int] = field(default_factory=dict)   # 'pkg.Class.method' -> call-site count

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "ApkFacts":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


class AndroguardReader:
    """Reads manifest permissions, bundled classes and sensitive API call sites."""

    def read(self, apk_path: str | Path) -> ApkFacts:
        path = Path(apk_path)
        if not path.is_file():
            raise ApkReadError(f"APK not found: {path}")
        try:
            from androguard.misc import AnalyzeAPK  # lazy import
        except ImportError as exc:
            raise ApkReadError("androguard is not installed (pip install androguard)") from exc
        try:
            apk, _dex, analysis = AnalyzeAPK(str(path))
            facts = ApkFacts(
                package=apk.get_package() or "",
                version_name=apk.get_androidversion_name() or "",
                permissions=sorted(set(apk.get_permissions() or [])),
            )
            classes = []
            for cls in analysis.get_classes():
                if getattr(cls, "is_external", lambda: False)():
                    continue  # framework / library stubs, not code shipped inside the APK
                classes.append(to_dotted(cls.name))
            facts.class_names = sorted(set(classes))

            for method in analysis.get_methods():
                if not method.is_external():
                    continue
                hit = match_sensitive_api(method.class_name, method.name)
                if hit:
                    sites = len(list(method.get_xref_from()))
                    if sites:
                        facts.api_calls[hit] = facts.api_calls.get(hit, 0) + sites
            return facts
        except ApkReadError:
            raise
        except Exception as exc:  # noqa: BLE001 - corrupt/obfuscated APKs raise many types
            raise ApkReadError(f"could not analyse APK: {type(exc).__name__}: {exc}") from exc
