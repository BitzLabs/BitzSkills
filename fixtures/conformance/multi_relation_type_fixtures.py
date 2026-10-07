"""複合ワークスペースで、他のメンバーの文書が持つ`requires`の型制約を固定するレビュー済みの入力と期待値（Coreの公開操作は実行しない）。

`MULTI-027-01/02`は、メンバー`web`のREQ-001が、メンバー`api`のTECH-020を`requires`し、TECH-020が状態`proposed`のADR-001を
`requires`する。参照先が状態`accepted`でないADRである`requires`は、関係・トレースモデル §4の型制約に反するので、状態の診断
（`CTX-STATE-001`、`blocked`）ではなく`CTX-RELATION-TYPE-001`（`failed`）で返す。

TECH-020は、呼び出し側のワークスペース`web`の文書ではなく、`api`の文書である。呼び出し側の関係の検査は、他のメンバーの文書を
見ない。そこで、他のメンバーの文書については、閉包を構成する`requires`の辺の型制約だけを`TargetExpansion`が返す
（関係・トレースモデル §6.3、`context` §3）。診断の発生元は関係を宣言した文書で、他のメンバーなら、そのメンバーの
`workspaceId`と、メンバーのワークスペース相対のパスである（複合ワークスペース仕様 §4）。`evidence`は、宣言した参照先を、
そのメンバーの中で書いた修飾のない形（`ADR-001`）で持つ（結果・診断・終了コード §4）。

期待値の根拠は規範文と、このモジュールの参照計算（`reference_diagnostics`）だけである。参照計算は入力の木構造から`requires`の
閉包をたどり、型の表（関係・トレースモデル §4）に照らして診断を導く。Coreの出力は期待値の根拠にしない。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import multi_crosscheck, multi_reference
from .context_failure_fixtures import PROPOSED_ADR, PROPOSED_ADR_PATH
from .digest_crosscheck import read_yaml
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
REQ_PATH = "apps/web/.spec/requirements/REQ-001.md"
TECH_PATH = "services/api/.spec/technical/TECH-020.md"
ADR_PATH = "services/api/" + PROPOSED_ADR_PATH
TEST_PATH = "apps/web/tests/test_login.py"
ORIGIN = {"kind": "file", "workspaceId": "api", "path": ".spec/technical/TECH-020.md",
          "key": "relations.requires"}
# id: (操作, 実行ディレクトリ, 引数列の残り, 起点, 説明)
CASES = {
    "MULTI-027-01": ("context", "apps/web",
                     ["context", "REQ-001", "--purpose", "implement", "--format", "json"], "web::REQ-001",
                     "他のメンバーの文書がproposedのADRをrequiresするとき型制約でcontextをfailedにする"),
    "MULTI-027-02": ("verify", ".", ["verify", "web::REQ-001", "--format", "json"], "web::REQ-001",
                     "他のメンバーの文書がproposedのADRをrequiresするとき型制約でverifyをfailedにする"),
}
RESULT_FILES = {"MULTI-027-01": "expected/context.json", "MULTI-027-02": "expected/verify.json"}
EMPTY_COVERAGE = {
    **{modality: {key: [] for key in ("total", "addressed", "tested", "unaddressed", "untested")}
       for modality in ("must", "should", "may")},
    "adjacent": [],
}
# 関係・トレースモデル §4の表の`requires`の行。ADRは状態を含む型制約で、`accepted`だけを許す。
REQUIRES_TARGETS = {
    "requirement": {"requirement", "technical"},
    "technical": {"requirement", "technical"},
    "decision": {"requirement", "technical"},
    "task": {"requirement", "technical", "task"},
}
KIND_LABEL = {"requirement": "REQ", "technical": "TECH", "decision": "ADR", "task": "TASK"}
KIND_DIRECTORY = {"requirement": "requirements", "technical": "technical",
                  "decision": "decisions", "task": "tasks"}


def reviewed_inputs():
    """2件のfixtureが共有する入力。`verify`のために、REQ-001のテスト対応とコマンドを置く。"""
    req = (
        "---\nid: REQ-001\ntitle: 認証の基準\nstatus: approved\n"
        "relations:\n  requires: [api::TECH-020]\n"
        "tests:\n  - path: tests/test_login.py\n    covers: [REQ-001:AC-01]\n    command: frontend\n"
        "---\n"
        "\n# REQ-001 認証の基準\n"
        "\n## Intent\n\n認証の規範を定める。\n"
        "\n## Acceptance Criteria\n\n"
        "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n"
        "\n## Verification\n\nwebのtestで確認する。\n"
    )
    tech = (
        "---\nid: TECH-020\ntitle: API側の監査方針\nstatus: approved\n"
        "relations:\n  requires: [ADR-001]\n---\n"
        "\n# TECH-020 API側の監査方針\n"
        "\n## Context\n\n未承認の判断を前提にする方針である。\n"
    )
    return {
        multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config(
            [("web", "apps/web"), ("api", "services/api")]).encode(),
        multi_reference.WEB_CONFIG_PATH: multi_reference.member_config("web", "frontend").encode(),
        multi_reference.API_CONFIG_PATH: multi_reference.plain_config("api").encode(),
        REQ_PATH: req.encode(),
        TECH_PATH: tech.encode(),
        ADR_PATH: PROPOSED_ADR.encode(),
        TEST_PATH: b"def test_login():\n    assert True\n",
    }


def reviewed_manifest(identifier):
    operation, cwd, argv, _, description = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": description,
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": cwd, "argv": list(argv), "env": {}},
        "expect": {"status": "failed", "exitCode": 1, "stdout": "json",
                   "resultFile": RESULT_FILES[identifier], "reportFileCount": 0},
    }


def allowed(source_kind, target):
    """型の表（関係・トレースモデル §4）に照らした`requires`の可否。"""
    if target["kind"] == "decision":
        return target["frontmatter"]["status"] == "accepted"
    return target["kind"] in REQUIRES_TARGETS[source_kind]


def reference_diagnostics(documents, root):
    """参照計算: `root`から`requires`の閉包をたどり、型の表に反する辺ごとに診断を1件導く。

    診断の発生元は関係を宣言した文書（所有ワークスペースのIDと、ワークスペース相対のパス）、`key`は`relations.requires`、
    `evidence`は宣言した参照先を所有ワークスペースの中で書いた形とする。型に反する辺の先は、閉包へ進めない（`skip-edge`）。
    """
    found, seen, frontier = [], {root}, [root]
    while frontier:
        current = frontier.pop(0)
        edges = requires_edges(documents, current)
        found += [diagnostic for diagnostic, _ in edges if diagnostic is not None]
        for diagnostic, target in edges:
            if diagnostic is None and target not in seen:
                seen.add(target)
                frontier.append(target)
    return sorted(found, key=lambda item: (item["source"]["workspaceId"], item["source"]["path"],
                                           item["evidence"]))


def requires_edges(documents, identifier):
    """文書1件の`requires`の辺ごとに(型に反するときの診断または`None`, 修飾した参照先)を返す。"""
    document = documents[identifier]
    edges = []
    for text in document["frontmatter"].get("relations", {}).get("requires", []):
        target = multi_crosscheck.qualify(document["workspaceId"], text)
        if target not in documents:
            raise ValueError("参照先が存在しません。この群は型制約だけを扱います")
        diagnostic = None
        if not allowed(document["kind"], documents[target]):
            diagnostic = {
                "code": "CTX-RELATION-TYPE-001", "severity": "error", "resultStatus": "failed",
                "summary": f"{KIND_LABEL[document['kind']]}から{KIND_LABEL[documents[target]['kind']]}への"
                           "requiresは許可されません",
                "source": {"kind": "file", "workspaceId": document["workspaceId"],
                           "path": f".spec/{KIND_DIRECTORY[document['kind']]}/{document['frontmatter']['id']}.md",
                           "key": "relations.requires"},
                "evidence": text,
            }
        edges.append((diagnostic, target))
    return edges


def reviewed_diagnostics():
    return [{
        "code": "CTX-RELATION-TYPE-001", "severity": "error", "resultStatus": "failed",
        "summary": "TECHからADRへのrequiresは許可されません",
        "source": dict(ORIGIN), "evidence": "ADR-001",
    }]


def failed_context_result():
    """完全解決が成立しないので、ハッシュ値を計算せず空のコンテキスト一式を返す。

    到達ワークスペースは起点ワークスペースの1件だけとする（`MULTI-004-01`と同じ。複合ワークスペース仕様 §6の
    「1件以上」を満たす最小の値）。未解決の強い関係は、返した`CTX-RELATION-TYPE-001`の件数の1件である。
    """
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "failed", "purpose": "implement",
        "workspace": {"id": "web", "path": "apps/web"},
        "roots": ["web::REQ-001"],
        "contextDigest": None,
        "revision": {"commit": COMMIT, "dirty": False},
        "resolution": {"complete": False, "documentCount": 0, "unresolvedStrongRelations": 1,
                       "workspaces": [{"id": "web", "path": "apps/web"}],
                       "crossWorkspaceEdges": []},
        "projection": {"detail": "standard", "expanded": []},
        "documents": [],
        "constraintLedger": {"statements": []},
        "coverage": json.loads(json.dumps(EMPTY_COVERAGE)),
        "durationMs": 0,
        "diagnostics": reviewed_diagnostics(),
    }


def failed_verify_result():
    """型制約の診断は検証対象の`diagnostics`に置き、ハッシュ値、規範文、テスト割当てを持たず、テストを開始しない。"""
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "failed", "scope": "selected",
        "workspace": {"id": "web", "path": "apps/web"},
        "targetResults": [{"target": "web::REQ-001", "status": "failed", "contextDigest": None,
                           "statements": [], "bindingRefs": [], "diagnostics": reviewed_diagnostics()}],
        "revision": {"commit": COMMIT, "dirty": False},
        "commands": [],
        "durationMs": 0,
        "diagnostics": [],
    }


def reviewed_result(identifier):
    return failed_context_result() if CASES[identifier][0] == "context" else failed_verify_result()


def result_diagnostics(result):
    if result["operation"] == "context":
        return result["diagnostics"]
    return result["targetResults"][0]["diagnostics"]


def check_single_cause(identifier, repository, result):
    """原因がちょうど1つであることを、散文ではなく入力と参照計算から確かめる。"""
    _, workspaces, documents = multi_crosscheck.load_workspaces(repository)
    root = CASES[identifier][3]
    # 閉包をたどる参照計算の結果が、期待する診断と一致する。
    if reference_diagnostics(documents, root) != result_diagnostics(result):
        raise ValueError("診断が入力からの参照計算と異なります")
    # 型に反する辺は、corpus全体でも1つだけである。ほかの強い関係は宣言しない。
    violations = [diagnostic for name in documents for diagnostic, _ in requires_edges(documents, name)
                  if diagnostic is not None]
    if len(violations) != 1:
        raise ValueError("型に反する辺は、corpus全体で1件だけである必要があります")
    for name, document in documents.items():
        declared = document["frontmatter"].get("relations", {})
        extra = {key: value for key, value in declared.items() if key != "requires" and value}
        if extra:
            raise ValueError(f"{name}はrequires以外の関係を宣言してはいけません")
    # 診断の発生元は、呼び出し側のワークスペース（起点のworkspace）ではなく、他のメンバーの文書である。
    request = root.partition("::")[0]
    origin = result_diagnostics(result)[0]["source"]["workspaceId"]
    if origin == request or origin not in workspaces:
        raise ValueError("診断の発生元は、呼び出し側と異なる実在のメンバーである必要があります")
    # 起点の文書は、型制約を満たす強い関係と、通るテスト対応を持ち、ほかの原因を持たない。
    req, tech, adr = documents["web::REQ-001"], documents["api::TECH-020"], documents["api::ADR-001"]
    if req["frontmatter"]["status"] != "approved" or tech["frontmatter"]["status"] != "approved":
        raise ValueError("起点とその参照先の文書は`approved`である必要があります")
    if req["frontmatter"]["relations"]["requires"] != ["api::TECH-020"] \
            or tech["frontmatter"]["relations"]["requires"] != ["ADR-001"]:
        raise ValueError("起点は他のメンバーのTECH-020だけを`requires`し、TECH-020は`ADR-001`だけを`requires`する必要があります")
    if adr["frontmatter"]["status"] != "proposed":
        raise ValueError("型制約を満たさない原因は、状態`proposed`のADR-001である必要があります")
    entries = req["frontmatter"].get("tests", [])
    config = read_yaml((repository / multi_reference.WEB_CONFIG_PATH).read_text(encoding="utf-8"))
    if (len(entries) != 1 or entries[0]["covers"] != ["REQ-001:AC-01"]
            or entries[0]["command"] not in config["verify"]["commands"]
            or not (repository / "apps/web" / entries[0]["path"]).is_file()):
        raise ValueError("起点は、定義済みのコマンドと実在のテストを持つテスト対応を1件持つ必要があります")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    frontmatter = json.loads(schema_path(root, "frontmatter").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / RESULT_FILES[identifier]).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for key, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[key].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            inputs = reviewed_inputs()
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[key]
                                                for key, p in files.items()):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-relation-type-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {key: sandbox / key for key in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
                    check_single_cause(identifier, repository, result)
                    _, _, documents = multi_crosscheck.load_workspaces(repository)
                    for document in documents.values():
                        kind = {"requirement": "reqFrontmatter", "technical": "techFrontmatter",
                                "decision": "adrFrontmatter", "task": "taskFrontmatter"}[document["kind"]]
                        Draft202012Validator({"$ref": "#/$defs/" + kind,
                                              "$defs": frontmatter["$defs"]}).validate(document["frontmatter"])
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
