"""結果外形の識別と複合workspace化の移行を固定するreview済みvector（Core操作は実行しない）。

`runner: consumer`と`runner: migration`は、Core配布物のmodule `bitz.compat`を
`python -m bitz.compat <runner> <argv...>`として起動し、`{"outcome": ...}`だけを返す（ADR-046）。
`MULTI-023-01/02/03`はdual-read consumerの排他的外形、`MULTI-024-01/02/03`は複合workspace化、
完全rollback、部分rollbackの扱いを固定する。migrationのcase名と引数は本fixtureで確定する。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import multi_reference
from .harness import git, setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
RESULT_PATH = "result.json"
SINGLE_CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "1.0"\n'
REQ_PATH = ".spec/requirements/REQ-001.md"
SINGLE_TECH_PATH = ".spec/technical/TECH-010.md"
MEMBER_TECH_PATH = "apps/web/.spec/technical/TECH-010.md"
TEST_PATH = "tests/test_login.py"
MEMBER_TEST_PATH = "apps/web/tests/test_login.py"
# id: (runner, argv, outcome, 終了コード, 説明)
CASES = {
    "MULTI-023-01": ("consumer", ["result-shape", RESULT_PATH], "accepted", 0,
                     "単一workspaceの結果を単独外形として受理する"),
    "MULTI-023-02": ("consumer", ["result-shape", RESULT_PATH], "accepted", 0,
                     "複合workspaceの結果を全体外形として受理する"),
    "MULTI-023-03": ("consumer", ["result-shape", RESULT_PATH], "rejected", 1,
                     "単一と複合workspaceのfieldが混在する結果を拒否する"),
    "MULTI-024-01": ("migration", ["to-multi-workspace"], "passed", 0,
                     "複合workspace化を1つの原子的な変更集合として適用する"),
    "MULTI-024-02": ("migration", ["rollback"], "passed", 0,
                     "複合workspace化を単一workspaceへ完全に戻す"),
    "MULTI-024-03": ("migration", ["rollback"], "rejected", 1,
                     "修飾参照が残る部分rollbackを拒否する"),
}


def single_result():
    """単一workspaceの結果。`workspace`を持ち、複合workspace固有fieldを持たない。"""
    return {
        "schemaVersion": "1.0", "operation": "check", "scope": "full", "status": "passed",
        "workspace": {"id": "root", "path": "."},
        "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
        "checkedDocumentCount": 1, "checkedStatementCount": 1,
        "durationMs": 0, "diagnostics": [],
    }


def multi_result():
    """複合workspaceの全体結果。`multiWorkspace`と`workspaces`を持ち、`workspace`を持たない。"""
    return {
        "schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": "passed",
        "multiWorkspace": {"id": "platform", "path": "."},
        "workspaces": [
            {"id": "platform", "path": ".", "status": "passed", "checkedDocumentCount": 1,
             "checkedStatementCount": 1, "durationMs": 0, "diagnostics": []},
            {"id": "web", "path": "apps/web", "status": "passed", "checkedDocumentCount": 1,
             "checkedStatementCount": 0, "durationMs": 0, "diagnostics": []},
        ],
        "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
        "durationMs": 0, "diagnostics": [],
    }


def mixed_result():
    """両方の外形を混ぜた結果。consumerはこれをSchema errorとして拒否する。"""
    return {**multi_result(), "workspace": {"id": "platform", "path": "."}}


def requirement():
    return (
        "---\nid: REQ-001\ntitle: 認証の基準\nstatus: approved\n---\n"
        "\n# REQ-001 認証の基準\n"
        "\n## Intent\n\n移行の前後で同じ規範を保つ。\n"
        "\n## Acceptance Criteria\n"
        "\n- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n"
        "\n## Verification\n\n移行後もtestで確認する。\n"
    )


def technical(refines, covers, test_path):
    return (
        f"---\nid: TECH-010\ntitle: 認証の実装方針\nstatus: approved\n"
        f"relations:\n  refines: [{refines}]\n"
        f"tests:\n  - path: {test_path}\n    covers: [{covers}]\n    command: default\n---\n"
        "\n# TECH-010 認証の実装方針\n"
        "\n## Context\n\n移行の対象になる実装方針である。\n"
    )


def single_tree():
    """複合workspace化する前の単一workspace。IDを明示せず、参照はすべて非修飾である。"""
    return {
        ".spec/bitz.yaml": (SINGLE_CONFIG + 'verify:\n  commands:\n    default:\n'
                            '      argv: ["/bin/true", "{tests}"]\n      cwd: .\n').encode(),
        REQ_PATH: requirement().encode(),
        SINGLE_TECH_PATH: technical("REQ-001:AC-01", "REQ-001:AC-01", TEST_PATH).encode(),
        TEST_PATH: b"def test_login():\n    assert True\n",
    }


def multi_tree():
    """複合workspace化した後のtree。catalog、member設定、修飾参照を同時に持つ。"""
    return {
        multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config([("web", "apps/web")]).encode(),
        REQ_PATH: requirement().encode(),
        multi_reference.WEB_CONFIG_PATH: multi_reference.member_config("web", "default").encode(),
        MEMBER_TECH_PATH: technical("platform::REQ-001:AC-01", "platform::REQ-001:AC-01",
                                    "tests/test_login.py").encode(),
        MEMBER_TEST_PATH: b"def test_login():\n    assert True\n",
    }


def reviewed_inputs(identifier):
    """repo/（基準版のtree）とchanges/（現在版へ差し替えるfile）を返す。"""
    if identifier.startswith("MULTI-023"):
        payload = {"MULTI-023-01": single_result(), "MULTI-023-02": multi_result(),
                   "MULTI-023-03": mixed_result()}[identifier]
        return {"files": {".spec/bitz.yaml": SINGLE_CONFIG.encode(),
                          RESULT_PATH: (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()},
                "changes": {}}
    if identifier == "MULTI-024-01":
        return {"files": single_tree(),
                "changes": {"root.yaml": multi_tree()[multi_reference.ROOT_CONFIG_PATH],
                            "member.yaml": multi_tree()[multi_reference.WEB_CONFIG_PATH],
                            "tech.md": multi_tree()[MEMBER_TECH_PATH]}}
    # rollbackの2件は、複合workspaceを基準版にして単一workspaceへ戻す。
    changes = {"root.yaml": single_tree()[".spec/bitz.yaml"],
               "tech.md": single_tree()[SINGLE_TECH_PATH]}
    if identifier == "MULTI-024-03":
        # 部分rollback: catalogは戻すが、文書の修飾参照が残る。
        changes["tech.md"] = technical("platform::REQ-001:AC-01", "platform::REQ-001:AC-01",
                                       TEST_PATH).encode()
    return {"files": multi_tree(), "changes": changes}


def operations(identifier):
    if identifier.startswith("MULTI-023"):
        return []
    if identifier == "MULTI-024-01":
        # catalog、member設定、SPECの移動、修飾参照を1つの変更集合として適用する。
        return [
            {"op": "update", "path": multi_reference.ROOT_CONFIG_PATH, "source": "changes/root.yaml"},
            {"op": "create", "path": multi_reference.WEB_CONFIG_PATH, "source": "changes/member.yaml"},
            {"op": "rename", "from": SINGLE_TECH_PATH, "to": MEMBER_TECH_PATH},
            {"op": "update", "path": MEMBER_TECH_PATH, "source": "changes/tech.md"},
            {"op": "rename", "from": TEST_PATH, "to": MEMBER_TEST_PATH},
            {"op": "stage", "paths": ["."]},
        ]
    return [
        {"op": "update", "path": multi_reference.ROOT_CONFIG_PATH, "source": "changes/root.yaml"},
        {"op": "rename", "from": MEMBER_TECH_PATH, "to": SINGLE_TECH_PATH},
        {"op": "update", "path": SINGLE_TECH_PATH, "source": "changes/tech.md"},
        {"op": "rename", "from": MEMBER_TEST_PATH, "to": TEST_PATH},
        {"op": "delete", "path": "apps/web/.spec"},
        {"op": "stage", "paths": ["."]},
    ]


def reviewed_manifest(identifier):
    runner, argv, outcome, exit_code, description = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": description,
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]},
                  "operations": operations(identifier)},
        "invocation": {"runner": runner, "cwd": ".", "argv": list(argv), "env": {}},
        "expect": {"outcome": outcome, "exitCode": exit_code, "stdout": "json",
                   "resultFile": f"expected/{runner}.json", "reportFileCount": 0},
    }


def reviewed_result(identifier):
    return {"outcome": CASES[identifier][2]}


def check_shape(identifier, repository, result_validator):
    """外形と移行の条件を、散文ではなくsetup後のtreeとGitのblobから確かめる。"""
    if identifier.startswith("MULTI-023"):
        payload = json.loads((repository / RESULT_PATH).read_text(encoding="utf-8"))
        single = "workspace" in payload
        federated = "multiWorkspace" in payload and "workspaces" in payload
        expected = CASES[identifier][2]
        if expected == "accepted" and single == federated:
            raise ValueError("受理するcaseは、単独と全体のどちらか一方の外形でなければなりません")
        if expected == "rejected" and not (single and federated):
            raise ValueError("拒否するcaseは、両方の外形を混ぜた結果でなければなりません")
        errors = list(result_validator.iter_errors(payload))
        if expected == "accepted" and errors:
            raise ValueError("受理するcaseの結果は公開Schemaへ適合しなければなりません")
        if expected == "rejected" and not errors:
            raise ValueError("拒否するcaseの結果は公開Schemaへ適合してはいけません")
        return
    base = {path.decode() for path in git(repository, "ls-tree", "-r", "--name-only", "-z", "HEAD").split(b"\0") if path}
    current = {p.relative_to(repository).as_posix() for p in repository.rglob("*")
               if p.is_file() and ".git" not in p.relative_to(repository).parts}
    root_config = (repository / multi_reference.ROOT_CONFIG_PATH).read_text(encoding="utf-8")
    technical_text = (repository / (MEMBER_TECH_PATH if identifier == "MULTI-024-01"
                                    else SINGLE_TECH_PATH)).read_text(encoding="utf-8")
    if identifier == "MULTI-024-01":
        if multi_reference.ROOT_CONFIG_PATH not in base or "multiWorkspace" in git(
                repository, "show", f"HEAD:{multi_reference.ROOT_CONFIG_PATH}").decode():
            raise ValueError("複合workspace化のcaseは、単一workspaceの基準版が必要です")
        if "multiWorkspace" not in root_config or "platform::" not in technical_text:
            raise ValueError("複合workspace化は、catalogと修飾参照を同時に持つ必要があります")
        if MEMBER_TECH_PATH not in current or SINGLE_TECH_PATH in current:
            raise ValueError("複合workspace化は、SPECをmember配下へ移す必要があります")
        return
    if "multiWorkspace" not in git(repository, "show", f"HEAD:{multi_reference.ROOT_CONFIG_PATH}").decode():
        raise ValueError("rollbackのcaseは、複合workspaceの基準版が必要です")
    if "multiWorkspace" in root_config:
        raise ValueError("rollbackはcatalogを単一workspaceへ戻す必要があります")
    if any(path.startswith("apps/web/.spec") for path in current):
        raise ValueError("rollbackはmemberの設定を残してはいけません")
    qualified = "platform::" in technical_text
    if identifier == "MULTI-024-02" and qualified:
        raise ValueError("完全rollbackは修飾参照を残しません")
    if identifier == "MULTI-024-03" and not qualified:
        raise ValueError("部分rollbackのcaseは、修飾参照が残っている必要があります")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        runner = CASES[identifier][0]
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            outcome = json.loads((fixture / f"expected/{runner}.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["manifest"].validate(manifest)
            validators["side-effects"].validate(effects)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件が審査済み期待値と異なります")
            if outcome != reviewed_result(identifier):
                raise ValueError("outcomeの期待値が審査済みcaseと異なります")
            if "status" in manifest["expect"]:
                raise ValueError("bitz以外のrunnerはCore共通結果のstatusを返しません")
            reviewed = reviewed_inputs(identifier)
            entries = {}
            for directory in ("repo", "changes"):
                for path in (fixture / directory).rglob("*"):
                    if path.is_file():
                        entries[(directory, path.relative_to(fixture / directory).as_posix())] = path.read_bytes()
            expected = {**{("repo", name): data for name, data in reviewed["files"].items()},
                        **{("changes", name): data for name, data in reviewed["changes"].items()}}
            if entries != expected:
                raise ValueError("入力が審査済みcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-compat-") as temporary:
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
                    check_shape(identifier, repository, validators["result"])
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
