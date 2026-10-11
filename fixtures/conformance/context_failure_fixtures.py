"""`context`が非成功になる場合を固定するレビュー済みの入力と期待値（本番のコンテキスト解決器やハッシュ値の計算はない）。

`SINGLE-147`と`SINGLE-148`は、状態が`accepted`でないADR（`proposed`）への`requires`を固定する。参照先の型の組が表
（関係・トレースモデル §4）を満たさないので、状態の検査（`CTX-STATE-001`、`blocked`）ではなく型制約の
`CTX-RELATION-TYPE-001`（`failed`）で返す。診断の発生元は関係を宣言した文書（`relations.requires`）である。
`SINGLE-148`は、独立した別の原因（状態`draft`のREQ-002への`requires`）も同じ文書が持つ。状態の検査と型制約の検査は一方が
非成功でも他方を行い、独立した元の原因として両方の診断を返す（`context` §3、診断レジストリ）。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from .harness import git, setup
from .initial_fixtures import CONFIGS, observe, compare_state
from .trace_fixtures import TECH, TECH_PATH
from .git_fixtures import TASK_PATH
from .expansion_fixtures import requirement

HERE = Path(__file__).resolve().parent
CASES = {
    "SINGLE-050": ("TECH-999", "interpret", "failed", "CTX-ROOT-MISSING-001", "起点TECH-999が存在しません"),
    "SINGLE-051": ("TASK-001", "implement", "blocked", "CTX-TASK-DEPENDENCY-001", "先行TASK-002が完了していません"),
    "SINGLE-144": ("TASK-001", "implement", "blocked", "CTX-TASK-DEPENDENCY-001", "先行TASK-002が完了していません"),
    "SINGLE-147": ("TASK-001", "implement", "failed", "CTX-RELATION-TYPE-001", "TASKからADRへのrequiresは許可されません"),
    "SINGLE-148": ("REQ-001", "implement", "failed", "CTX-RELATION-TYPE-001", "REQからADRへのrequiresは許可されません"),
    "SINGLE-052-01": ("TECH-001", "implement", "blocked", "CTX-STATE-SUPERSEDED-001", "起点TECH-001はTECH-002に置換されています"),
    "SINGLE-052-02": ("TECH-003", "implement", "blocked", "CTX-STATE-SUPERSEDED-001", "依存先TECH-001はTECH-002に置換されています"),
    "SINGLE-053": ("TECH-001", "implement", "failed", "CTX-STATE-SUPERSEDED-002", "TECH-001の有効な後継が複数存在します"),
    "SINGLE-127-13": ("TECH-999", "interpret", "failed", "CTX-ROOT-MISSING-001", "起点TECH-999が存在しません"),
}
TASK = "---\nid: TASK-001\ntitle: 先行作業の確認\nstatus: open\n---\n\n# TASK-001 先行作業の確認\n\n## Objective\n\n先行作業の完了を確認する。\n"


# `SINGLE-144`: 起点のTASK-001の先行TASK-002が`cancelled`。起点が`addresses`するREQ-001（`approved`、`MUST`が1件）を置く。
# `SINGLE-051`と同じ単一の原因で、TASK-002の状態が`open`ではなく`cancelled`であることだけが異なる。
CANCELLED_PREREQUISITE_REQ = requirement(
    "REQ-001", "先行TASKが取消済みの起点の対象要求", [("REQ-001:AC-01", "入力を検証する")],
    verification="テスト対応は宣言しない。")
CANCELLED_PREREQUISITE_REQ_PATH = ".spec/requirements/REQ-001.md"


# `SINGLE-147`と`SINGLE-148`: 状態が`proposed`のADR-001。`requires`の参照先の型は、`accepted`のADRだけを許す。
PROPOSED_ADR_PATH = ".spec/decisions/ADR-001.md"
PROPOSED_ADR = (
    "---\nid: ADR-001\ntitle: 未承認の判断\nstatus: proposed\n---\n"
    "\n# ADR-001 未承認の判断\n"
    "\n## Context\n\n判断の背景。\n"
    "\n## Decision\n\n方式を提案する。\n"
    "\n## Consequences\n\n承認までは強い関係の参照先にしない。\n"
)
PROPOSED_ADR_FRONTMATTER = {"id": "ADR-001", "title": "未承認の判断", "status": "proposed"}
# `SINGLE-148`: REQ-001（`approved`）は、状態`draft`のREQ-002と状態`proposed`のADR-001を`requires`する。
DRAFT_REQ_PATH = ".spec/requirements/REQ-002.md"
TYPE_REQ_PATH = ".spec/requirements/REQ-001.md"
TYPE_REQUIRES = {"SINGLE-147": ["ADR-001"], "SINGLE-148": ["REQ-002", "ADR-001"]}
# `SINGLE-147`: 起点のTASK-001（`open`）が、状態`proposed`のADR-001を`requires`し、REQ-001:AC-01を`addresses`する。
TYPE_TASK_TITLE = "未承認の判断を前提にする作業"


def type_constraint_documents(identifier):
    if identifier == "SINGLE-147":
        head, body = requirement("REQ-001", "対象要求", [("REQ-001:AC-01", "入力を検証する")],
                                 verification="テスト対応は宣言しない。")
        root = TASK.replace("先行作業の確認", TYPE_TASK_TITLE).replace(
            "status: open\n---", "status: open\nrelations:\n  requires: [ADR-001]\n  addresses: [REQ-001:AC-01]\n---", 1)
        return {
            TASK_PATH: (root, {"id": "TASK-001", "title": TYPE_TASK_TITLE, "status": "open",
                               "relations": {"requires": ["ADR-001"], "addresses": ["REQ-001:AC-01"]}}),
            TYPE_REQ_PATH: (head + "\n" + body, {"id": "REQ-001", "title": "対象要求", "status": "approved"}),
            PROPOSED_ADR_PATH: (PROPOSED_ADR, PROPOSED_ADR_FRONTMATTER),
        }
    head, body = requirement("REQ-001", "二つの原因を持つ起点", [("REQ-001:AC-01", "入力を検証する")],
                             "relations:\n  requires: [REQ-002, ADR-001]\n", verification="テスト対応は宣言しない。")
    head2, body2 = requirement("REQ-002", "検討中の前提要求", [("REQ-002:AC-01", "前提を満たす")],
                               verification="テスト対応は宣言しない。")
    return {
        TYPE_REQ_PATH: (head + "\n" + body, {"id": "REQ-001", "title": "二つの原因を持つ起点", "status": "approved",
                                              "relations": {"requires": ["REQ-002", "ADR-001"]}}),
        DRAFT_REQ_PATH: (head2.replace("status: approved", "status: draft") + "\n" + body2,
                         {"id": "REQ-002", "title": "検討中の前提要求", "status": "draft"}),
        PROPOSED_ADR_PATH: (PROPOSED_ADR, PROPOSED_ADR_FRONTMATTER),
    }


def reviewed_documents(identifier):
    if identifier in TYPE_REQUIRES:
        return type_constraint_documents(identifier)
    if identifier == "SINGLE-144":
        head, body = CANCELLED_PREREQUISITE_REQ
        root = TASK.replace("先行作業の確認", "取消済みの先行作業を持つ作業").replace(
            "status: open\n---", "status: open\nrelations:\n  requires: [TASK-002]\n  addresses: [REQ-001:AC-01]\n---", 1)
        prerequisite = TASK.replace("TASK-001", "TASK-002").replace("status: open", "status: cancelled")
        return {
            TASK_PATH: (root, {"id": "TASK-001", "title": "取消済みの先行作業を持つ作業", "status": "open",
                               "relations": {"requires": ["TASK-002"], "addresses": ["REQ-001:AC-01"]}}),
            ".spec/tasks/TASK-002.md": (prerequisite, {"id": "TASK-002", "title": "先行作業の確認", "status": "cancelled"}),
            CANCELLED_PREREQUISITE_REQ_PATH: (head + "\n" + body, {"id": "REQ-001", "title": "先行TASKが取消済みの起点の対象要求",
                                                                  "status": "approved"}),
        }
    # YAMLと値の組を固定する。関係の意味はレビュー済みで、ここでは推測しない。
    if identifier == "SINGLE-051":
        root = TASK.replace("status: open\n---", "status: open\nrelations:\n  requires: [TASK-002]\n---", 1)
        return {TASK_PATH: (root, {"id": "TASK-001", "title": "先行作業の確認", "status": "open", "relations": {"requires": ["TASK-002"]}}),
            ".spec/tasks/TASK-002.md": (TASK.replace("TASK-001", "TASK-002"), {"id": "TASK-002", "title": "先行作業の確認", "status": "open"})}
    documents = {TECH_PATH: (TECH, {"id": "TECH-001", "title": "前提技術", "status": "approved"})}
    if identifier not in {"SINGLE-050", "SINGLE-127-13"}:
        for number in ([2, 3] if identifier == "SINGLE-053" else [2]):
            spec_id = f"TECH-{number:03}"
            doc = TECH.replace("TECH-001", spec_id).replace("status: approved\n---", "status: approved\nrelations:\n  supersedes: [TECH-001]\n---", 1)
            documents[f".spec/technical/{spec_id}.md"] = (doc, {"id": spec_id, "title": "前提技術", "status": "approved", "relations": {"supersedes": ["TECH-001"]}})
    if identifier == "SINGLE-052-02":
        doc = TECH.replace("TECH-001", "TECH-003").replace("status: approved\n---", "status: approved\nrelations:\n  requires: [TECH-001]\n---", 1)
        documents[".spec/technical/TECH-003.md"] = (doc, {"id": "TECH-003", "title": "前提技術", "status": "approved", "relations": {"requires": ["TECH-001"]}})
    return documents


def reviewed_inputs(identifier):
    return {".spec/bitz.yaml": CONFIGS["SINGLE-001"].encode(),
            **{path: doc.encode() for path, (doc, _) in reviewed_documents(identifier).items()}}


def reviewed_manifest(identifier):
    root, purpose, status, _, description = CASES[identifier]
    return {"fixtureId": identifier, "description": description, "setup": {"git": True, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": ["context", root, "--purpose", purpose, "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": 1 if status == "failed" else 2,
            "stdout": "json", "resultFile": "expected/context.json", "reportFileCount": 0}}


def reviewed_result(identifier):
    root, purpose, status, code, summary = CASES[identifier]
    diagnostics = None
    unresolved = 0
    if identifier in TYPE_REQUIRES:
        # 型制約の診断は、関係を宣言した文書の`relations.requires`から返し、`evidence`に参照先（ADR-001）を宣言どおりに持つ
        # （結果・診断・終了コード §4、診断レジストリ`RELATION-TYPE`）。型制約を満たさない強い関係は未解決として数える。
        origin = TASK_PATH if identifier == "SINGLE-147" else TYPE_REQ_PATH
        diagnostics = [{"code": code, "severity": "error", "resultStatus": "failed", "summary": summary,
                        "source": {"kind": "file", "workspaceId": "root", "path": origin, "key": "relations.requires"},
                        "evidence": "ADR-001"}]
        unresolved = 1
        if identifier == "SINGLE-148":
            # 独立した別の原因。状態`draft`のREQ-002は目的`implement`に適用できない。発生元は適用できない文書のファイル。
            # 診断の順序は`path`の辞書順（REQ-001.md < REQ-002.md）なので、型制約の診断が先になる。
            diagnostics.append({"code": "CTX-STATE-001", "severity": "error", "resultStatus": "blocked",
                                "summary": "REQ-002は現在のpurposeに適用できません",
                                "source": {"kind": "file", "workspaceId": "root", "path": DRAFT_REQ_PATH}})
        source = None
    elif identifier in {"SINGLE-050", "SINGLE-127-13"}:
        source = {"kind": "invocation", "argument": "TECH-999"}
    elif identifier in {"SINGLE-051", "SINGLE-144"}:
        source = {"kind": "file", "workspaceId": "root", "path": TASK_PATH, "key": "relations.requires"}
    else:
        source = {"kind": "file", "workspaceId": "root", "path": TECH_PATH}
    return {"schemaVersion": "1.0", "operation": "context", "status": status, "purpose": purpose,
        "workspace": {"id": "root", "path": "."}, "roots": [root], "contextDigest": None, "revision": None,
        "resolution": {"complete": False, "documentCount": 0, "unresolvedStrongRelations": unresolved},
        "projection": {"detail": "standard", "expanded": []}, "documents": [], "constraintLedger": {"statements": []},
        "coverage": {**{modality: {key: [] for key in ("total", "addressed", "tested", "unaddressed", "untested")}
                       for modality in ("must", "should", "may")}, "adjacent": []},
        "durationMs": 0,
        "diagnostics": diagnostics if diagnostics is not None else
        [{"code": code, "severity": "error", "resultStatus": status, "summary": summary, "source": source}]}


def check_cancelled_prerequisite(result):
    """`SINGLE-144`: 先行TASKの`cancelled`は、同じ原因の`CTX-STATE-001`を重ねず、`CTX-TASK-DEPENDENCY-001`だけで示す
    （診断レジストリの主診断の規則、ADR-029、ADR-036、関係・トレースモデル §6.2）。"""
    codes = [item["code"] for item in result["diagnostics"]]
    if codes != ["CTX-TASK-DEPENDENCY-001"]:
        raise ValueError("先行TASKが`cancelled`の起点は、`CTX-TASK-DEPENDENCY-001`だけを返す必要があります")
    source = result["diagnostics"][0]["source"]
    if source.get("path") != TASK_PATH or source.get("key") != "relations.requires":
        raise ValueError("診断の発生元は起点のTASKの`relations.requires`である必要があります")


def check_type_constraint(identifier, result):
    """`SINGLE-147`と`SINGLE-148`: 状態が`accepted`でないADRへの`requires`は、状態の診断（`CTX-STATE-001`）ではなく、型制約の
    `CTX-RELATION-TYPE-001`（`failed`）で返す（関係・トレースモデル §4・§5.1）。`SINGLE-148`は、独立した別の原因の
    `CTX-STATE-001`も返し、状態は最悪値の`failed`、未解決の強い関係は型制約の1件だけとする（`context` §3、結果・診断・終了コード §3）。"""
    expected = ["CTX-RELATION-TYPE-001"] + (["CTX-STATE-001"] if identifier == "SINGLE-148" else [])
    diagnostics = result["diagnostics"]
    if [item["code"] for item in diagnostics] != expected:
        raise ValueError("状態が`accepted`でないADRへの`requires`は、型制約の診断で返し、独立した原因の診断だけを併記する必要があります")
    primary = diagnostics[0]
    source = primary["source"]
    if (result["status"] != "failed" or primary["resultStatus"] != "failed" or primary.get("evidence") != "ADR-001"
            or source.get("key") != "relations.requires" or "line" in source):
        raise ValueError("型制約の診断は、`failed`で、関係を宣言した文書の`relations.requires`と`evidence`の参照先を持つ必要があります")
    if source["path"] != (TASK_PATH if identifier == "SINGLE-147" else TYPE_REQ_PATH):
        raise ValueError("型制約の診断の発生元は、関係を宣言した文書である必要があります")
    if result["resolution"] != {"complete": False, "documentCount": 0, "unresolvedStrongRelations": 1}:
        raise ValueError("型制約を満たさない強い関係は、未解決の強い関係として1件だけ数える必要があります")
    if identifier == "SINGLE-148":
        state = diagnostics[1]
        if (state["source"] != {"kind": "file", "workspaceId": "root", "path": DRAFT_REQ_PATH}
                or "evidence" in state or state["resultStatus"] != "blocked"):
            raise ValueError("状態の診断の発生元は、適用できないREQ-002のファイルである必要があります")


def check_type_inputs(identifier, documents):
    """原因は、状態`proposed`のADR-001への`requires`であり、`SINGLE-148`だけが状態`draft`のREQ-002への`requires`を併せ持つ。"""
    origin = documents[TASK_PATH if identifier == "SINGLE-147" else TYPE_REQ_PATH][1]
    adr = documents[PROPOSED_ADR_PATH][1]
    if origin["relations"]["requires"] != TYPE_REQUIRES[identifier] or adr["status"] != "proposed":
        raise ValueError("起点は、状態`proposed`のADR-001を`requires`する必要があります")
    if identifier == "SINGLE-147":
        if origin["status"] != "open" or origin["relations"]["addresses"] != ["REQ-001:AC-01"] \
                or documents[TYPE_REQ_PATH][1]["status"] != "approved":
            raise ValueError("起点のTASK-001は、状態`open`で、状態`approved`のREQ-001:AC-01を`addresses`する必要があります")
    elif origin["status"] != "approved" or documents[DRAFT_REQ_PATH][1]["status"] != "draft":
        raise ValueError("起点のREQ-001は状態`approved`で、REQ-002は状態`draft`である必要があります")


def check_unborn(repository, identifier):
    git(repository, "rev-parse", "--git-dir")
    if git(repository, "symbolic-ref", "HEAD").decode().strip() != "refs/heads/fixture":
        raise ValueError("コミットのないリポジトリのブランチが想定と異なります")
    try:
        git(repository, "rev-parse", "--verify", "HEAD")
    except subprocess.CalledProcessError:
        pass
    else:
        raise ValueError("`context`操作のfixtureに想定外のコミットがあります")
    if git(repository, "for-each-ref") or git(repository, "ls-files", "-z"):
        raise ValueError("`context`操作のfixtureはGitの参照もステージ済みのパスも持ってはいけません")
    actual = {p.relative_to(repository).as_posix(): p.read_bytes() for p in repository.rglob("*")
              if p.is_file() and ".git" not in p.relative_to(repository).parts}
    if actual != reviewed_inputs(identifier):
        raise ValueError("`context`操作のfixtureの作業ツリーがレビュー済みの入力と異なります")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads(schema_path(root, "frontmatter").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/context.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("起動条件または完全結果がレビュー済みの期待値と異なります")
            if identifier == "SINGLE-144":
                check_cancelled_prerequisite(result)
            elif identifier in TYPE_REQUIRES:
                check_type_constraint(identifier, result)
                check_type_inputs(identifier, reviewed_documents(identifier))
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name] for name, p in files.items()):
                raise ValueError("入力がレビュー済みの単一原因と異なります")
            for path, (_, fm) in reviewed_documents(identifier).items():
                kind = ("taskFrontmatter" if path.startswith(".spec/tasks/")
                        else "reqFrontmatter" if path.startswith(".spec/requirements/")
                        else "adrFrontmatter" if path.startswith(".spec/decisions/") else "techFrontmatter")
                Draft202012Validator({"$ref": "#/$defs/" + kind, "$defs": schema["$defs"]}).validate(fm)
            if effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-context-failure-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    check_unborn(repository, identifier)
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
