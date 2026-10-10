"""テスト対応が文書の`verify`でコマンド名を解決するとき、ハッシュ値の材料がそのコマンドを収録することを固定する（Coreの公開操作は実行しない）。

`SINGLE-154`（`context --purpose verify`）と`SINGLE-155`（`verify`）は同じ入力で、同じコンテキストのハッシュ値を期待する対である。
入力は、テスト対応が`command`を持たず、文書の`verify: default`でコマンド名`default`を解決する1つのREQ-001である。

- ハッシュ値の`settings.commands`と`settings.verifyTimeouts`は、目的`verify`のコンテキスト一式が収録したテスト割当てだけから作る。
  収録したテスト割当ては、閉包の文書のテスト対応のコマンド名を`tests[].command`、なければ文書の`verify`の順で解決し、
  そのワークスペースの設定に定義があるものとする（ハッシュ値の正規化仕様 §3。`verify`が実行する解決と同じ）。
  この入力では`root::default`の1件と、`root`の`timeoutSeconds`（既定値300）の1件になる。
- `SINGLE-154`の`contextDigest`は、独立に書いた2系統の参照計算（digest_command_fixtures内のリテラルA、digest_crosscheckの木構造からの導出B）で
  照合する。`SINGLE-155`の検証対象の`contextDigest`は`SINGLE-154`と同じ値であり、`SINGLE-155`の入力からも参照計算Bで導く。
- 文書の`verify`による解決は、`verify`だけが読んでハッシュ値の材料は`tests[].command`しか読まない、という不整合を検出するためにある。
  このため、`verify: default`を取り除くと材料の`commands`と`verifyTimeouts`が空になって正規JSONが変わることも、監査が確かめる。
"""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference
from .context_config_fixtures import EMPTY_BUCKET, check_unborn
from .document_fixtures import DOCUMENT, REQ_PATH
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
CONFIG_PATH = digest_reference.CONFIG_PATH
TEST_PATH = "tests/test_auth.py"
STATEMENT = "REQ-001:AC-01"
HEAD_END = "status: approved\n---\n"
# フロントマターは、`tests`が`command`を持たず、文書の`verify`だけがコマンド名を与える。
FRONTMATTER_FIELDS = f"tests:\n  - path: {TEST_PATH}\n    covers: [{STATEMENT}]\nverify: default\n"
REQUIREMENT = DOCUMENT.replace(HEAD_END, "status: approved\n" + FRONTMATTER_FIELDS + "---\n", 1)
BODY_TEXT = DOCUMENT.partition(HEAD_END)[2].removeprefix("\n")
CASES = ("SINGLE-154", "SINGLE-155")
DESCRIPTIONS = {
    "SINGLE-154": "contextの目的verifyで、文書のverifyが解決したコマンドとタイムアウトをハッシュ値の材料へ収録する",
    "SINGLE-155": "verifyが文書のverifyで解決したコマンドを実行し、検証対象のハッシュ値がSINGLE-154と一致する",
}
LEDGER_STATEMENT = {
    "id": STATEMENT, "documentId": "REQ-001", "documentRole": "root", "modality": "MUST", "reason": None,
    "actor": "TargetSystem", "activation": {"kind": "ALWAYS"},
    "operation": {"kind": "CONSTRAINT", "text": "秘密情報を出力しない"},
}


def reviewed_inputs(identifier):
    return {
        CONFIG_PATH: digest_reference.CONFIG.encode(),
        REQ_PATH: REQUIREMENT.encode(),
        TEST_PATH: digest_reference.CODE_FILES[TEST_PATH].encode(),
    }


def reviewed_manifest(identifier):
    if identifier == "SINGLE-154":
        return {
            "fixtureId": identifier, "description": DESCRIPTIONS[identifier],
            "setup": {"git": True, "operations": []},
            "invocation": {"runner": "bitz", "cwd": ".",
                           "argv": ["context", "REQ-001", "--purpose", "verify", "--format", "json"], "env": {}},
            "expect": {"status": "passed", "exitCode": 0, "stdout": "json",
                       "resultFile": "expected/context.json", "reportFileCount": 0},
        }
    # `verify`は、インデックスで追跡されている設定がないと起動を遮断する（`VERIFY-CONFIG-UNTRACKED`）。
    return {
        "fixtureId": identifier, "description": DESCRIPTIONS[identifier],
        "setup": {"git": True, "operations": [{"op": "stage", "paths": ["."]}]},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": ["verify", "REQ-001", "--format", "json"], "env": {}},
        "expect": {"status": "passed", "exitCode": 0, "stdout": "json",
                   "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


def reviewed_digest_input():
    """ハッシュ値の材料（参照計算A）。`commands`と`verifyTimeouts`は、文書の`verify`が解決した`default`から作る。"""
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": "verify", "requestWorkspaceId": "root", "roots": ["REQ-001"],
        "workspaces": [{"id": "root", "path": "."}],
        "documents": [{
            "id": "REQ-001", "workspaceId": "root", "kind": "requirement", "status": "approved",
            "applicability": "applicable",
            "frontmatter": {"id": "REQ-001", "title": "文書の検査", "status": "approved",
                            "relations": dict(digest_reference.EMPTY_RELATIONS), "implements": [],
                            "tests": [{"path": TEST_PATH, "covers": [STATEMENT], "command": None}],
                            "verify": "default", "changes": []},
            "bodyText": BODY_TEXT,
            "statements": [{"id": STATEMENT, "actor": "TargetSystem", "activation": {"kind": "ALWAYS", "text": None},
                            "modality": "MUST", "reason": None,
                            "operation": {"kind": "CONSTRAINT", "text": "秘密情報を出力しない"}, "extensions": []}],
            "strongRelations": [],
        }],
        "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [{"id": "root", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [{"workspaceId": "root", "timeoutSeconds": 300}],
            "commands": [{"workspaceId": "root", "name": "default", "argv": ["/bin/true", "{tests}"], "cwd": "."}],
        },
    }


def literal_digest():
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input()))


def reviewed_context_result(context_digest):
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "passed", "purpose": "verify",
        "workspace": {"id": "root", "path": "."}, "roots": ["REQ-001"],
        "contextDigest": context_digest, "revision": None,
        "resolution": {"complete": True, "documentCount": 1, "unresolvedStrongRelations": 0},
        "projection": {"detail": "standard", "expanded": []},
        "documents": [{
            "id": "REQ-001", "kind": "requirement", "status": "approved", "role": "root", "path": REQ_PATH,
            "projection": "full", "reachedBy": ["root"], "statementRefs": [STATEMENT],
            # 結果のフロントマターはnullと空配列を省略する（`command`のないテスト対応は`command`を持たない）。
            "frontmatter": {"id": "REQ-001", "title": "文書の検査", "status": "approved",
                            "tests": [{"path": TEST_PATH, "covers": [STATEMENT]}], "verify": "default"},
            "bodyText": BODY_TEXT, "untrustedText": True,
        }],
        "constraintLedger": {"statements": [copy.deepcopy(LEDGER_STATEMENT)]},
        # 目的`verify`ではTASKが閉包に入らないので`addressed`は空、`unaddressed`は対象規範文のすべてである。
        "coverage": {"must": {"total": [STATEMENT], "addressed": [], "tested": [STATEMENT],
                              "unaddressed": [STATEMENT], "untested": []},
                     "should": dict(EMPTY_BUCKET), "may": dict(EMPTY_BUCKET), "adjacent": []},
        "durationMs": 0,
        "diagnostics": [],
    }


def reviewed_verify_result(context_digest):
    return {
        "schemaVersion": "1.0", "operation": "verify", "status": "passed", "scope": "selected",
        "workspace": {"id": "root", "path": "."},
        "targetResults": [{"target": "REQ-001", "status": "passed", "contextDigest": context_digest,
                           "statements": [STATEMENT], "bindingRefs": ["root::default"], "diagnostics": []}],
        "revision": None,
        "commands": [{
            "bindingId": "root::default", "workspaceId": "root", "name": "default", "status": "passed",
            "termination": "exit", "cwd": ".", "argv": ["/bin/true", TEST_PATH], "tests": [TEST_PATH],
            "covers": [STATEMENT], "exitCode": 0, "timeoutSeconds": 300,
            "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False, "stderrTruncated": False,
            "durationMs": 0}],
        "durationMs": 0,
        "diagnostics": [],
    }


def reviewed_result(identifier, context_digest):
    return reviewed_context_result(context_digest) if identifier == "SINGLE-154" else reviewed_verify_result(context_digest)


def result_name(identifier):
    return "context" if identifier == "SINGLE-154" else "verify"


def references(repository):
    """同じハッシュ値の材料を、独立に書いた2系統で計算し、バイト列の一致を要求する。"""
    literal = digest_reference.canonical_bytes(reviewed_digest_input())
    derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository, "REQ-001", "verify"))
    if literal != derived:
        raise ValueError("参照計算AとBの正規JSONが一致しません")
    if digest_reference.digest(literal) != digest_crosscheck.digest(derived):
        raise ValueError("参照計算AとBのハッシュ値が一致しません")
    return literal


def check_settings_material(canonical):
    """材料の`commands`が`root::default`の1件、`verifyTimeouts`が`root`の1件（既定値300）であることを、バイト列から確かめる。"""
    settings = json.loads(canonical.decode("utf-8"))["settings"]
    if settings["commands"] != [{"workspaceId": "root", "name": "default", "argv": ["/bin/true", "{tests}"], "cwd": "."}]:
        raise ValueError("材料の`commands`が、文書の`verify`で解決した`default`の1件ではありません")
    if settings["verifyTimeouts"] != [{"workspaceId": "root", "timeoutSeconds": 300}]:
        raise ValueError("材料の`verifyTimeouts`が、`root`の既定値の1件ではありません")


def check_conditions(inputs):
    """単一の原因を、散文からではなく固定したバイト列から確かめる。"""
    frontmatter, _ = digest_crosscheck.split_document(inputs[REQ_PATH].decode())
    if frontmatter.get("verify") != "default":
        raise ValueError("文書の`verify`が`default`ではありません")
    tests = frontmatter.get("tests")
    if not tests or any("command" in test for test in tests):
        raise ValueError("テスト対応は`command`を持ってはいけません（コマンド名は文書の`verify`だけが与える）")
    config = digest_crosscheck.read_yaml(inputs[CONFIG_PATH].decode())
    if sorted(config["verify"]["commands"]) != ["default"] or "timeoutSeconds" in config["verify"]:
        raise ValueError("設定は`default`だけを定義し、タイムアウトを指定してはいけません（既定値を使う）")


def check_resolution_is_exercised(repository, canonical):
    """文書の`verify`を取り除くと材料の`commands`と`verifyTimeouts`が空になり、正規JSONが変わる（解決がこの入力で効いている）。"""
    with tempfile.TemporaryDirectory(prefix="bitz-digest-command-") as temporary:
        stripped = Path(temporary) / "repo"
        shutil.copytree(repository, stripped, ignore=shutil.ignore_patterns(".git"))
        path = stripped / REQ_PATH
        text = path.read_text(encoding="utf-8")
        if "verify: default\n" not in text:
            raise ValueError("入力に文書の`verify`がありません")
        path.write_text(text.replace("verify: default\n", "", 1), encoding="utf-8")
        derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(stripped, "REQ-001", "verify"))
    settings = json.loads(derived.decode("utf-8"))["settings"]
    if derived == canonical or settings["commands"] or settings["verifyTimeouts"]:
        raise ValueError("文書の`verify`を取り除いても材料が変わらないか、コマンドが残っています")


def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    canonical = None
    for identifier in CASES:
        fixture = root / "single" / identifier
        inputs, manifest = reviewed_inputs(identifier), reviewed_manifest(identifier)
        for name, content in inputs.items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        if identifier == "SINGLE-154":
            with tempfile.TemporaryDirectory(prefix="bitz-digest-command-") as temporary:
                repository = Path(temporary) / "repo"
                shutil.copytree(fixture / "repo", repository)
                canonical = references(repository)
            (fixture / "expected/context.canonical.json").write_bytes(canonical)
        digest = digest_reference.digest(canonical)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / f"expected/{result_name(identifier)}.json").write_text(_dump(reviewed_result(identifier, digest)))
        with tempfile.TemporaryDirectory(prefix="bitz-digest-command-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(
            _dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


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
            name = result_name(identifier)
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / f"expected/{name}.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for kind, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[kind].validate(value)
            canonical_path = root / "single/SINGLE-154/expected/context.canonical.json"
            canonical = canonical_path.read_bytes()
            if canonical.startswith(b"\xef\xbb\xbf") or canonical.endswith(b"\n"):
                raise ValueError("正規JSONはBOMも末尾改行も持ってはいけません")
            if identifier == "SINGLE-155" and (fixture / "expected/context.canonical.json").exists():
                raise ValueError("`verify`のfixtureは正規JSONを持たず、`SINGLE-154`の正規JSONを共有する")
            digest = digest_reference.digest(canonical)
            check_settings_material(canonical)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier, digest):
                raise ValueError("起動条件または完全結果がレビュー済みの期待値と異なります")
            inputs = reviewed_inputs(identifier)
            check_conditions(inputs)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[file]
                                                for file, p in files.items()):
                raise ValueError("入力がレビュー済みの期待値と異なります")
            frontmatter, _ = digest_crosscheck.split_document(inputs[REQ_PATH].decode())
            Draft202012Validator({"$ref": "#/$defs/reqFrontmatter", "$defs": schema["$defs"]}).validate(frontmatter)
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-digest-command-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    if identifier == "SINGLE-154":
                        check_unborn(repository, inputs)
                    else:
                        tracked = subprocess.run(["git", "ls-files", "--", CONFIG_PATH], cwd=repository,
                                                 capture_output=True, text=True, timeout=10).stdout.strip()
                        if tracked != CONFIG_PATH:
                            raise ValueError("`verify`にはインデックスで追跡されている設定が必要です")
                    external = {key: sandbox / key for key in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
                    if references(repository) != canonical:
                        raise ValueError("コミットした正規JSONが参照計算と異なります")
                    check_resolution_is_exercised(repository, canonical)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
