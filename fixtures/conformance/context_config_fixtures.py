"""`context`が設定の不適合・不在・警告をどう返すかを固定するレビュー済みの入力と期待値（Coreの公開操作は実行しない）。

`SINGLE-150`〜`152`は、設定の不適合と不在で`context`が停止する結果を固定する。`SINGLE-153`は、設定の警告
（`SPEC-CONFIG-UNKNOWN-001`）が、成功した`context`の結果へ加わることを固定する。`check`と`verify`が返す診断と同じ値を返す
（診断レジストリは設定の診断の`operations`を`all`、不在を`context, check, verify`とする）。

- `SINGLE-150`（型の不正）と`SINGLE-151`（値の範囲外）は、診断レジストリの同じ行`CONFIG-FIELD-TYPE`である。
  `SPEC-CONFIG-SCHEMA-001`（`error`、`stop-operation`）を返し、`SPEC-WORKSPACE-MISSING-001`は返さない。
- `SINGLE-152`は`WORKSPACE-CONFIG-MISSING`（`blocked`、発生元`environment`）である。
- `SINGLE-153`の`contextDigest`は、独立に書いた2系統の参照計算（digest_referenceのリテラルA、digest_crosscheckの木構造からの導出B）で
  照合する。未知の標準キーは、正規化仕様 §3.3の許可リストにないので、ハッシュ値の材料へ入らない。
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference
from .document_fixtures import DOCUMENT, REQ_PATH
from .harness import git, setup
from .initial_fixtures import CONFIGS, observe, compare_state

HERE = Path(__file__).resolve().parent
CONFIG_PATH = ".spec/bitz.yaml"
EXIT = {"passed": 0, "passed_with_warnings": 0, "failed": 1, "blocked": 2, "error": 3}
# 設定の標準のキー（ワークスペース・設定仕様 §5）。`futureOption`はここにない。
STANDARD_KEYS = {"schemaVersion", "language", "earsAi", "context", "verify", "safety", "workspace", "multiWorkspace"}
RANGE_CONFIG = CONFIGS["SINGLE-001"] + "context:\n  maxBytes: 100\n"
BODY_TEXT = (
    "# REQ-001 文書の検査\n\n"
    "## Intent\n\n文書構造を検査する。\n\n"
    "## Acceptance Criteria\n\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n\n"
    "## Verification\n\nCore実装後に確認する。現時点では未証明。\n"
)
EMPTY_BUCKET = {"total": [], "addressed": [], "tested": [], "unaddressed": [], "untested": []}


def config_source(workspace, key):
    return {"kind": "file", "workspaceId": workspace, "path": CONFIG_PATH, "key": key}


# 要約は規範文を持たない。SINGLE-004-01、SINGLE-005-01、SINGLE-094のレビュー済みの文言を再利用する。
# SINGLE-151だけは、同じ形（`<key>は<期待する型>で指定してください`）で値の範囲を書く。
CASES = {
    "SINGLE-150": {
        "status": "error", "config": CONFIGS["SINGLE-004-01"], "workspace": None,
        "code": "SPEC-CONFIG-SCHEMA-001", "severity": "error", "summary": "languageはstringで指定してください",
        "source": config_source(None, "language"),
        "description": "contextで設定の型不正を設定の診断で返しハッシュ値を計算しない"},
    "SINGLE-151": {
        "status": "error", "config": RANGE_CONFIG, "workspace": None,
        "code": "SPEC-CONFIG-SCHEMA-001", "severity": "error",
        "summary": "context.maxBytesは4096〜1048576のintegerで指定してください",
        "source": config_source(None, "context.maxBytes"),
        "description": "contextで設定の値の範囲外を設定の診断で返しハッシュ値を計算しない"},
    "SINGLE-152": {
        "status": "blocked", "config": None, "workspace": None,
        "code": "SPEC-WORKSPACE-MISSING-001", "severity": "error", "summary": ".spec/bitz.yamlがありません",
        "source": {"kind": "environment", "component": "workspace", "identifier": "."},
        "description": "contextで設定の不在をワークスペースの不在としてenvironmentの発生元で止める"},
    "SINGLE-153": {
        "status": "passed_with_warnings", "config": CONFIGS["SINGLE-005-01"], "workspace": "root",
        "code": "SPEC-CONFIG-UNKNOWN-001", "severity": "warning", "summary": "未知の設定keyです",
        "source": config_source("root", "futureOption"),
        "description": "contextの成功の結果に設定の未知のキーの警告を加える"},
}


def reviewed_inputs(identifier):
    config = CASES[identifier]["config"]
    # REQ-001は有効で存在する。設定だけが唯一の原因であり、起点の不在などが混ざらない。
    return {**({CONFIG_PATH: config.encode()} if config is not None else {}), REQ_PATH: DOCUMENT.encode()}


def reviewed_manifest(identifier):
    status = CASES[identifier]["status"]
    return {"fixtureId": identifier, "description": CASES[identifier]["description"],
            "setup": {"git": True, "operations": []},
            "invocation": {"runner": "bitz", "cwd": ".", "argv": ["context", "REQ-001", "--format", "json"], "env": {}},
            "expect": {"status": status, "exitCode": EXIT[status], "stdout": "json",
                       "resultFile": "expected/context.json", "reportFileCount": 0}}


def reviewed_result(identifier, context_digest=None):
    case = CASES[identifier]
    succeeded = case["status"] == "passed_with_warnings"
    document = {
        "id": "REQ-001", "kind": "requirement", "status": "approved", "role": "root", "path": REQ_PATH,
        "projection": "full", "reachedBy": ["root"], "statementRefs": ["REQ-001:AC-01"],
        "frontmatter": {"id": "REQ-001", "title": "文書の検査", "status": "approved"},
        "bodyText": BODY_TEXT, "untrustedText": True,
    }
    return {
        "schemaVersion": "1.0", "operation": "context", "status": case["status"], "purpose": "interpret",
        "workspace": {"id": case["workspace"], "path": "."}, "roots": ["REQ-001"],
        "contextDigest": context_digest if succeeded else None, "revision": None,
        "resolution": {"complete": succeeded, "documentCount": 1 if succeeded else 0, "unresolvedStrongRelations": 0},
        "projection": {"detail": "standard", "expanded": []},
        "documents": [document] if succeeded else [],
        # 目的`interpret`は対象規範文を持たない（関係・トレースモデル §6.4）ので、制約台帳とカバレッジは空である。
        "constraintLedger": {"statements": []},
        "coverage": {"must": dict(EMPTY_BUCKET), "should": dict(EMPTY_BUCKET), "may": dict(EMPTY_BUCKET), "adjacent": []},
        "durationMs": 0,
        "diagnostics": [{"code": case["code"], "severity": case["severity"], "resultStatus": case["status"],
                         "summary": case["summary"], "source": case["source"]}],
    }


def reviewed_digest_input():
    """`SINGLE-153`のハッシュ値の材料（参照計算A）。`futureOption`は許可リストにないので、どこにも現れない。"""
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": "interpret", "requestWorkspaceId": "root", "roots": ["REQ-001"],
        "workspaces": [{"id": "root", "path": "."}],
        "documents": [{
            "id": "REQ-001", "workspaceId": "root", "kind": "requirement", "status": "approved",
            "applicability": "applicable",
            "frontmatter": {"id": "REQ-001", "title": "文書の検査", "status": "approved",
                            "relations": dict(digest_reference.EMPTY_RELATIONS), "implements": [], "tests": [],
                            "verify": None, "changes": []},
            "bodyText": BODY_TEXT,
            "statements": [{"id": "REQ-001:AC-01", "actor": "TargetSystem", "activation": {"kind": "ALWAYS", "text": None},
                            "modality": "MUST", "reason": None,
                            "operation": {"kind": "CONSTRAINT", "text": "秘密情報を出力しない"}, "extensions": []}],
            "strongRelations": [],
        }],
        "crossWorkspaceEdges": [],
        "settings": {"workspaces": [{"id": "root", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
                     "context": {"maxDocuments": 20, "maxBytes": 131072}, "verifyTimeouts": [], "commands": []},
    }


def references(repository):
    """同じハッシュ値の材料を、独立に書いた2系統で計算し、バイト列の一致を要求する。"""
    literal = digest_reference.canonical_bytes(reviewed_digest_input())
    derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository, "REQ-001", "interpret"))
    if literal != derived:
        raise ValueError("参照計算AとBの正規JSONが一致しません")
    if digest_reference.digest(literal) != digest_crosscheck.digest(derived):
        raise ValueError("参照計算AとBのハッシュ値が一致しません")
    return literal


def check_digest_ignores_unknown_key(repository, canonical):
    """未知の標準キーを除いた設定から導いた正規JSONが、同じバイト列になる（許可リストの外のキーは材料へ入らない）。"""
    with tempfile.TemporaryDirectory(prefix="bitz-context-config-") as temporary:
        clean = Path(temporary) / "repo"
        shutil.copytree(repository, clean, ignore=shutil.ignore_patterns(".git"))
        (clean / CONFIG_PATH).write_bytes(CONFIGS["SINGLE-001"].encode())
        if digest_crosscheck.canonical_bytes(digest_crosscheck.build(clean, "REQ-001", "interpret")) != canonical:
            raise ValueError("未知のキーがハッシュ値の材料に影響しています")


def check_conditions(identifier, inputs):
    """各単一原因を、散文からではなく固定したバイト列から確かめる。"""
    config = inputs.get(CONFIG_PATH)
    if identifier == "SINGLE-150" and config != CONFIGS["SINGLE-004-01"].encode():
        raise ValueError("型不正のケースはSINGLE-004-01のレビュー済みの入力を再利用する必要があります")
    if identifier == "SINGLE-151":
        extra = config.decode().removeprefix(CONFIGS["SINGLE-001"]) if config else ""
        if extra != "context:\n  maxBytes: 100\n":
            raise ValueError("値の範囲のケースは、最小の設定と`context.maxBytes: 100`だけが異なる必要があります（下限は4,096）")
    if identifier == "SINGLE-152" and (CONFIG_PATH in inputs or set(inputs) != {REQ_PATH}):
        raise ValueError("設定不在のケースは、設定を置かず、有効なREQ-001だけを置く必要があります")
    if identifier == "SINGLE-153":
        extra = config.decode().removeprefix(CONFIGS["SINGLE-001"]) if config else ""
        key = extra.split(":", 1)[0]
        if extra != CONFIGS["SINGLE-005-01"].removeprefix(CONFIGS["SINGLE-001"]) or key in STANDARD_KEYS or key == "profiles":
            raise ValueError("警告のケースは、最小の設定と標準でないキー1つだけが異なる必要があります")
    if identifier != "SINGLE-152" and CONFIG_PATH not in inputs:
        raise ValueError("設定を置くケースに設定がありません")


def check_unborn(repository, inputs):
    git(repository, "rev-parse", "--git-dir")
    if git(repository, "symbolic-ref", "HEAD").decode().strip() != "refs/heads/fixture":
        raise ValueError("コミットのないリポジトリのブランチが想定と異なります")
    try:
        git(repository, "rev-parse", "--verify", "HEAD")
    except subprocess.CalledProcessError:
        pass
    else:
        raise ValueError("`context`操作のfixtureに想定外のコミットがあります")
    if git(repository, "for-each-ref") or git(repository, "ls-files", "-z"):
        raise ValueError("`context`操作のfixtureはGitの参照もステージ済みのパスも持ってはいけません")
    actual = {p.relative_to(repository).as_posix(): p.read_bytes() for p in repository.rglob("*")
              if p.is_file() and ".git" not in p.relative_to(repository).parts}
    if actual != inputs:
        raise ValueError("`context`操作のfixtureの作業ツリーがレビュー済みの入力と異なります")


def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = root / "single" / identifier
        inputs, manifest = reviewed_inputs(identifier), reviewed_manifest(identifier)
        for name, content in inputs.items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        digest = None
        if identifier == "SINGLE-153":
            with tempfile.TemporaryDirectory(prefix="bitz-context-config-") as temporary:
                repository = Path(temporary) / "repo"
                shutil.copytree(fixture / "repo", repository)
                canonical = references(repository)
            (fixture / "expected").mkdir(parents=True, exist_ok=True)
            (fixture / "expected/context.canonical.json").write_bytes(canonical)
            digest = digest_reference.digest(canonical)
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected/context.json").write_text(_dump(reviewed_result(identifier, digest)))
        with tempfile.TemporaryDirectory(prefix="bitz-context-config-") as temporary:
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
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/context.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            digest = None
            if identifier == "SINGLE-153":
                canonical = (fixture / "expected/context.canonical.json").read_bytes()
                if canonical.startswith(b"\xef\xbb\xbf") or canonical.endswith(b"\n"):
                    raise ValueError("正規JSONはBOMも末尾改行も持ってはいけません")
                digest = digest_reference.digest(canonical)
            elif (fixture / "expected/context.canonical.json").exists():
                raise ValueError("ハッシュ値を計算しない結果は正規JSONを持ってはいけません")
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier, digest):
                raise ValueError("起動条件または完全結果がレビュー済みの単一原因と異なります")
            inputs = reviewed_inputs(identifier)
            check_conditions(identifier, inputs)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("入力がレビュー済みの単一原因と異なります")
            frontmatter, _ = digest_crosscheck.split_document(inputs[REQ_PATH].decode())
            Draft202012Validator({"$ref": "#/$defs/reqFrontmatter", "$defs": schema["$defs"]}).validate(frontmatter)
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-context-config-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    check_unborn(repository, inputs)
                    external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
                    if identifier == "SINGLE-153":
                        if references(repository) != canonical:
                            raise ValueError("コミットした正規JSONが参照計算と異なります")
                        check_digest_ignores_unknown_key(repository, canonical)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
