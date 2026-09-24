"""明示起点の不在とADR起点を固定するfixture（Core操作は実行しない）。

SINGLE-111-01〜04は構文上妥当だがcatalogに存在しない起点を扱う。いずれも終了コード4ではなく
`CTX-ROOT-MISSING-001`／failedとし、statement不在を所有文書のcheckへ置き換えない。
SINGLE-112-01/03はADR起点のinterpret contextと明示checkを扱う。ADRはtest義務へ展開されないため、
target statementは空で、checkは文書検査だけを行う。ADR起点を引数不正とする112-02/04は
cli_error_fixturesが所有する。

根拠は[CLI基盤契約 §6]、[check仕様 §2・§9]、[関係・トレースモデル §6.4]である。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference
from .harness import git, setup
from .initial_fixtures import CONFIGS, observe, compare_state

HERE = Path(__file__).resolve().parent
MISSING_DOCUMENT = "REQ-009"
MISSING_STATEMENT = "REQ-001:AC-09"
MISSING_PATH = ".spec/requirements/REQ-009.md"
ADR_TITLE = "認証方式の選定"
# ID: (argv, status, 説明)
CASES = {
    "SINGLE-111-01": (["check", MISSING_DOCUMENT, "--base", "HEAD", "--format", "json"], "failed",
                      "catalogにない明示文書IDをCTX-ROOT-MISSING-001で返す"),
    "SINGLE-111-02": (["check", MISSING_STATEMENT, "--base", "HEAD", "--format", "json"], "failed",
                      "不在statement IDを所有文書checkへ置換せずCTX-ROOT-MISSING-001で返す"),
    "SINGLE-111-03": (["check", MISSING_PATH, "--base", "HEAD", "--format", "json"], "failed",
                      "catalogにないSPEC pathをCTX-ROOT-MISSING-001で返す"),
    "SINGLE-111-04": (["verify", MISSING_DOCUMENT, "--format", "json"], "failed",
                      "catalogにない明示文書IDをverify targetのDiagnosticで返す"),
    "SINGLE-112-01": (["context", "ADR-001", "--purpose", "interpret", "--format", "json"], "passed",
                      "ADR起点のinterpret contextはtarget statementを持たない"),
    "SINGLE-112-03": (["check", "ADR-001", "--base", "HEAD", "--format", "json"], "passed",
                      "ADR起点の明示checkは文書検査だけを行う"),
}
MISSING_ARGUMENT = {"SINGLE-111-01": MISSING_DOCUMENT, "SINGLE-111-02": MISSING_STATEMENT,
                    "SINGLE-111-03": MISSING_PATH, "SINGLE-111-04": MISSING_DOCUMENT}
EMPTY_COVERAGE = {**{modality: {key: [] for key in ("total", "addressed", "tested", "unaddressed", "untested")}
                     for modality in ("must", "should", "may")}, "adjacent": []}


def reviewed_inputs(identifier):
    if identifier.startswith("SINGLE-111"):
        return dict(digest_reference.reviewed_inputs("SINGLE-042"))
    # ADRを参照する文書を置かず、逆参照の扱いを原因へ混ぜない。
    return {".spec/bitz.yaml": CONFIGS["SINGLE-001"].encode(),
            digest_reference.ADR_PATH: digest_reference.ADR_DOCUMENT.encode()}


def reviewed_manifest(identifier):
    argv, status, description = CASES[identifier]
    if argv[0] == "verify":
        # verifyは設定がindexに無いと起動前に停止するため、commitせずstageする。
        plan = {"git": True, "operations": [{"op": "stage", "paths": ["."]}]}
    elif argv[0] == "check":
        plan = {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []}
    else:
        plan = {"git": True, "operations": []}
    return {
        "fixtureId": identifier, "description": description, "setup": plan,
        "invocation": {"runner": "bitz", "cwd": ".", "argv": list(argv), "env": {}},
        "expect": {"status": status, "exitCode": 1 if status == "failed" else 0, "stdout": "json",
                   "resultFile": f"expected/{argv[0]}.json", "reportFileCount": 0},
    }


def missing_diagnostic(identifier):
    argument = MISSING_ARGUMENT[identifier]
    return {"code": "CTX-ROOT-MISSING-001", "severity": "error", "resultStatus": "failed",
            "summary": f"起点{argument}が存在しません",
            "source": {"kind": "invocation", "argument": argument}}


def reviewed_digest_input():
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0",
        "resolverVersion": "1.0", "purpose": "interpret", "requestWorkspaceId": "root",
        "roots": ["ADR-001"], "workspaces": [{"id": "root", "path": "."}],
        "documents": [{
            "id": "ADR-001", "workspaceId": "root", "kind": "decision", "status": "accepted",
            "applicability": "applicable",
            "frontmatter": {"id": "ADR-001", "title": ADR_TITLE, "status": "accepted",
                            "relations": dict(digest_reference.EMPTY_RELATIONS),
                            "implements": [], "tests": [], "verify": None, "changes": []},
            "bodyText": digest_reference.ADR_DOCUMENT.split("\n---\n", 1)[1].lstrip("\n"),
            "statements": [], "strongRelations": [],
        }],
        "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [{"id": "root", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            # interpretはbindingを収録しないため、timeoutとcommandは空である。
            "verifyTimeouts": [], "commands": [],
        },
    }


def reviewed_result(identifier):
    argv, status, _ = CASES[identifier]
    base = {"schemaVersion": "1.0", "operation": argv[0], "status": status}
    committed = {"base": "0" * 40, "commit": "0" * 40, "dirty": False}
    if argv[0] == "check":
        missing = identifier.startswith("SINGLE-111")
        return {**base, "scope": "selected", "workspace": {"id": "root", "path": "."},
                "revision": committed,
                # 起点を解決できないため完全検査した文書はない。ADRは1文書・規範文0件である。
                "checkedDocumentCount": 0 if missing else 1, "checkedStatementCount": 0,
                "durationMs": 0, "diagnostics": [missing_diagnostic(identifier)] if missing else []}
    if argv[0] == "verify":
        return {**base, "scope": "selected", "workspace": {"id": "root", "path": "."},
                "targetResults": [{"target": MISSING_DOCUMENT, "status": "failed", "contextDigest": None,
                                   "statements": [], "bindingRefs": [],
                                   "diagnostics": [missing_diagnostic(identifier)]}],
                "revision": None, "commands": [], "durationMs": 0, "diagnostics": []}
    return {
        **base, "purpose": "interpret", "workspace": {"id": "root", "path": "."},
        "roots": ["ADR-001"],
        "contextDigest": digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input())),
        "revision": None,
        "resolution": {"complete": True, "documentCount": 1, "unresolvedStrongRelations": 0},
        "projection": {"detail": "standard", "expanded": []},
        "documents": [{
            "id": "ADR-001", "kind": "decision", "status": "accepted", "role": "root",
            "path": digest_reference.ADR_PATH, "projection": "full", "reachedBy": ["root"],
            "statementRefs": [],
            "frontmatter": {"id": "ADR-001", "title": ADR_TITLE, "status": "accepted"},
            "bodyText": reviewed_digest_input()["documents"][0]["bodyText"], "untrustedText": True}],
        "constraintLedger": {"statements": []},
        "coverage": json.loads(json.dumps(EMPTY_COVERAGE)),
        "durationMs": 0, "diagnostics": [],
    }


def check_contract(identifier, result):
    """個々の期待値が単一原因の規則に沿うことを、完全比較とは別に確かめる。"""
    if identifier.startswith("SINGLE-111"):
        diagnostics = (result["targetResults"][0]["diagnostics"] + result["diagnostics"]
                       if result["operation"] == "verify" else result["diagnostics"])
        if [d["code"] for d in diagnostics] != ["CTX-ROOT-MISSING-001"] or result["status"] != "failed":
            raise ValueError("不在起点はCTX-ROOT-MISSING-001／failedの1件だけで返す必要があります")
        if diagnostics[0]["source"] != {"kind": "invocation", "argument": MISSING_ARGUMENT[identifier]}:
            raise ValueError("不在起点のsourceは指定した引数そのものである必要があります")
        if result["operation"] == "check" and result["checkedDocumentCount"] != 0:
            raise ValueError("不在起点を所有文書や既知文書のcheckへ置換してはいけません")
        if result["operation"] == "verify" and (result["commands"] or result["targetResults"][0]["bindingRefs"]):
            raise ValueError("不在起点のtargetはbindingを実行してはいけません")
    elif result["operation"] == "context":
        if result["constraintLedger"]["statements"] or result["coverage"] != EMPTY_COVERAGE:
            raise ValueError("ADR起点のinterpretはtarget statementを持ってはいけません")
    elif result["checkedStatementCount"] != 0 or result["diagnostics"]:
        raise ValueError("ADR起点のcheckは規範文を持たない文書検査だけで通過する必要があります")


def check_inputs(identifier):
    inputs = reviewed_inputs(identifier)
    if identifier.startswith("SINGLE-111"):
        if MISSING_PATH in inputs or any(MISSING_DOCUMENT.encode() in data for data in inputs.values()):
            raise ValueError("不在とする起点が入力に存在します")
        requirement = inputs[digest_reference.REQ_PATH].decode()
        if "[REQ-001:AC-01]" not in requirement or f"[{MISSING_STATEMENT}]" in requirement:
            raise ValueError("111-02は所有文書が存在しstatementだけが不在である必要があります")
    elif any(b"ADR-001" in data for path, data in inputs.items() if path != digest_reference.ADR_PATH):
        raise ValueError("ADR起点caseにADRを参照する文書を置いてはいけません")


def check_git_state(identifier, repository):
    argv = CASES[identifier][0]
    inputs = reviewed_inputs(identifier)
    listed = set(git(repository, "ls-files", "-z").decode().split("\0")[:-1])
    if argv[0] == "context":
        if listed:
            raise ValueError("context fixtureのindexは空である必要があります")
    elif listed != set(inputs):
        raise ValueError("indexのpathが審査済み入力と異なります")
    try:
        git(repository, "rev-parse", "--verify", "HEAD")
        committed = True
    except subprocess.CalledProcessError:
        committed = False
    if committed != (argv[0] == "check"):
        raise ValueError("commitの有無が操作の前提と異なります")
    if committed and git(repository, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("明示check fixtureはclean状態である必要があります")


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
            result = json.loads((fixture / manifest["expect"]["resultFile"]).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("起動条件または完全結果が審査済み期待値と異なります")
            check_contract(identifier, result)
            check_inputs(identifier)
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            for path, kind in ((digest_reference.REQ_PATH, "reqFrontmatter"),
                               (digest_reference.TECH_PATH, "techFrontmatter"),
                               (digest_reference.ADR_PATH, "adrFrontmatter")):
                if path in inputs:
                    frontmatter, _ = digest_crosscheck.split_document(inputs[path].decode())
                    Draft202012Validator({"$ref": "#/$defs/" + kind, "$defs": schema["$defs"]}).validate(frontmatter)
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-target-root-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    check_git_state(identifier, repository)
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離setupが固定snapshotと異なります")
                    previous = actual
                    if identifier == "SINGLE-112-01":
                        derived = digest_crosscheck.canonical_bytes(
                            digest_crosscheck.build(repository, root="ADR-001", purpose="interpret"))
                        if derived != digest_reference.canonical_bytes(reviewed_digest_input()):
                            raise ValueError("reference AとBのCanonical JSONが一致しません")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
