"""提示のhard limitを固定するreview済みvector（Core操作は実行しない）。

`SINGLE-049`は設定した閉包の上限内で完全に解決し、`--detail full`では固定した1 MiBの
提示hard limitを超えるという理由だけで失敗する。標準の提示は小さく保ち、fullの提示だけが
上限を越えるようにcorpusを作る。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference
from .context_limit_fixtures import EMPTY_COVERAGE
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
IDENTIFIER = "SINGLE-049"
HARD_LIMIT_BYTES = 1048576
# 閉包の2つの次元を最大値に設定して閉包を通過させ、
# 固定した提示のhard limitだけを越え得るようにする。
CONFIG = digest_reference.CONFIG + "context:\n  maxDocuments: 100\n  maxBytes: 1048576\n"
REQ_HEAD = "---\nid: REQ-001\ntitle: 提示量の基準\nstatus: approved\n---\n"
REQ_BODY = (
    "# REQ-001 提示量の基準\n"
    "\n"
    "## Intent\n"
    "\n"
    "提示hard limitの検査に使う固定要求を定義する。\n"
    "\n"
    "## Acceptance Criteria\n"
    "\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n"
    "\n"
    "## Verification\n"
    "\n"
    "提示量の上限で確認する。\n"
)
PAD_LINE = "この段落は提示hard limitを超えるための固定本文であり、意味を持たない。\n"
# 間接の2件のrefinementの本文が合わせて1 MiBを超え、
# 各fileは1文書あたり1 MiBの入力上限を下回るように選んだ。
PAD_REPEAT = 5300
SMALL_TECH_BODY = "# TECH-001 直接の具体化\n\n## Context\n\n距離1の具体化。\n"


def large_body(number, title):
    return f"# TECH-{number:03} {title}\n\n## Context\n\n{PAD_LINE * PAD_REPEAT}"


DOCUMENTS = {
    ".spec/technical/TECH-001.md": ("TECH-001", "直接の具体化", "REQ-001", SMALL_TECH_BODY),
    ".spec/technical/TECH-002.md": ("TECH-002", "間接の具体化", "TECH-001", large_body(2, "間接の具体化")),
    ".spec/technical/TECH-003.md": ("TECH-003", "さらに間接の具体化", "TECH-002", large_body(3, "さらに間接の具体化")),
}
ORDER = ["REQ-001", "TECH-001", "TECH-002", "TECH-003"]


def technical_document(path):
    identifier, title, target, body = DOCUMENTS[path]
    return (f"---\nid: {identifier}\ntitle: {title}\nstatus: approved\n"
            f"relations:\n  refines: [{target}]\n---\n\n" + body)


def reviewed_inputs():
    inputs = {digest_reference.CONFIG_PATH: CONFIG.encode(),
              digest_reference.REQ_PATH: (REQ_HEAD + "\n" + REQ_BODY).encode()}
    for path in DOCUMENTS:
        inputs[path] = technical_document(path).encode()
    return inputs


def reviewed_digest_input():
    documents = [{
        "id": "REQ-001", "workspaceId": "root", "kind": "requirement", "status": "approved",
        "applicability": "applicable",
        "frontmatter": {"id": "REQ-001", "title": "提示量の基準", "status": "approved",
                        "relations": dict(digest_reference.EMPTY_RELATIONS), "implements": [],
                        "tests": [], "verify": None, "changes": []},
        "bodyText": REQ_BODY,
        "statements": [dict(digest_reference.STATEMENTS[0])],
        "strongRelations": [],
    }]
    for path in DOCUMENTS:
        identifier, title, target, body = DOCUMENTS[path]
        documents.append({
            "id": identifier, "workspaceId": "root", "kind": "technical", "status": "approved",
            "applicability": "applicable",
            "frontmatter": {"id": identifier, "title": title, "status": "approved",
                            "relations": {**digest_reference.EMPTY_RELATIONS, "refines": [target]},
                            "implements": [], "tests": [], "verify": None, "changes": []},
            "bodyText": body, "statements": [],
            "strongRelations": [{"relation": "refines", "target": target}],
        })
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0",
        "resolverVersion": "1.0", "purpose": "verify", "requestWorkspaceId": "root",
        "roots": ["REQ-001"], "workspaces": [{"id": "root", "path": "."}],
        "documents": documents, "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [{"id": "root", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
            "context": {"maxDocuments": 100, "maxBytes": 1048576},
            "verifyTimeouts": [], "commands": [],
        },
    }


def reviewed_manifest():
    return {
        "fixtureId": IDENTIFIER,
        "description": "detailによる提示量が1 MiBのhard limitを超過する",
        "setup": {"git": True, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["context", "REQ-001", "--purpose", "verify", "--detail", "full",
                                "--format", "json"],
                       "env": {}},
        "expect": {"status": "failed", "exitCode": 1, "stdout": "json",
                   "resultFile": "expected/context.json", "reportFileCount": 0},
    }


def reviewed_result(context_digest):
    return {
        "schemaVersion": "1.0", "operation": "context", "status": "failed", "purpose": "verify",
        "workspace": {"id": "root", "path": "."},
        "roots": ["REQ-001"],
        "contextDigest": context_digest,
        "revision": None,
        "resolution": {"complete": True, "documentCount": 4, "unresolvedStrongRelations": 0},
        # `detail`は要求したmodeを示し、`expanded`は実際に適用したものを並べる。
        "projection": {"detail": "full", "expanded": []},
        "documents": [],
        "constraintLedger": {"statements": []},
        "coverage": json.loads(json.dumps(EMPTY_COVERAGE)),
        "durationMs": 0,
        "diagnostics": [{
            "code": "CTX-PROJECTION-LIMIT-001", "severity": "error", "resultStatus": "failed",
            "summary": "detail fullの提示量が1 MiBのhard limitを超過します",
            "source": {"kind": "invocation", "argument": "--detail"},
        }],
    }


def check_limits(inputs):
    """corpusは`--detail full`のときだけ提示のhard limitを越えなければならない。
    大きな本文は、`standard`では`normative`、`full`では`full`で提示する。"""
    bodies = {"REQ-001": REQ_BODY, **{DOCUMENTS[path][0]: DOCUMENTS[path][3] for path in DOCUMENTS}}
    full = sum(len(body.encode()) for body in bodies.values())
    standard = sum(len(bodies[identifier].encode()) for identifier in ("REQ-001", "TECH-001"))
    if full <= HARD_LIMIT_BYTES:
        raise ValueError("fullの提示が1 MiBのhard limitを超えていません")
    if standard >= HARD_LIMIT_BYTES:
        raise ValueError("標準の提示はhard limit内に収まる必要があります")
    for path, payload in inputs.items():
        if path.endswith(".md") and len(payload) >= HARD_LIMIT_BYTES:
            raise ValueError("SPEC file 1件は1 MiBの入力上限を下回る必要があります")
    if len(bodies) > 100:
        raise ValueError("文書数は設定した閉包の上限内に収まる必要があります")


def validate(root=HERE, identifiers=None):
    if identifiers is not None and IDENTIFIER not in identifiers:
        return {"prepared": [], "setups_per_fixture": 2, "core_execution": "Not run",
                "status": "Passed", "errors": []}
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    fixture = root / "single" / IDENTIFIER
    try:
        manifest = json.loads((fixture / "manifest.json").read_text())
        result = json.loads((fixture / "expected/context.json").read_text())
        effects = json.loads((fixture / "side-effects.json").read_text())
        for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
            validators[name].validate(value)
        canonical = (fixture / "expected/context.canonical.json").read_bytes()
        if canonical.endswith(b"\n") or canonical.startswith(b"\xef\xbb\xbf"):
            raise ValueError("Canonical JSONはBOMと末尾改行のないUTF-8である必要があります")
        if manifest != reviewed_manifest():
            raise ValueError("起動条件が審査済み期待値と異なります")
        if result != reviewed_result(digest_reference.digest(canonical)):
            raise ValueError("完全結果が審査済み期待値と異なります")
        if result["documents"] or result["constraintLedger"]["statements"]:
            raise ValueError("非成功のContextはBundleの材料を返してはいけません")
        inputs = reviewed_inputs()
        check_limits(inputs)
        files = {p.relative_to(fixture / "repo").as_posix(): p
                 for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
        if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                            for name, p in files.items()):
            raise ValueError("入力が審査済みcorpusと異なります")
        if effects["before"] != effects["after"]:
            raise ValueError("read-only期待値が書込みを許しています")
        previous = None
        with tempfile.TemporaryDirectory(prefix="bitz-projection-limit-") as temporary:
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
                literal = digest_reference.canonical_bytes(reviewed_digest_input())
                derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository))
                if literal != derived:
                    raise ValueError("reference AとBのCanonical JSONが一致しません")
                if literal != canonical:
                    raise ValueError("commitしたCanonical JSONが参照計算と異なります")
                order = [document["id"] for document in json.loads(derived.decode())["documents"]]
                if order != ORDER:
                    raise ValueError("Digestの文書がreview済みの順序ではありません")
        prepared.append(IDENTIFIER)
    except (OSError, ValueError, KeyError, TypeError, ValidationError,
            subprocess.SubprocessError) as error:
        errors.append(f"{IDENTIFIER}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
