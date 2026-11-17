"""Stepごとの完了fixtureの一覧（`steps.json`）が、実装計画の完了条件と一致することを確かめる（ADR-052）。

実装計画はGate条件の正本であり、各Stepの完了条件をID列の散文で書く。`steps.json`はGate Bの実行に使う
機械可読な写しである。散文のID列は次の規則で読む。

- 接頭辞のない番号は、同じ段落で直前に現れた接頭辞（`SINGLE-`または`MULTI-`）を引き継ぐ。
- `A`〜`B`は範囲を表す。枝番付きの`A`に2桁の`B`が続けば同じファミリーの枝番の範囲、
  3桁どうしならファミリーの範囲（枝番をすべて含む）とする。

実寸の上限のfixture（適合fixture仕様 §3.4が名前を挙げるファミリー）は、手動で実行する検証であり、Stepに含めない
（ADR-076）。`steps.json`の`manual`がその一覧を持つ。実装計画の範囲表記がそれらを含んでも、各Stepからは除いて照合し、
`manual`は§3.4が挙げるファミリーのmatrixのIDと、生成fixtureのディレクトリにちょうど対応することを確かめる。
"""
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PLAN = ROOT / "docs/04.提案資料/12_Core-1.0実装計画.md"
MATRIX = ROOT / "docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md"
SECTIONS = {1: "## 4. Step 1", 2: "## 5. Step 2", 3: "## 6. Step 3", 4: "## 7. Step 4", 5: "## 8. Step 5"}
TOKEN = re.compile(r"`((?:SINGLE|MULTI)-)?(\d{3})(?:-(\d{2}))?`(?:〜`((?:SINGLE|MULTI)-)?(\d{2,3})(?:-(\d{2}))?`)?")


MANUAL_SENTENCE = re.compile(r"実寸の上限のfixture（([^）]*)）")
MANUAL_FAMILY = re.compile(r"`((?:SINGLE|MULTI)-\d{3})-\*`")


def manual_families(text=None):
    """適合fixture仕様 §3.4が手動の検証として名前を挙げるファミリー（例: `MULTI-020`）。"""
    text = MATRIX.read_text() if text is None else text
    match = MANUAL_SENTENCE.search(text)
    if match is None:
        raise ValueError("適合fixture仕様に実寸の上限のfixtureの一覧がありません")
    families = MANUAL_FAMILY.findall(match.group(1))
    if not families:
        raise ValueError("適合fixture仕様の実寸の上限のfixtureの一覧が空です")
    return families


def matrix_ids(text=None):
    text = MATRIX.read_text() if text is None else text
    return re.findall(r"^\| `((?:SINGLE|MULTI)-\d{3}(?:-\d{2})?)` \|", text, re.M)


def expand(ids, prefix, family, sub, end_family=None, end_sub=None):
    def parts(identifier):
        head, number = identifier.rsplit("-", 1) if identifier.count("-") == 2 else (identifier, None)
        return head.split("-")[0] + "-", int(head.split("-")[1]), (int(number) if number else None)
    selected = set()
    for identifier in ids:
        own_prefix, own_family, own_sub = parts(identifier)
        if own_prefix != prefix:
            continue
        if end_family is None:
            if own_family == family and (sub is None or own_sub == sub):
                selected.add(identifier)
        elif sub is not None:
            last = end_family if end_sub is None else end_sub
            if own_family == family and own_sub is not None and sub <= own_sub <= last:
                selected.add(identifier)
        elif family <= own_family <= end_family:
            selected.add(identifier)
    return selected


def plan_steps(plan_text=None, ids=None):
    """実装計画の各Stepの完了条件の段落から、IDの集合を読む。"""
    plan_text = PLAN.read_text() if plan_text is None else plan_text
    ids = matrix_ids() if ids is None else ids
    steps = {}
    for step, heading in SECTIONS.items():
        start = plan_text.index(heading)
        end = plan_text.find("\n## ", start + 1)
        body = plan_text[start:end if end >= 0 else len(plan_text)]
        body = body[body.index("完了条件"):]
        selected, prefix = set(), None
        for paragraph in body.split("\n\n"):
            for match in TOKEN.finditer(paragraph):
                prefix = match.group(1) or prefix
                if prefix is None:
                    raise ValueError(f"Step {step}: 接頭辞のないIDがあります")
                family, sub = int(match.group(2)), (int(match.group(3)) if match.group(3) else None)
                if match.group(5) is None:
                    selected |= expand(ids, prefix, family, sub)
                elif sub is not None and len(match.group(5)) == 2:
                    selected |= expand(ids, prefix, family, sub, family, int(match.group(5)))
                else:
                    end_family = int(match.group(5))
                    end_sub = int(match.group(6)) if match.group(6) else None
                    if sub is not None:
                        selected |= expand(ids, prefix, family, sub, end_family, end_sub)
                    else:
                        selected |= expand(ids, prefix, family, None, end_family)
        steps[step] = selected
    return steps


def validate(root=HERE, plan_text=None):
    errors = []
    ids = matrix_ids()
    try:
        document = json.loads((root / "steps.json").read_text())
        declared = {entry["step"]: entry for entry in document["steps"]}
        planned = plan_steps(plan_text, ids)
        manual_list = document["manual"]["fixtures"]
        families = manual_families()
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"status": "Failed", "errors": [f"steps.json: {str(error).splitlines()[0]}"]}
    manual = set(manual_list)
    expected_manual = {identifier for identifier in ids if identifier.rsplit("-", 1)[0] in families}
    if manual_list != sorted(manual, key=lambda value: ids.index(value) if value in ids else len(ids)):
        errors.append("手動の一覧のIDがmatrixの順序で重複なく並んでいません")
    if manual != expected_manual:
        errors.append(f"手動の一覧が適合fixture仕様 §3.4の実寸の上限のfixtureと一致しません: "
                      f"欠落={sorted(expected_manual - manual)}、余分={sorted(manual - expected_manual)}")
    for identifier in manual_list:
        fixture = root / "multi" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
        except (OSError, ValueError):
            errors.append(f"{identifier}: 手動の一覧のfixtureのディレクトリがありません")
            continue
        if manifest.get("fixtureId") != identifier or "generate" not in manifest.get("setup", {}):
            errors.append(f"{identifier}: 手動の一覧のfixtureは実寸の入力を生成するfixtureである必要があります")
    planned = {step: selected - manual for step, selected in planned.items()}
    if sorted(declared) != sorted(planned):
        errors.append("`steps.json`のStepが実装計画と異なります")
    parser_ids = set()
    for step, entry in sorted(declared.items()):
        fixtures, parser_checks = set(entry["fixtures"]), set(entry.get("parserChecks", []))
        if entry["fixtures"] != sorted(fixtures, key=ids.index) or entry.get("parserChecks", []) != sorted(parser_checks, key=ids.index):
            errors.append(f"Step {step}: IDがmatrixの順序で重複なく並んでいません")
        if fixtures & parser_checks:
            errors.append(f"Step {step}: 公開結果と構文解析器の受入の両方に同じIDがあります")
        if (fixtures | parser_checks) & manual:
            errors.append(f"Step {step}: 手動で実行する実寸の上限のfixtureをStepに置いています")
        if fixtures | parser_checks != planned.get(step, set()):
            errors.append(f"Step {step}: 実装計画の完了条件と一致しません")
        for identifier in sorted(parser_checks):
            manifest = json.loads((root / "single" / identifier / "manifest.json").read_text())
            if "parserChecks" not in manifest:
                errors.append(f"{identifier}: `parserChecks`を持たないfixtureを構文解析器の受入に置いています")
        parser_ids |= parser_checks
    public = {identifier for entry in declared.values() for identifier in entry["fixtures"]}
    for identifier in sorted(set(ids) - public - manual):
        errors.append(f"{identifier}: 公開結果を比較するStepも手動の一覧もありません")
    for path in sorted((root / "single").glob("*/manifest.json")):
        if "parserChecks" in json.loads(path.read_text()) and path.parent.name not in parser_ids:
            errors.append(f"{path.parent.name}: 構文解析器の受入を行うStepがありません")
    return {"steps": {str(step): len(entry["fixtures"]) for step, entry in sorted(declared.items())},
            "manual": len(manual_list),
            "status": "Passed" if not errors else "Failed", "errors": errors}
