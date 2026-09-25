"""memberの独立性とcatalogの変更を固定するreview済みvector（Core操作は実行しない）。

全体checkは、1つのmemberが非成功でも後続memberの検査を続ける。`MULTI-011`はその独立性、
`MULTI-017`はIDを保ったmember pathの移動、`MULTI-018-01/02`はworkspace IDの変更とmemberの削除を扱う。
後者2つは、base側の管理済みSPECが現在版から消えたことを削除検査で捉えることを固定する。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import multi_crosscheck, multi_reference
from .harness import git, setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
MOVED_WEB_PATH = "frontend/web"
API_MISMATCH_PATH = "services/api/.spec/technical/TECH-020.md"
API_MISMATCH = (
    "---\n"
    "id: TECH-010\n"
    "title: API側の実装方針\n"
    "status: approved\n"
    "---\n"
    "\n"
    "# TECH-010 API側の実装方針\n"
    "\n"
    "## Context\n"
    "\n"
    "file名のIDとFrontmatterのIDが一致しない文書である。\n"
)
FILE_NAME = {
    "code": "SPEC-FILE-NAME-001", "severity": "error", "resultStatus": "failed",
    "summary": "file名IDとFrontmatter IDが一致しません",
    "source": {"kind": "file", "workspaceId": "api", "path": ".spec/technical/TECH-020.md"},
}
DELETED = {
    "code": "SPEC-STATE-TRANSITION-001", "severity": "error", "resultStatus": "failed",
    "summary": "管理済みSPECが削除されています",
    # 基準版のworkspace IDとそのworkspace root相対pathで指す。現在版にこのworkspaceはない。
    "source": {"kind": "file", "workspaceId": "web", "path": ".spec/technical/TECH-010.md"},
}
CASES = {
    "MULTI-011": "1つのmemberの文書が非成功でも後続memberの検査を続ける",
    "MULTI-017": "IDを保ったmember pathの移動を同一workspaceとして扱う",
    "MULTI-018-01": "memberのworkspace ID変更を管理済みSPECの削除として検査する",
    "MULTI-018-02": "memberの削除を管理済みSPECの削除として検査する",
}


def reviewed_inputs(identifier):
    """repo/の入力とchanges/の差替えfileを返す。基準版はrepo/、現在版はoperationsで作る。"""
    files = dict(multi_reference.reviewed_inputs())
    changes = {}
    if identifier == "MULTI-011":
        # apiの文書を、file名IDとFrontmatter IDが一致しない1件だけに置き換える。
        del files[multi_reference.API_TECH_PATH]
        del files["services/api/src/session.py"]
        del files["services/api/tests/test_session.py"]
        files[API_MISMATCH_PATH] = API_MISMATCH.encode()
    if identifier == "MULTI-017":
        changes["bitz.yaml"] = multi_reference.root_config(
            [("web", MOVED_WEB_PATH), ("api", "services/api")]).encode()
    if identifier == "MULTI-018-01":
        changes["bitz.yaml"] = multi_reference.root_config(
            [("webui", "apps/web"), ("api", "services/api")]).encode()
        changes["web.yaml"] = multi_reference.member_config("webui", "frontend").encode()
    if identifier == "MULTI-018-02":
        changes["bitz.yaml"] = multi_reference.root_config([("api", "services/api")]).encode()
    return {"files": files, "changes": changes}


def operations(identifier):
    if identifier == "MULTI-017":
        return [{"op": "rename", "from": "apps/web", "to": MOVED_WEB_PATH},
                {"op": "update", "path": multi_reference.ROOT_CONFIG_PATH, "source": "changes/bitz.yaml"}]
    if identifier == "MULTI-018-01":
        return [{"op": "update", "path": multi_reference.ROOT_CONFIG_PATH, "source": "changes/bitz.yaml"},
                {"op": "update", "path": multi_reference.WEB_CONFIG_PATH, "source": "changes/web.yaml"}]
    if identifier == "MULTI-018-02":
        return [{"op": "delete", "path": "apps/web"},
                {"op": "update", "path": multi_reference.ROOT_CONFIG_PATH, "source": "changes/bitz.yaml"}]
    return []


def reviewed_manifest(identifier):
    return {
        "fixtureId": identifier,
        "description": CASES[identifier],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]},
                  "operations": operations(identifier)},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["check", "--all-workspaces", "--base", "HEAD", "--format", "json"], "env": {}},
        "expect": {"status": "passed" if identifier == "MULTI-017" else "failed",
                   "exitCode": 0 if identifier == "MULTI-017" else 1,
                   "stdout": "json", "resultFile": "expected/check.json", "reportFileCount": 0},
    }


def workspace_entry(workspace_id, path, status="passed", documents=1, statements=0, diagnostics=()):
    return {"id": workspace_id, "path": path, "status": status,
            "checkedDocumentCount": documents, "checkedStatementCount": statements,
            "durationMs": 0, "diagnostics": [dict(entry) for entry in diagnostics]}


def reviewed_result(identifier):
    if identifier == "MULTI-011":
        workspaces = [
            workspace_entry("platform", ".", documents=1, statements=2),
            # file名IDと一致しない文書はskip-documentとなり、完全検査した文書数へ数えない
            # （check仕様 §9・Diagnostic registry。SINGLE-014と同じ扱い）。後続のwebは影響を受けない。
            workspace_entry("api", "services/api", status="failed", documents=0, diagnostics=[FILE_NAME]),
            workspace_entry("web", "apps/web"),
        ]
        diagnostics = []
    elif identifier == "MULTI-017":
        workspaces = [
            workspace_entry("platform", ".", documents=1, statements=2),
            workspace_entry("api", "services/api"),
            workspace_entry("web", MOVED_WEB_PATH),
        ]
        diagnostics = []
    elif identifier == "MULTI-018-01":
        workspaces = [
            workspace_entry("platform", ".", documents=1, statements=2),
            workspace_entry("api", "services/api"),
            workspace_entry("webui", "apps/web"),
        ]
        diagnostics = [dict(DELETED)]
    else:
        workspaces = [
            workspace_entry("platform", ".", documents=1, statements=2),
            workspace_entry("api", "services/api"),
        ]
        diagnostics = [dict(DELETED)]
    return {
        "schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces",
        "status": "passed" if identifier == "MULTI-017" else "failed",
        "multiWorkspace": {"id": "platform", "path": "."},
        "workspaces": workspaces,
        "revision": {"base": COMMIT, "commit": COMMIT,
                     "dirty": identifier != "MULTI-011"},
        "durationMs": 0,
        "diagnostics": diagnostics,
    }


def check_catalog_change(identifier, repository):
    """基準版と現在版のcatalogを、散文ではなくGitのblobと作業treeから確かめる。"""
    base_config = git(repository, "show", f"HEAD:{multi_reference.ROOT_CONFIG_PATH}").decode()
    base = multi_crosscheck.read_yaml(base_config)["multiWorkspace"]["members"]
    base_members = {entry["id"]: entry["path"] for entry in base}
    _, current = multi_crosscheck.catalog(repository)
    current_members = dict(current)
    if identifier == "MULTI-011":
        if base_members != current_members:
            raise ValueError("member独立のcaseはcatalogを変えない")
        frontmatter, _ = multi_crosscheck.split_document(
            (repository / API_MISMATCH_PATH).read_text(encoding="utf-8"))
        if frontmatter["id"] == Path(API_MISMATCH_PATH).stem:
            raise ValueError("file名IDとFrontmatter IDが一致しています")
    if identifier == "MULTI-017":
        if set(base_members) != set(current_members):
            raise ValueError("path移動のcaseはworkspace IDを変えない")
        if base_members["web"] == current_members["web"]:
            raise ValueError("path移動のcaseはmember pathを変える必要があります")
        if not (repository / MOVED_WEB_PATH / ".spec/bitz.yaml").is_file():
            raise ValueError("移動先にmemberの設定がありません")
    if identifier == "MULTI-018-01":
        if set(base_members) == set(current_members) or set(base_members.values()) != set(current_members.values()):
            raise ValueError("ID変更のcaseは、pathを保ったままIDだけを変える必要があります")
    if identifier == "MULTI-018-02":
        if set(current_members) >= set(base_members):
            raise ValueError("member削除のcaseは、catalogからmemberを外す必要があります")
        if (repository / "apps/web").exists():
            raise ValueError("member削除のcaseは、memberのtreeも削除する必要があります")
    if identifier in {"MULTI-018-01", "MULTI-018-02"}:
        # 基準版には削除検査の対象になる管理済みSPECがある。
        if git(repository, "cat-file", "-t", f"HEAD:{multi_reference.WEB_TECH_PATH}").decode().strip() != "blob":
            raise ValueError("基準版にwebの管理済みSPECがありません")


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
            result = json.loads((fixture / "expected/check.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件が審査済み期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果が審査済み期待値と異なります")
            reviewed = reviewed_inputs(identifier)
            entries = {}
            for directory in ("repo", "changes"):
                for path in (fixture / directory).rglob("*"):
                    if path.is_symlink():
                        raise ValueError("この群はsymlinkを入力に持ちません")
                    if path.is_file():
                        entries[(directory, path.relative_to(fixture / directory).as_posix())] = path.read_bytes()
            expected = {**{("repo", name): data for name, data in reviewed["files"].items()},
                        **{("changes", name): data for name, data in reviewed["changes"].items()}}
            if entries != expected:
                raise ValueError("入力が審査済みcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-member-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
                    check_catalog_change(identifier, repository)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
