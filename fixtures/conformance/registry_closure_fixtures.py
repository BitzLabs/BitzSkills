"""matrix §6.9のregistry閉包を固定した証拠。規範文、relation、設定、doctor、workspaceの条件を、
それぞれ単独で返さなければならない。

Core操作、YAML loader、Gitの調査は実装しない。同等の原因に固定したbyte列がある場合は
review済みの入力を再利用し、fixtureは同じ入力の2つ目の読み方ではなく、新しい操作や結果の形を加える。
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .document_fixtures import DOCUMENT, REQ_PATH
from .ears_fixtures import GOOD
from .harness import setup, snapshot
from .initial_fixtures import CONFIGS, observe, compare_state

HERE = Path(__file__).resolve().parent
CONFIG_PATH = ".spec/bitz.yaml"
KEEP_PATH = ".gitkeep"
CONFIG = CONFIGS["SINGLE-001"]
ANCHOR_CONFIG = 'schemaVersion: "1.0"\nlanguage: &label ja\nearsAi: "1.0"\n'
EARS_MAJOR_CONFIG = 'schemaVersion: "1.0"\nlanguage: ja\nearsAi: "2.0"\n'
SHOULD_STATEMENT = "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [SHOULD] [CONSTRAINT] 秘密情報を出力しない。"
RELATED = "relations:\n  related: [TECH-999]\n"
MISSING_TARGET = "TECH-999"
# 固定した文書での、[SHOULD]のreview済みの1始まりのUnicodeコードポイント位置。
SHOULD_LINE, SHOULD_COLUMN = 15, 49
EXIT = {"passed": 0, "passed_with_warnings": 0, "failed": 1, "blocked": 2, "error": 3}
CORE = {"version": "1.0.0", "apiVersion": "1.0",
        "capabilities": ["context.v1", "check.v1", "verify.v1", "doctor.v1", "multiWorkspace.v1"]}
LOST_GUARANTEES = ["approved-diff-protection", "deletion-detection", "status-transition", "task-boundary"]
# docs/03.詳細設計/03_操作仕様/04_doctor.md §3: the reviewed check order.
DOCTOR_ORDER = ("core", "workspace", "config", "schema", "ears", "git", "command", "impact")


def doctor_checks(degraded=None, executed=DOCTOR_ORDER):
    checks = []
    for name in DOCTOR_ORDER:
        if name not in executed:
            continue
        check = {"name": name, "status": "info" if name == "impact" else "passed"}
        if degraded and name in degraded:
            check = {"name": name, **degraded[name]}
        checks.append(check)
    return checks


def file_source(path, workspace, **extra):
    return {"kind": "file", "workspaceId": workspace, "path": path, **extra}


CASES = {
    "SINGLE-089": {
        "operation": "check", "status": "passed_with_warnings", "git": True, "workspace": "root",
        "documents": 1, "statements": 1, "code": "EAI-CORE-SHOULD-001",
        "summary": "SHOULDに[REASON]がありません",
        "source": file_source(REQ_PATH, "root", line=SHOULD_LINE, column=SHOULD_COLUMN),
        "description": "理由なしSHOULDを警告し規範文の検査を続ける"},
    "SINGLE-090": {
        "operation": "check", "status": "passed_with_warnings", "git": True, "workspace": "root",
        "documents": 1, "statements": 1, "code": "SPEC-RELATION-ADVISORY-MISSING-001",
        "summary": "relatedの参照先が存在しません",
        "source": file_source(REQ_PATH, "root", key="relations.related"),
        "description": "不在のrelatedを警告し文書の検査を続ける"},
    "SINGLE-091": {
        "operation": "check", "status": "error", "git": True, "workspace": None,
        "documents": 0, "statements": 0, "code": "SPEC-CONFIG-SCHEMA-001",
        "summary": "設定YAMLのanchorは禁止です", "config": ANCHOR_CONFIG,
        "source": file_source(CONFIG_PATH, None, key="language"),
        "description": "設定の禁止YAML構文で読取りを止める"},
    "SINGLE-092": {
        "operation": "doctor", "status": "error", "git": True, "workspace": None,
        "code": "SPEC-CONFIG-SCHEMA-001", "summary": "languageはstringで指定してください",
        "config": CONFIGS["SINGLE-004-01"], "source": file_source(CONFIG_PATH, None, key="language"),
        "checks": doctor_checks({"config": {"status": "error"}}, ("core", "workspace", "config", "git")),
        "description": "doctorの設定型不正をconfig checkと共通codeで返す"},
    "SINGLE-093": {
        "operation": "doctor", "status": "passed_with_warnings", "git": False, "workspace": "root",
        "code": "SPEC-DOCTOR-GIT-001",
        "summary": "Git不在のため差分に依存する保証を提供できません",
        "source": {"kind": "environment", "component": "git", "identifier": "git"},
        "checks": doctor_checks({"git": {"status": "warning", "lostGuarantees": LOST_GUARANTEES}}),
        "description": "Git不在の単一workspace doctorを警告で継続する"},
    "SINGLE-094": {
        "operation": "check", "status": "blocked", "git": True, "workspace": None,
        "documents": 0, "statements": 0, "code": "SPEC-WORKSPACE-MISSING-001",
        "summary": ".spec/bitz.yamlがありません",
        "source": {"kind": "environment", "component": "workspace", "identifier": "."},
        "description": "設定不在のcheckをworkspace不在として止める"},
    "SINGLE-095": {
        "operation": "check", "status": "blocked", "git": True, "workspace": "root",
        "documents": 0, "statements": 0, "code": "SPEC-EARS-VERSION-001",
        "summary": "未対応のEARS-AI majorです", "config": EARS_MAJOR_CONFIG,
        "source": file_source(CONFIG_PATH, "root", key="earsAi"),
        "description": "未知EARS-AI majorで読取りを止める"},
}


def reviewed_inputs(identifier):
    case = CASES[identifier]
    if identifier == "SINGLE-094":
        return {KEEP_PATH: b""}
    inputs = {CONFIG_PATH: case.get("config", CONFIG).encode()}
    if identifier == "SINGLE-089":
        inputs[REQ_PATH] = DOCUMENT.replace(GOOD, SHOULD_STATEMENT, 1).encode()
    elif identifier == "SINGLE-090":
        inputs[REQ_PATH] = DOCUMENT.replace("status: approved\n---", "status: approved\n" + RELATED + "---", 1).encode()
    return inputs


def reviewed_manifest(identifier):
    case = CASES[identifier]
    operation, status, git_present = case["operation"], case["status"], case["git"]
    plan = {"git": git_present, "operations": []}
    argv = [operation]
    if operation == "check":
        argv.append("--full")
        if git_present:
            plan["baseCommit"] = {"message": "base", "paths": ["."]}
            argv += ["--base", "HEAD"]
    argv += ["--format", "json"]
    return {"fixtureId": identifier, "description": case["description"], "setup": plan,
            "invocation": {"runner": "bitz", "cwd": ".", "argv": argv,
                           "env": {} if git_present else {"PATH": "/dev/null"}},
            "expect": {"status": status, "exitCode": EXIT[status], "stdout": "json",
                       "resultFile": f"expected/{operation}.json", "reportFileCount": 0}}


def reviewed_result(identifier):
    case = CASES[identifier]
    status = case["status"]
    result = {"schemaVersion": "1.0", "operation": case["operation"], "status": status,
              "workspace": {"id": case["workspace"], "path": "."}, "durationMs": 0,
              "diagnostics": [{"code": case["code"],
                               "severity": "warning" if status == "passed_with_warnings" else "error",
                               "resultStatus": status, "summary": case["summary"], "source": case["source"]}]}
    if case["operation"] == "doctor":
        result["core"] = CORE
        result["checks"] = case["checks"]
    else:
        result["scope"] = "full"
        result["revision"] = {"base": "0" * 40, "commit": "0" * 40, "dirty": False} if case["git"] else None
        result["checkedDocumentCount"] = case["documents"]
        result["checkedStatementCount"] = case["statements"]
    return result


def check_conditions(identifier, inputs):
    """各単一原因を、散文からではなく固定したbyte列から導き直す。"""
    if identifier == "SINGLE-089":
        document = inputs[REQ_PATH].decode()
        if "[REASON]" in document or document.count("[SHOULD]") != 1:
            raise ValueError("SHOULDのcaseには、ちょうど1つのmodalityとreason fieldのないことが必要です")
        line = document.splitlines()[SHOULD_LINE - 1]
        if line.find("[SHOULD]") + 1 != SHOULD_COLUMN or not line.startswith("- [REQ-001:AC-01]"):
            raise ValueError("review済みの[SHOULD]の位置が固定した文書と異なります")
    if identifier == "SINGLE-090":
        document = inputs[REQ_PATH].decode()
        if document.count(MISSING_TARGET) != 1 or "requires" in document or "refines" in document:
            raise ValueError("advisoryのcaseはrelated関係だけを持つ必要があります")
        if any(MISSING_TARGET in name for name in inputs):
            raise ValueError("advisoryの参照先はcorpusに存在してはいけません")
    if identifier == "SINGLE-091":
        config = inputs[CONFIG_PATH].decode()
        if config.replace("&label ", "") != CONFIG or "*label" in config:
            raise ValueError("禁止構文のcaseは、最小の設定とanchorだけが異なる必要があります")
    if identifier == "SINGLE-092" and inputs[CONFIG_PATH] != CONFIGS["SINGLE-004-01"].encode():
        raise ValueError("doctorの設定caseはreview済みの型誤りの入力を再利用する必要があります")
    if identifier == "SINGLE-094" and (set(inputs) != {KEEP_PATH} or inputs[KEEP_PATH]):
        raise ValueError("workspace不在のcaseには、空のSPECでないfile 1件と、設定がないことが必要です")
    if identifier == "SINGLE-095":
        config = inputs[CONFIG_PATH].decode()
        if config.replace('earsAi: "2.0"', 'earsAi: "1.0"') != CONFIG:
            raise ValueError("EARS majorのcaseは、最小の設定とversionだけが異なる必要があります")
    configured = any(name.startswith(".spec/") for name in inputs)
    if configured == (identifier == "SINGLE-094"):
        raise ValueError("workspaceの有無が審査済みのcaseと矛盾します")


def check_environment(identifier, repository, manifest):
    """Git不在は断定ではなく、隔離setupで観測する性質である。"""
    if CASES[identifier]["git"]:
        return observe
    if manifest["invocation"]["env"] != {"PATH": "/dev/null"} or not Path("/dev/null").is_char_device():
        raise ValueError("Git不在fixtureにはLinuxの/dev/nullのPATHが必要です")
    if shutil.which("git", path=manifest["invocation"]["env"]["PATH"]) is not None:
        raise ValueError("fixtureの起動環境でGitが解決されています")
    if (repository / ".git").exists() or (repository / ".git").is_symlink():
        raise ValueError("Git不在fixtureはGitのmetadataを含んではいけません")
    # 明示的な不在として扱い、空の成功したGit statusにはしない。
    return lambda root, external: {"repository": snapshot(root), "git": None,
                                   **{name: snapshot(path) for name, path in external.items()}}


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            operation = CASES[identifier]["operation"]
            result = json.loads((fixture / f"expected/{operation}.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("manifestまたは結果が審査済みの単一条件と異なります")
            inputs = reviewed_inputs(identifier)
            check_conditions(identifier, inputs)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("これらの条件はfileを書いてはいけません")
            if (effects["before"]["git"] is None) is CASES[identifier]["git"]:
                raise ValueError("Git snapshotの有無が審査済みの環境と矛盾します")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-registry-closure-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    observer = check_environment(identifier, repository, manifest)
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observer(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
