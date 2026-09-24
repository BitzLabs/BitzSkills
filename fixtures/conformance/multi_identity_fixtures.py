"""複合workspaceの識別子解決を固定するreview済みvector（Core操作は実行しない）。

同じcorpusの3変種で、修飾IDの4つの結末を1件ずつ切り分ける。`MULTI-001`は別workspaceの同じlocal IDが
衝突しないこと、`MULTI-003`は別workspaceにだけあるtargetの非修飾参照、`MULTI-004-01/02`は存在workspaceの
不在target、`MULTI-025-01/02`は存在workspaceの不在起点である。後者2つは、未知`--workspace`の終了コード4と
異なり、操作結果を返すことを示す。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import multi_crosscheck, multi_reference
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
WEB_TECH_RESULT_PATH = ".spec/technical/TECH-010.md"
MULTI_REF = {
    "code": "SPEC-MULTI-REF-001", "severity": "error", "resultStatus": "failed",
    "summary": "非修飾の参照先が別workspaceにだけ存在します",
    "source": {"kind": "file", "workspaceId": "web", "path": WEB_TECH_RESULT_PATH,
               "key": "relations.refines"},
}
RELATION_MISSING = {
    "code": "SPEC-RELATION-MISSING-001", "severity": "error", "resultStatus": "failed",
    "summary": "strong relationの参照先が存在しません",
    "source": {"kind": "file", "workspaceId": "web", "path": WEB_TECH_RESULT_PATH,
               "key": "relations.requires"},
}
ROOT_MISSING = {
    "code": "CTX-ROOT-MISSING-001", "severity": "error", "resultStatus": "failed",
    "summary": "起点api::REQ-009が存在しません",
    "source": {"kind": "invocation", "argument": "api::REQ-009"},
}
# id: (変種, argvの残り, status, 終了コード, 説明)
CASES = {
    "MULTI-001": ("golden", ["check", "--all-workspaces", "--base", "HEAD", "--format", "json"],
                  "passed", 0, "別workspaceの同じlocal IDを修飾IDで衝突させない"),
    "MULTI-003": ("unqualified", ["check", "--all-workspaces", "--base", "HEAD", "--format", "json"],
                  "failed", 1, "別workspaceにだけあるtargetの非修飾参照を拒否する"),
    "MULTI-004-01": ("missing-target",
                     ["context", "web::TECH-010", "--purpose", "verify", "--format", "json"],
                     "failed", 1, "context時に存在workspace内のtarget不在を関係不在として返す"),
    "MULTI-004-02": ("missing-target",
                     ["check", "web::TECH-010", "--base", "HEAD", "--format", "json"],
                     "failed", 1, "check時に存在workspace内のtarget不在を関係不在として返す"),
    "MULTI-025-01": ("golden", ["check", "api::REQ-009", "--base", "HEAD", "--format", "json"],
                     "failed", 1, "存在workspaceの不在修飾起点をcheckの結果として返す"),
    "MULTI-025-02": ("golden", ["verify", "api::REQ-009", "--format", "json"],
                     "failed", 1, "存在workspaceの不在修飾起点をverifyのtarget結果として返す"),
}
RESULT_FILES = {
    "MULTI-001": "expected/check.json", "MULTI-003": "expected/check.json",
    "MULTI-004-01": "expected/context.json", "MULTI-004-02": "expected/check.json",
    "MULTI-025-01": "expected/check.json", "MULTI-025-02": "expected/verify.json",
}
EMPTY_COVERAGE = {
    **{modality: {key: [] for key in ("total", "addressed", "tested", "unaddressed", "untested")}
       for modality in ("must", "should", "may")},
    "adjacent": [],
}


def reviewed_manifest(identifier):
    variant, argv, status, exit_code, description = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": description,
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": list(argv), "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": RESULT_FILES[identifier], "reportFileCount": 0},
    }


def workspace_entry(workspace_id, path, status, documents, statements, diagnostics):
    return {"id": workspace_id, "path": path, "status": status,
            "checkedDocumentCount": documents, "checkedStatementCount": statements,
            "durationMs": 0, "diagnostics": diagnostics}


def all_workspaces_result(identifier):
    """`check --all-workspaces`はcatalogの全SPECを完全検査する。件数はworkspaceごとの実数である。"""
    failing = identifier == "MULTI-003"
    return {
        "schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces",
        "status": "failed" if failing else "passed",
        "multiWorkspace": {"id": "platform", "path": "."},
        "workspaces": [
            workspace_entry("platform", ".", "passed", 1, 2, []),
            workspace_entry("api", "services/api", "passed", 1, 0, []),
            workspace_entry("web", "apps/web", "failed" if failing else "passed", 1, 0,
                            [dict(MULTI_REF)] if failing else []),
        ],
        "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
        "durationMs": 0,
        "diagnostics": [],
    }


def selected_check_result(identifier):
    """workspace単独checkは、複合workspace内でも実際のworkspace IDとroot相対pathを返す。"""
    if identifier == "MULTI-004-02":
        workspace = {"id": "web", "path": "apps/web"}
        # 横断閉包のplatform::REQ-001も完全検査するため、2文書2句を数える。
        documents, statements, diagnostics = 2, 2, [dict(RELATION_MISSING)]
    else:
        workspace = {"id": "api", "path": "services/api"}
        documents, statements, diagnostics = 0, 0, [dict(ROOT_MISSING)]
    return {
        "schemaVersion": "1.0", "operation": "check", "scope": "selected", "status": "failed",
        "workspace": workspace,
        "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
        "checkedDocumentCount": documents,
        "checkedStatementCount": statements,
        "durationMs": 0,
        "diagnostics": diagnostics,
    }


def failed_context_result():
    """完全解決が成立しないので、Digestを計算せず空のBundleを返す。到達workspaceはrequestの1件。"""
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "failed", "purpose": "verify",
        "workspace": {"id": "web", "path": "apps/web"},
        "roots": ["web::TECH-010"],
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
        "diagnostics": [dict(RELATION_MISSING)],
    }


def failed_verify_result():
    """不在起点はtargetのDiagnosticとして返し、commandを実行しない。"""
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "failed", "scope": "selected",
        "workspace": {"id": "api", "path": "services/api"},
        "targetResults": [{"target": "api::REQ-009", "status": "failed", "contextDigest": None,
                           "statements": [], "bindingRefs": [], "diagnostics": [dict(ROOT_MISSING)]}],
        "revision": {"commit": COMMIT, "dirty": False},
        "commands": [],
        "durationMs": 0,
        "diagnostics": [],
    }


def reviewed_result(identifier):
    if identifier in {"MULTI-001", "MULTI-003"}:
        return all_workspaces_result(identifier)
    if identifier == "MULTI-004-01":
        return failed_context_result()
    if identifier == "MULTI-025-02":
        return failed_verify_result()
    return selected_check_result(identifier)


def check_single_cause(identifier, repository):
    """変種が加える原因がちょうど1つであることを、散文ではなく入力から確かめる。"""
    _, workspaces, documents = multi_crosscheck.load_workspaces(repository)
    known = set(documents)
    variant = CASES[identifier][0]
    web = documents["web::TECH-010"]
    declared = web["frontmatter"].get("relations", {})
    if variant == "golden":
        if "api::REQ-009" in known or set(declared) != {"refines"}:
            raise ValueError("goldenの変種は解決できるrelationだけを持つ必要があります")
    elif variant == "unqualified":
        if declared != {"refines": ["REQ-001"]} or "web::REQ-001" in known:
            raise ValueError("非修飾の変種はweb内に解決先を持ってはいけません")
        if web["frontmatter"].get("tests") or web["frontmatter"].get("implements"):
            raise ValueError("非修飾の変種は2つ目の原因を持ってはいけません")
    else:
        if declared.get("requires") != ["api::TECH-999"] or "api::TECH-999" in known:
            raise ValueError("不在targetの変種は、存在workspaceの不在文書を指す必要があります")
        if "api" not in workspaces:
            raise ValueError("不在targetの変種は、存在するworkspaceを修飾に使う必要があります")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
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
                raise ValueError("起動条件が審査済み期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果が審査済み期待値と異なります")
            inputs = multi_reference.reviewed_inputs(CASES[identifier][0])
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[key]
                                                for key, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-identity-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {key: sandbox / key for key in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
                    check_single_cause(identifier, repository)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
