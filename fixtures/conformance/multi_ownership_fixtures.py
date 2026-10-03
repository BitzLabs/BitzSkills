"""複合ワークスペースの所有境界とTASK境界を固定するレビュー済みの入力と期待値（Coreの公開操作は実行しない）。

メンバーが所有できるのは自身のルート配下だけであり、シンボリックリンクは同じ所有領域内へ解決する場合だけ許される
（[複合ワークスペース仕様 §5.1](../../docs/03.詳細設計/02_仕様文書モデル/05_複合ワークスペース仕様.md)）。
`MULTI-008`はシンボリックリンクで別のメンバーを所有する宣言、`MULTI-009`は字句のセグメントの境界、`MULTI-010`は
基準版と現在版の双方で行うシンボリックリンクの所有の判定を扱う。
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import multi_reference
from .harness import git, setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
API_CODE_PATH = "services/api/src/session.py"
WEB_TECH_PATH = "apps/web/.spec/technical/TECH-010.md"
WEB_TASK_PATH = "apps/web/.spec/tasks/TASK-010.md"
SHARED_LINK = "apps/web/src/shared.py"
CHANGED_LINK = "apps/web/src/link"
OUTSIDE_PATH = "apps/web/src2/outside.py"
INSIDE_PATH = "apps/web/src/inside.py"
# メンバーのルートから別のメンバーのコードへ出るリンク文字列。セグメントの境界ではなく実際のパスの解決で判定する。
ESCAPING_TARGET = "../../../services/api/src/session.py"
LOCAL_TARGET = "inside.py"
WEB_TECH = (
    "---\n"
    "id: TECH-010\n"
    "title: Web側の共有実装方針\n"
    "status: approved\n"
    "relations:\n"
    "  refines: [platform::REQ-001:AC-01]\n"
    "implements: [src/shared.py]\n"
    "---\n"
    "\n"
    "# TECH-010 Web側の共有実装方針\n"
    "\n"
    "## Context\n"
    "\n"
    "共有実装をwebから参照する方針を記述する。\n"
)
WEB_TASK = (
    "---\n"
    "id: TASK-010\n"
    "title: 変更境界の検査\n"
    "status: open\n"
    "changes: [src/]\n"
    "---\n"
    "\n"
    "# TASK-010 変更境界の検査\n"
    "\n"
    "## Objective\n"
    "\n"
    "webの変更境界を確認する。\n"
)
OWNERSHIP_IMPLEMENTS = {
    "code": "SPEC-MULTI-OWNERSHIP-001", "severity": "error", "resultStatus": "failed",
    "summary": "src/shared.pyの解決先がwebの所有範囲外です",
    "source": {"kind": "file", "workspaceId": "web", "path": ".spec/technical/TECH-010.md",
               "key": "implements"},
}
TASK_BOUNDARY = {
    "code": "SPEC-TASK-BOUNDARY-001", "severity": "error", "resultStatus": "failed",
    "summary": "src2/outside.pyはweb::TASK-010の許可変更path外です",
    "source": {"kind": "file", "workspaceId": "web", "path": "src2/outside.py"},
}
OWNERSHIP_BASE_LINK = {
    "code": "SPEC-MULTI-OWNERSHIP-001", "severity": "error", "resultStatus": "failed",
    "summary": "src/linkの基準版のsymlinkがwebの所有範囲外を指します",
    "source": {"kind": "file", "workspaceId": "web", "path": "src/link"},
}
# id: (引数列の残り, 状態, 検査文書数, 検査規範文数, 診断, 説明)
CASES = {
    "MULTI-008": (["check", "--all-workspaces"], "failed", None, None, OWNERSHIP_IMPLEMENTS,
                  "symlinkで別memberのcodeを所有する宣言を拒否する"),
    "MULTI-009": (["check", "web::TASK-010"], "failed", 1, 0, TASK_BOUNDARY,
                  "TASK changesのsegment境界をsrc2へ広げない"),
    "MULTI-010": (["check", "web::TASK-010"], "failed", 1, 0, OWNERSHIP_BASE_LINK,
                  "基準版と現在版の双方でsymlinkの所有を判定する"),
}


def reviewed_inputs(identifier):
    """repo/とchanges/の全入力。シンボリックリンクはリンク文字列で返し、リンク先を解決しない。"""
    files = {
        multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config(
            [("web", "apps/web"), ("api", "services/api")]).encode(),
        multi_reference.ROOT_REQ_PATH: (multi_reference.REQ_HEAD + "\n" + multi_reference.REQ_BODY).encode(),
        multi_reference.WEB_CONFIG_PATH: multi_reference.plain_config("web").encode(),
        multi_reference.API_CONFIG_PATH: multi_reference.plain_config("api").encode(),
        API_CODE_PATH: b"def open_session():\n    return True\n",
    }
    links, changes, change_links = {}, {}, {}
    if identifier == "MULTI-008":
        files[WEB_TECH_PATH] = WEB_TECH.encode()
        links[SHARED_LINK] = ESCAPING_TARGET
    else:
        files[WEB_TASK_PATH] = WEB_TASK.encode()
        files[INSIDE_PATH] = b"# allowed path\n"
    if identifier == "MULTI-009":
        files[OUTSIDE_PATH] = b"# before\n"
        changes["outside.py"] = b"# after\n"
    if identifier == "MULTI-010":
        # 基準版では別のメンバーを指し、現在版ではweb内へ向け直す。現在版だけを見ると不適合を見落とす。
        links[CHANGED_LINK] = ESCAPING_TARGET
        change_links["link"] = LOCAL_TARGET
    return {"files": files, "links": links, "changes": changes, "changeLinks": change_links}


def reviewed_manifest(identifier):
    argv, status, _documents, _statements, _diagnostic, description = CASES[identifier]
    operations = []
    if identifier == "MULTI-009":
        operations = [{"op": "update", "path": OUTSIDE_PATH, "source": "changes/outside.py"}]
    if identifier == "MULTI-010":
        operations = [{"op": "update", "path": CHANGED_LINK, "source": "changes/link"}]
    return {
        "fixtureId": identifier,
        "description": description,
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": operations},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": [*argv, "--base", "HEAD", "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": 1, "stdout": "json",
                   "resultFile": "expected/check.json", "reportFileCount": 0},
    }


def reviewed_result(identifier):
    _argv, status, documents, statements, diagnostic, _description = CASES[identifier]
    dirty = identifier != "MULTI-008"
    if identifier == "MULTI-008":
        return {
            "schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": status,
            "multiWorkspace": {"id": "platform", "path": "."},
            "workspaces": [
                {"id": "platform", "path": ".", "status": "passed", "checkedDocumentCount": 1,
                 "checkedStatementCount": 2, "durationMs": 0, "diagnostics": []},
                {"id": "api", "path": "services/api", "status": "passed", "checkedDocumentCount": 0,
                 "checkedStatementCount": 0, "durationMs": 0, "diagnostics": []},
                {"id": "web", "path": "apps/web", "status": "failed", "checkedDocumentCount": 1,
                 "checkedStatementCount": 0, "durationMs": 0, "diagnostics": [dict(diagnostic)]},
            ],
            "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
            "durationMs": 0,
            "diagnostics": [],
        }
    return {
        "schemaVersion": "1.0", "operation": "check", "scope": "selected", "status": status,
        "workspace": {"id": "web", "path": "apps/web"},
        "revision": {"base": COMMIT, "commit": COMMIT, "dirty": dirty},
        "checkedDocumentCount": documents,
        "checkedStatementCount": statements,
        "durationMs": 0,
        "diagnostics": [dict(diagnostic)],
    }


def check_boundary_inputs(identifier, repository):
    """境界の条件を、散文ではなく準備手順の後の木構造とGitのブロブから確かめる。"""
    reviewed = reviewed_inputs(identifier)
    if identifier == "MULTI-008":
        link = repository / SHARED_LINK
        if not link.is_symlink() or os.readlink(link) != ESCAPING_TARGET:
            raise ValueError("所有境界のケースは、別メンバーへ出るシンボリックリンクが必要です")
        resolved = link.resolve()
        if not resolved.is_relative_to(repository / "services/api"):
            raise ValueError("シンボリックリンクの解決先が別メンバーの中にありません")
        if (repository / "apps/web/.spec/tasks").exists():
            raise ValueError("所有境界のケースはTASKを持たず、TASK境界の診断コードを起こさない")
    if identifier == "MULTI-009":
        # 字句のセグメントの境界。src/はsrc2/のファイルを許可しない。
        if not (repository / OUTSIDE_PATH).is_file() or not (repository / INSIDE_PATH).is_file():
            raise ValueError("セグメント境界のケースは、`src/`と`src2/`の両方のファイルが必要です")
        if git(repository, "show", f"HEAD:{OUTSIDE_PATH}") == (repository / OUTSIDE_PATH).read_bytes():
            raise ValueError("セグメント境界のケースは、`src2/`のファイルが基準版から変わっている必要があります")
    if identifier == "MULTI-010":
        link = repository / CHANGED_LINK
        if not link.is_symlink() or os.readlink(link) != LOCAL_TARGET:
            raise ValueError("現在版のシンボリックリンクは`web`内を指す必要があります")
        base = git(repository, "cat-file", "-p", f"HEAD:{CHANGED_LINK}").decode()
        if base != ESCAPING_TARGET:
            raise ValueError("基準版のシンボリックリンクは別メンバーを指す必要があります")
        if git(repository, "ls-tree", "HEAD", CHANGED_LINK).decode().split()[0] != "120000":
            raise ValueError("基準版のエントリはシンボリックリンクとして記録されている必要があります")
    actual_files = {p.relative_to(repository).as_posix(): p.read_bytes()
                    for p in repository.rglob("*")
                    if p.is_file() and not p.is_symlink() and ".git" not in p.relative_to(repository).parts}
    expected_files = dict(reviewed["files"])
    if identifier == "MULTI-009":
        expected_files[OUTSIDE_PATH] = reviewed["changes"]["outside.py"]
    if actual_files != expected_files:
        raise ValueError("作業ツリーがレビュー済みの入力と異なります")


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
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            reviewed = reviewed_inputs(identifier)
            entries = {}
            for directory in ("repo", "changes"):
                for path in (fixture / directory).rglob("*"):
                    if path.is_symlink():
                        entries[path.relative_to(fixture / directory).as_posix()] = (directory, "link",
                                                                                     os.readlink(path))
                    elif path.is_file():
                        entries[path.relative_to(fixture / directory).as_posix()] = (directory, "file",
                                                                                     path.read_bytes())
            expected = {**{name: ("repo", "file", data) for name, data in reviewed["files"].items()},
                        **{name: ("repo", "link", target) for name, target in reviewed["links"].items()},
                        **{name: ("changes", "file", data) for name, data in reviewed["changes"].items()},
                        **{name: ("changes", "link", target) for name, target in reviewed["changeLinks"].items()}}
            if entries != expected:
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-ownership-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
                    check_boundary_inputs(identifier, repository)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
