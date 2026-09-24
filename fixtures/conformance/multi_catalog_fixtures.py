"""複合workspaceのcatalogと環境の事前検査を固定するreview済みvector（Core操作は実行しない）。

全体事前検査が非成功なら、member処理もContext解決もcommandも始めずに`workspaces: []`で結果を返す。
この群は、その停止条件を1件ずつ切り分ける。`MULTI-005`は未知`--workspace`が操作結果を作らないこと、
`MULTI-006`はGitが知っているcatalog未登録の設定、`MULTI-007-01/02/03`はmember pathの入れ子・submodule・別worktree、
`MULTI-019`はGit不在である。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import multi_crosscheck, multi_reference
from .git_environment_fixtures import check_cli_error_output
from .harness import git, setup, snapshot
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
UNREGISTERED_PATH = "libs/native/.spec/bitz.yaml"
INNER_CONFIG_PATH = "apps/web/inner/.spec/bitz.yaml"
CAPABILITIES = ["context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1"]
CORE = {"version": "1.0.0", "apiVersion": "1.0", "capabilities": list(CAPABILITIES)}
UNREGISTERED = {
    "code": "SPEC-MULTI-UNREGISTERED-001", "severity": "error", "resultStatus": "blocked",
    "summary": "Gitが認識する設定fileがcatalogに登録されていません",
    # 未登録の設定はworkspaceではないので、所有workspaceを持たない。
    "source": {"kind": "file", "workspaceId": None, "path": UNREGISTERED_PATH},
}
def path_diagnostic(summary):
    return {
        "code": "SPEC-MULTI-PATH-001", "severity": "error", "resultStatus": "failed",
        "summary": summary,
        "source": {"kind": "file", "workspaceId": "platform", "path": ".spec/bitz.yaml",
                   "key": "multiWorkspace.members"},
    }


NESTED_PATH = path_diagnostic("member pathが別のmemberの配下にあります")
SUBMODULE_PATH = path_diagnostic("member pathがGit submoduleです")
WORKTREE_PATH = path_diagnostic("member pathが別のworktreeです")
NO_GIT = {
    "code": "SPEC-MULTI-GIT-001", "severity": "error", "resultStatus": "blocked",
    "summary": "Git repositoryの境界を確定できません",
    "source": {"kind": "environment", "component": "git"},
}
# id: (corpus, argvの残り, Git有無, status, 終了コード, 説明)
CASES = {
    "MULTI-005": ("golden", ["check", "--workspace", "missing", "--format", "json"], True,
                  None, 4, "catalogにない--workspaceを操作結果なしで拒否する"),
    "MULTI-006": ("unregistered", ["check", "--all-workspaces", "--base", "HEAD", "--format", "json"],
                  True, "blocked", 2, "Gitが知るcatalog未登録の設定で全体操作を遮断する"),
    "MULTI-007-01": ("nested", ["doctor", "--all-workspaces", "--format", "json"], True,
                     "failed", 1, "memberの入れ子をmember path不正として拒否する"),
    "MULTI-007-02": ("submodule", ["doctor", "--all-workspaces", "--format", "json"], True,
                     "failed", 1, "memberがGit submoduleである構成を拒否する"),
    "MULTI-007-03": ("worktree", ["doctor", "--all-workspaces", "--format", "json"], True,
                     "failed", 1, "memberが別のworktreeである構成を拒否する"),
    "MULTI-019": ("golden", ["doctor", "--all-workspaces", "--format", "json"], False,
                  "blocked", 2, "Git不在の複合workspaceを遮断する"),
}
RESULT_FILES = {"MULTI-006": "expected/check.json", "MULTI-007-01": "expected/doctor.json",
                "MULTI-007-02": "expected/doctor.json", "MULTI-007-03": "expected/doctor.json",
                "MULTI-019": "expected/doctor.json"}
MEMBER_SOURCE = "changes/member"
MEMBER_SOURCE_CONFIG = f"{MEMBER_SOURCE}/.spec/bitz.yaml"


def reviewed_inputs(corpus):
    if corpus == "golden":
        return multi_reference.reviewed_inputs()
    if corpus == "unregistered":
        # catalogはweb、apiだけを登録し、libs/nativeの設定はGitが知るだけの未登録workspaceとする。
        return {**multi_reference.reviewed_inputs(),
                UNREGISTERED_PATH: multi_reference.plain_config("native").encode()}
    if corpus == "nested":
        return {
            multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config(
                [("web", "apps/web"), ("inner", "apps/web/inner")]).encode(),
            multi_reference.ROOT_REQ_PATH: (multi_reference.REQ_HEAD + "\n" + multi_reference.REQ_BODY).encode(),
            multi_reference.WEB_CONFIG_PATH: multi_reference.plain_config("web").encode(),
            INNER_CONFIG_PATH: multi_reference.plain_config("inner").encode(),
        }
    # submoduleと別worktreeは、member pathをGitの構造として作るので、member設定をchanges/へ置く。
    return {
        multi_reference.ROOT_CONFIG_PATH: multi_reference.root_config([("web", "apps/web")]).encode(),
        multi_reference.ROOT_REQ_PATH: (multi_reference.REQ_HEAD + "\n" + multi_reference.REQ_BODY).encode(),
        MEMBER_SOURCE_CONFIG: multi_reference.plain_config("web").encode(),
    }


def reviewed_manifest(identifier):
    corpus, argv, git, status, exit_code, description = CASES[identifier]
    setup_plan = {"git": git, "operations": []}
    if git and identifier != "MULTI-005":
        operations = []
        if corpus in {"submodule", "worktree"}:
            operations = [{"op": corpus, "path": "apps/web", "source": MEMBER_SOURCE}]
        setup_plan = {"git": True, "baseCommit": {"message": "base", "paths": ["."]},
                      "operations": operations}
    expect = {"exitCode": exit_code, "stdout": "json" if status else "none", "reportFileCount": 0}
    if status:
        expect = {"status": status, **expect, "resultFile": RESULT_FILES[identifier]}
    return {
        "fixtureId": identifier,
        "description": description,
        "setup": setup_plan,
        # Git不在は起動環境からGitを外して表す。単一workspaceのGit不在fixtureと同じ方法である。
        "invocation": {"runner": "bitz", "cwd": ".", "argv": list(argv),
                       "env": {} if git else {"PATH": "/dev/null"}},
        "expect": expect,
    }


def cli_output():
    """workspace selectorのinvocation errorは、終了コード4と標準エラー出力1行だけを返す。"""
    return {"exitCode": 4, "stdout": "", "stderrPrefix": "bitz: check: ",
            "stderrLineCount": 1, "stderrReasonRequired": True, "stderrTerminalControls": False}


def observe_state(manifest, repository, external):
    if manifest["setup"]["git"]:
        return observe(repository, external)
    # 明示的な不在として扱う。空の成功したGit statusにはしない。
    return {"repository": snapshot(repository), "git": None,
            **{name: snapshot(path) for name, path in external.items()}}


def blocked_check_result():
    return {
        "schemaVersion": "1.0", "operation": "check", "scope": "all-workspaces", "status": "blocked",
        "multiWorkspace": {"id": "platform", "path": "."},
        # 事前検査が非成功なので、member処理を開始せず空配列を返す。
        "workspaces": [],
        "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
        "durationMs": 0,
        "diagnostics": [dict(UNREGISTERED)],
    }


def doctor_result(identifier):
    if identifier == "MULTI-019":
        # Git境界を確定できないので、catalogの検査へ進まない。
        checks = [{"name": "core", "status": "passed"}, {"name": "git", "status": "blocked"}]
        status, diagnostic = "blocked", NO_GIT
    else:
        checks = [{"name": "core", "status": "passed"}, {"name": "git", "status": "passed"},
                  {"name": "catalog", "status": "failed"}]
        status = "failed"
        diagnostic = {"MULTI-007-01": NESTED_PATH, "MULTI-007-02": SUBMODULE_PATH,
                      "MULTI-007-03": WORKTREE_PATH}[identifier]
    return {
        "schemaVersion": "1.0", "operation": "doctor", "status": status,
        "multiWorkspace": {"id": "platform", "path": "."},
        "core": json.loads(json.dumps(CORE)),
        "checks": checks,
        "workspaces": [],
        "durationMs": 0,
        "diagnostics": [dict(diagnostic)],
    }


def reviewed_result(identifier):
    if identifier == "MULTI-006":
        return blocked_check_result()
    return doctor_result(identifier)


def check_precondition(identifier, repository):
    """停止の原因を、散文ではなくsetup後の入力から確かめる。"""
    corpus = CASES[identifier][0]
    if corpus == "unregistered":
        _, members = multi_crosscheck.catalog(repository)
        if UNREGISTERED_PATH in {f"{path}/.spec/bitz.yaml" for _, path in members}:
            raise ValueError("未登録の設定がcatalogへ入っています")
        if not (repository / UNREGISTERED_PATH).is_file():
            raise ValueError("未登録の設定fileが入力にありません")
    elif corpus == "nested":
        _, members = multi_crosscheck.catalog(repository)
        paths = [path for _, path in members]
        if not any(other != path and other.startswith(path + "/") for path in paths for other in paths):
            raise ValueError("入れ子のcaseは、別memberの配下にあるmember pathが必要です")
        for _, path in members:
            if not (repository / path / ".spec/bitz.yaml").is_file():
                raise ValueError("入れ子のcaseでも、各memberは自身の設定を持つ必要があります")
    if corpus == "submodule":
        entry = git(repository, "ls-files", "--stage", "--", "apps/web").decode().split()
        if not entry or entry[0] != "160000":
            raise ValueError("submoduleのcaseは、gitlinkとして記録されている必要があります")
        if "apps/web" not in (repository / ".gitmodules").read_text(encoding="utf-8"):
            raise ValueError("submoduleのcaseは、.gitmodulesの登録が必要です")
        if not (repository / "apps/web/.git").is_dir():
            raise ValueError("submoduleのcaseは、別repositoryの実体が必要です")
    if corpus == "worktree":
        marker = repository / "apps/web/.git"
        if not marker.is_file() or not marker.read_text(encoding="utf-8").startswith("gitdir:"):
            raise ValueError("別worktreeのcaseは、gitdirを指す.git fileが必要です")
        if "apps/web" not in git(repository, "worktree", "list").decode():
            raise ValueError("別worktreeのcaseは、同じrepositoryのworktreeである必要があります")
        if git(repository, "ls-files", "--stage", "--", "apps/web").decode().strip():
            raise ValueError("別worktreeのmember pathは親のindexへ記録しません")
    if corpus in {"submodule", "worktree"}:
        if not (repository / "apps/web/.spec/bitz.yaml").is_file():
            raise ValueError("member設定がなければ、原因がmember pathではなくmember設定になります")
    if identifier == "MULTI-019" and (repository / ".git").exists():
        raise ValueError("Git不在のcaseにGitのmetadataがあります")
    if identifier == "MULTI-005":
        argv = CASES[identifier][1]
        _, members = multi_crosscheck.catalog(repository)
        if argv[argv.index("--workspace") + 1] in {workspace_id for workspace_id, _ in members}:
            raise ValueError("未知--workspaceのcaseは、catalogにないIDを渡す必要があります")
        check_cli_error_output(4, b"", b"bitz: check: reason\n", "check")


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
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["manifest"].validate(manifest)
            validators["side-effects"].validate(effects)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件が審査済み期待値と異なります")
            if identifier == "MULTI-005":
                if (fixture / "expected").exists():
                    raise ValueError("引数不正fixtureは期待結果fileを持ちません")
                if json.loads((fixture / "cli-output.json").read_text()) != cli_output():
                    raise ValueError("CLI出力の期待値が審査済みの契約と異なります")
            else:
                result = json.loads((fixture / RESULT_FILES[identifier]).read_text())
                validators["result"].validate(result)
                if result != reviewed_result(identifier):
                    raise ValueError("完全結果が審査済み期待値と異なります")
                if result["workspaces"]:
                    raise ValueError("事前検査の非成功はmember結果を持ちません")
            inputs = reviewed_inputs(CASES[identifier][0])
            files = {}
            for directory in ("repo", "changes"):
                prefix = "" if directory == "repo" else f"{directory}/"
                for path in (fixture / directory).rglob("*"):
                    if path.is_file() or path.is_symlink():
                        files[prefix + path.relative_to(fixture / directory).as_posix()] = path
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[key]
                                                for key, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-catalog-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {key: sandbox / key for key in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe_state(manifest, repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
                    check_precondition(identifier, repository)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
