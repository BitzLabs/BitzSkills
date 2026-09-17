"""不正な基準版・Git不在の固定した証拠と出力の検査（Coreの処理ではない）。"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .harness import git, setup, snapshot
from .initial_fixtures import CONFIGS, observe, compare_state
from .trace_fixtures import TECH, TECH_PATH
from .git_fixtures import TASK_PATH

HERE = Path(__file__).resolve().parent
CASES = ("SINGLE-036", "SINGLE-037", "SINGLE-038")
MISSING_BASE = "fixture-missing-base"
TASK = "---\nid: TASK-001\ntitle: Git不在の境界検査\nstatus: open\n---\n\n# TASK-001 Git不在の境界検査\n\n## Objective\n\nGit基準版を必要とする境界検査を確認する。\n"
# 人向けの文言は機械の契約ではない。規範が定めるstreamの形だけを固定する。
CLI_OUTPUT = {"exitCode": 4, "stdout": "", "stderrPrefix": "bitz: check: ",
              "stderrLineCount": 1, "stderrReasonRequired": True, "stderrTerminalControls": False}


def check_cli_error_output(exit_code, stdout, stderr, operation="check"):
    """どの操作の引数不正でも、安全な標準エラー出力を1行だけ出す。終了コード4の
    fixtureすべてで共有し、契約を1か所で述べる。"""
    if exit_code != 4 or stdout != b"":
        raise ValueError("CLIの引数不正は終了コード4と空の標準出力でなければなりません")
    prefix = f"bitz: {operation}: "
    text = stderr.decode("utf-8")
    if not re.fullmatch(re.escape(prefix) + r"[^\x00-\x1f\x7f-\x9f]+\n", text) or not text[len(prefix):-1].strip():
        raise ValueError("CLIの標準エラー出力は、空でない理由を持つ安全な1行でなければなりません")


def reviewed_inputs(identifier):
    files = {".spec/bitz.yaml": CONFIGS["SINGLE-001"].encode()}
    if identifier == "SINGLE-038":
        files[TASK_PATH] = TASK.encode()
    else:
        files[TECH_PATH] = TECH.encode()
    if identifier == "SINGLE-036":
        files[".spec/reports/existing.json"] = b"{}\n"
    return files


def reviewed_manifest(identifier):
    invalid = identifier == "SINGLE-036"
    plan = {"git": invalid, "operations": []}
    if invalid:
        plan["baseCommit"] = {"message": "base", "paths": ["."]}
    args = ["--base", MISSING_BASE, "--report"] if invalid else ["TASK-001"] if identifier == "SINGLE-038" else []
    expect = {"exitCode": 4, "stdout": "none", "reportFileCount": 0} if invalid else {
        "exitCode": 2 if identifier == "SINGLE-038" else 0,
        "status": "blocked" if identifier == "SINGLE-038" else "passed_with_warnings",
        "stdout": "json", "resultFile": "expected/check.json", "reportFileCount": 0}
    return {"fixtureId": identifier, "description": "解決不能なGit基準版" if invalid else "Git不在でのcheck縮退とTASK境界",
        "setup": plan, "invocation": {"runner": "bitz", "cwd": ".", "argv": ["check", *args, "--format", "json"],
            "env": {} if invalid else {"PATH": "/dev/null"}}, "expect": expect}


def reviewed_result(identifier):
    task = identifier == "SINGLE-038"
    status = "blocked" if task else "passed_with_warnings"
    return {"schemaVersion": "1.0", "operation": "check", "status": status, "scope": "selected" if task else "full",
        "workspace": {"id": "root", "path": "."}, "revision": None,
        "checkedDocumentCount": 1, "checkedStatementCount": 0, "durationMs": 0,
        "diagnostics": [{"code": "SPEC-TASK-BOUNDARY-002" if task else "SPEC-GIT-DEGRADED-001",
            "severity": "error" if task else "warning", "resultStatus": status,
            "summary": "Git不在のためTASK-001の変更境界を検査できません" if task else
                "Git不在のため全体checkへ縮退します。承認済みREQ保護、状態遷移、管理済みSPEC削除の差分検査は実施できません",
            "source": {"kind": "environment", "component": "git", "identifier": "git"}}]}


def check_environment(repository, identifier, manifest):
    if identifier == "SINGLE-036":
        git(repository, "rev-parse", "--verify", "HEAD^{commit}")
        try:
            git(repository, "rev-parse", "--verify", MISSING_BASE + "^{commit}")
        except subprocess.CalledProcessError:
            pass
        else:
            raise ValueError("不正な基準版が想定外に解決されています")
        expected = reviewed_inputs(identifier)
        for revision, args in (("HEAD:", ("ls-tree", "-r", "--name-only", "-z", "HEAD")), (":", ("ls-files", "-z"))):
            if set(git(repository, *args).decode().split("\0")[:-1]) != set(expected):
                raise ValueError("不正な基準版のHEADまたはindexのpathが変わっています")
            for path, content in expected.items():
                if git(repository, "show", revision + path) != content:
                    raise ValueError("不正な基準版のHEADまたはindexのbyte列が変わっています")
    else:
        # directoryでない絶対pathをPATHにして、current directoryとhostのPATHへの退避を防ぐ。
        if manifest["invocation"]["env"] != {"PATH": "/dev/null"} or not Path("/dev/null").is_char_device():
            raise ValueError("Git不在fixtureにはLinuxの/dev/nullをPATHにする必要があります")
        if shutil.which("git", path=manifest["invocation"]["env"]["PATH"]) is not None:
            raise ValueError("fixtureの起動環境でGitが解決されています")
        # hostが一時directoryより上にGitのmetadataを置いている場合がある。起動環境では
        # Gitの実行fileを使えないので、hostのGitで調べない。
        if (repository / ".git").exists() or (repository / ".git").is_symlink():
            raise ValueError("Git不在fixtureはGitのmetadataを含んではいけません")
    actual = {p.relative_to(repository).as_posix(): p.read_bytes() for p in repository.rglob("*")
              if p.is_file() and ".git" not in p.relative_to(repository).parts}
    if actual != reviewed_inputs(identifier):
        raise ValueError("作業treeが審査済みの環境入力と異なります")


def observe_environment(repository, external, identifier):
    if identifier == "SINGLE-036":
        return observe(repository, external)
    # 明示的な不在として扱う。空の成功したGit statusや、握りつぶしたGitのerrorにはしない。
    return {"repository": snapshot(repository), "git": None,
            **{name: snapshot(path) for name, path in external.items()}}


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads((root / "frontmatter.schema.json").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            validators["manifest"].validate(manifest)
            validators["side-effects"].validate(effects)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("manifestが審査済みの環境caseと異なります")
            if identifier == "SINGLE-036":
                if json.loads((fixture / "cli-output.json").read_text()) != CLI_OUTPUT:
                    raise ValueError("CLI出力の契約が審査済みのstreamの形と異なります")
                if (fixture / "expected").exists():
                    raise ValueError("終了コード4は操作結果を持ってはいけません")
            else:
                result = json.loads((fixture / "expected/check.json").read_text())
                validators["result"].validate(result)
                if result != reviewed_result(identifier):
                    raise ValueError("完全結果が審査済みのGit不在と異なります")
            files = {p.relative_to(fixture / "repo").as_posix(): p for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            expected = reviewed_inputs(identifier)
            if set(files) != set(expected) or any(p.is_symlink() or p.read_bytes() != expected[name] for name, p in files.items()):
                raise ValueError("入力が審査済みの単一の環境原因と異なります")
            task = identifier == "SINGLE-038"
            Draft202012Validator({"$ref": "#/$defs/" + ("taskFrontmatter" if task else "techFrontmatter"), "$defs": schema["$defs"]}).validate(
                {"id": "TASK-001" if task else "TECH-001", "title": "Git不在の境界検査" if task else "前提技術", "status": "open" if task else "approved"})
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-git-environment-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    check_environment(repository, identifier, manifest)
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for directory in external.values():
                        directory.mkdir()
                    actual = observe_environment(repository, external, identifier)
                    if compare_state(effects["before"], actual) or (previous is not None and actual != previous):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
