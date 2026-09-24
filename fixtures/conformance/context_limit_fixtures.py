"""Context非成功を固定するreview済みvector: staleなDigest、集合外のexpand、閉包の上限。

Core操作を実装も模倣もしない。これらのfixtureはDigestの入力を共有し、Digestを返す場合は
別に作った定数ではなく、commitしたgoldenの値を返す。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_reference
from .harness import setup
from .initial_fixtures import observe, compare_state

HERE = Path(__file__).resolve().parent
GOLDEN = digest_reference.digest(
    digest_reference.canonical_bytes(digest_reference.reviewed_digest_input("SINGLE-042")))
WRONG_DIGEST = "sha256:" + "0" * 64
ROOT_DOCUMENT = ".spec/requirements/REQ-001.md"
EMPTY_COVERAGE = {
    **{modality: {key: [] for key in ("total", "addressed", "tested", "unaddressed", "untested")}
       for modality in ("must", "should", "may")},
    "adjacent": [],
}
# 4 KiBは設定できるcontext.maxBytesの最小値なので、詰め物は標準の提示をこれより
# 大きくすればよく、既定の128 KiBを越える必要はない。
PADDING_LINE = "この段落は標準提示のbyte数を上限検査のために増やす固定文である。\n"
PADDING = PADDING_LINE * 40

# id: (optionの残り, 追加の設定, REQの本文, status, 終了コード, complete, documentCount,
#      digest, Diagnostic code, source, summary)
CASES = {
    "SINGLE-046": (
        ["--expect-digest", WRONG_DIGEST], "", digest_reference.REQ_BODY,
        "blocked", 2, True, 2, GOLDEN, "CTX-STALE-001",
        {"kind": "invocation", "argument": "--expect-digest"},
        "期待Digestが現在のContext Digestと一致しません"),
    "SINGLE-047": (
        ["--expand", "ADR-001"], "", digest_reference.REQ_BODY,
        "failed", 1, True, 2, GOLDEN, "CTX-PROJECTION-001",
        {"kind": "invocation", "argument": "ADR-001"},
        "expand対象ADR-001は完全解決集合にありません"),
    "SINGLE-048-01": (
        [], "context:\n  maxDocuments: 1\n", digest_reference.REQ_BODY,
        "blocked", 2, False, 0, None, "CTX-LIMIT-001",
        {"kind": "file", "workspaceId": "root", "path": ROOT_DOCUMENT},
        "完全Context閉包が文書数上限を超過しました"),
    "SINGLE-048-02": (
        [], "context:\n  maxBytes: 4096\n",
        digest_reference.REQ_BODY.replace(
            "Digest goldenの固定要求を定義する。\n", "Digest goldenの固定要求を定義する。\n\n" + PADDING, 1),
        "blocked", 2, False, 0, None, "CTX-LIMIT-001",
        {"kind": "file", "workspaceId": "root", "path": ROOT_DOCUMENT},
        "完全Context閉包がbyte上限を超過しました"),
}
DESCRIPTIONS = {
    "SINGLE-046": "expect-digest不一致でstaleを検出し新しい仕様を暗黙受諾しない",
    "SINGLE-047": "解決集合外のexpandを拒否し依存へ追加しない",
    "SINGLE-048-01": "完全閉包の文書数上限超過で部分Bundleを返さない",
    "SINGLE-048-02": "完全閉包のbyte上限超過で部分Bundleを返さない",
}


def reviewed_inputs(identifier):
    _, extra_config, req_body, *_ = CASES[identifier]
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    inputs[digest_reference.CONFIG_PATH] = (digest_reference.CONFIG + extra_config).encode()
    inputs[digest_reference.REQ_PATH] = (digest_reference.REQ_HEAD + "\n" + req_body).encode()
    return inputs


def reviewed_manifest(identifier):
    tail, _, _, status, exit_code, *_ = CASES[identifier]
    return {
        "fixtureId": identifier,
        "description": DESCRIPTIONS[identifier],
        "setup": {"git": True, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".",
                       "argv": ["context", "REQ-001", "--purpose", "verify", *tail, "--format", "json"],
                       "env": {}},
        "expect": {"status": status, "exitCode": exit_code, "stdout": "json",
                   "resultFile": "expected/context.json", "reportFileCount": 0},
    }


def reviewed_result(identifier):
    (_, _, _, status, _, complete, count, digest, code, source, summary) = CASES[identifier]
    return {
        "schemaVersion": "1.0", "operation": "context", "status": status, "purpose": "verify",
        "workspace": {"id": "root", "path": "."},
        "roots": ["REQ-001"],
        "contextDigest": digest,
        "revision": None,
        "resolution": {"complete": complete, "documentCount": count, "unresolvedStrongRelations": 0},
        "projection": {"detail": "standard", "expanded": []},
        "documents": [],
        "constraintLedger": {"statements": []},
        "coverage": json.loads(json.dumps(EMPTY_COVERAGE)),
        "durationMs": 0,
        "diagnostics": [{"code": code, "severity": "error", "resultStatus": status,
                         "summary": summary, "source": source}],
    }


def check_presentation_size(identifier, inputs):
    """設定した上限は、fixture自身の入力で実際に越えなければならない。
    そうすれば、期待値がbyteの数え方の寛容さに依存しない。"""
    _, extra_config, *_ = CASES[identifier]
    if identifier == "SINGLE-048-01":
        documents = [name for name in inputs if name.startswith(".spec/") and name.endswith(".md")]
        if len(documents) <= 1:
            raise ValueError("文書数のcaseには設定上限より多くの文書が必要です")
    if identifier == "SINGLE-048-02":
        presented = len(inputs[digest_reference.REQ_PATH]) + len(inputs[digest_reference.TECH_PATH])
        if presented <= 4096:
            raise ValueError("byte上限のcaseが設定したmaxBytesを超えていません")
    if identifier in {"SINGLE-046", "SINGLE-047"} and extra_config:
        raise ValueError("staleとprojectionのcaseはgoldenの設定を保つ必要があります")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
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
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("起動条件または完全結果が審査済み期待値と異なります")
            if result["documents"] or result["constraintLedger"]["statements"]:
                raise ValueError("非成功のContextはBundleの材料を返してはいけません")
            if (result["contextDigest"] is None) is result["resolution"]["complete"]:
                raise ValueError("Digestの有無は完全解決に従う必要があります")
            inputs = reviewed_inputs(identifier)
            check_presentation_size(identifier, inputs)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("read-only期待値が書込みを許しています")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-context-limit-") as temporary:
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
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
