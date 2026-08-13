"""SI-FLW-052: 設計SSOTと出荷済みoperation catalogの契約を双方向照合する。"""

import json
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
FLOW = REPO / "plugins" / "bitz-flow"
DESIGN = FLOW / ".spec" / "design" / "FLW-DSN-012.md"
CATALOG = FLOW / "skills" / "flow-core" / "references" / "operation-catalog.md"
ALLOWLIST = FLOW / ".spec" / "catalog-consistency-exceptions.json"
FIELDS = ("class", "approval", "retry", "recovery")
DERIVED_CLASSES = {
    ("none", "none"): "read",
    ("local", "reversible"): "local-write",
    ("remote", "reversible"): "remote-write",
    ("local", "destructive"): "destructive",
    ("remote", "destructive"): "destructive",
}


def _expand_operation(value: str) -> list[str]:
    parts = value.split("/")
    domain, first = parts[0].split(".", 1)
    return [f"{domain}.{action}" for action in (first, *parts[1:])]


def _design_rows() -> dict[str, dict[str, str]]:
    text = DESIGN.read_text(encoding="utf-8")
    section = text.split("## 公開action catalog", 1)[1].split("## 正規状態への写像", 1)[0]
    rows: dict[str, dict[str, str]] = {}
    pattern = re.compile(
        r"^\| `(?P<operation>[^`]+)` \| (?P<write_target>[a-z-]+) \|"
        r" (?P<reversibility>[a-z-]+) \| (?P<class>[a-z-]+) \| (?P<approval>[a-z-]+) \|"
        r" [^|]+ \| (?P<retry>[a-z-]+) \| (?P<recovery>[^|]+) \|$"
    )
    for line in section.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        values = match.groupdict()
        recovery = values["recovery"].strip().strip("`")
        for operation in _expand_operation(values["operation"]):
            rows[operation] = {
                "class": values["class"],
                "write_target": values["write_target"],
                "reversibility": values["reversibility"],
                "approval": values["approval"],
                "retry": values["retry"],
                "recovery": recovery,
            }
    assert rows, "FLW-DSN-012の公開action catalogを解析できない"
    return rows


def _shipped_rows() -> dict[str, dict[str, str]]:
    text = CATALOG.read_text(encoding="utf-8")
    contract = text.split("### class / approval / retry / concurrency_key", 1)[1]
    contract = contract.split("### 追加 read operation", 1)[0]
    rows: dict[str, dict[str, str]] = {}
    pattern = re.compile(
        r"^\| `(?P<operation>[^`]+)` \| `(?P<class>[^`]+)` \| `(?P<approval>[^`]+)` \|"
        r" `(?P<retry>[^`]+)` \|"
    )
    for line in contract.splitlines():
        match = pattern.match(line)
        if match:
            values = match.groupdict()
            rows[values.pop("operation")] = values

    details = text.split("### write operation", 1)[1].split("## M1 の確認シナリオ", 1)[0]
    recovery_pattern = re.compile(
        r"^\| `(?P<operation>git\.[a-z-]+)` \|(?:[^|]+\|){5} `(?P<recovery>REC-[A-Z-]+)` \|$"
    )
    for line in details.splitlines():
        match = recovery_pattern.match(line)
        if match and match.group("operation") in rows:
            rows[match.group("operation")]["recovery"] = match.group("recovery")
    assert rows, "出荷済みoperation catalogを解析できない"
    return rows


def _observed_exceptions() -> set[str]:
    design = _design_rows()
    shipped = _shipped_rows()
    shared = set(design) & set(shipped)
    assert shared, "設計と出荷済みcatalogに共通operationがない"
    observed: set[str] = set()
    for operation in sorted(shared):
        for field in FIELDS:
            if field not in shipped[operation]:
                continue
            expected = design[operation][field]
            actual = shipped[operation][field]
            if expected != actual:
                observed.add(f"{operation}:{field}:{expected}!={actual}")
    return observed


def test_design_and_shipped_catalog_exceptions_are_exact_and_shrink_only() -> None:
    config = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    assert config["schema_version"] == 1
    assert config["additions_allowed"] is False
    expected = config["exceptions"]
    assert expected == sorted(set(expected)), "exception list must be unique and sorted"
    observed = _observed_exceptions()
    assert observed == set(expected), (
        "operation catalog exceptions changed. New exceptions are forbidden; fixed exceptions "
        "must be removed in the same change. "
        f"new={sorted(observed - set(expected))}, stale={sorted(set(expected) - observed)}"
    )


def test_catalog_exception_scope_is_fixed() -> None:
    config = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    assert config["issue"] == "SI-FLW-052"
    assert config["exceptions"] == []


def test_legacy_class_is_derived_from_orthogonal_axes() -> None:
    rows = _design_rows()
    for operation, row in rows.items():
        axes = (row["write_target"], row["reversibility"])
        assert axes in DERIVED_CLASSES, f"{operation}: invalid axes {axes}"
        assert row["class"] == DERIVED_CLASSES[axes], (
            f"{operation}: class must be derived from axes; "
            f"expected={DERIVED_CLASSES[axes]}, actual={row['class']}"
        )
