"""matrix §6.10のcheckのcaseについて、文法・Scanner・位置を固定した証拠。

Scanner、Lexer、Parser、Coreは実装しない。各fixtureはreview済みのEARS文書を再利用し、
ちょうど1行だけを変える。そのため監査は、固定したbyte列から、review済みの
1始まりのコードポイントの列を導き直せる。
"""
import json
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .ears_fixtures import SPEC_PATH, reviewed_document
from .harness import setup
from .initial_fixtures import CONFIGS, observe, compare_state

HERE = Path(__file__).resolve().parent
CONFIG_PATH = ".spec/bitz.yaml"
STATEMENT_LINE = 16
BASE = "- [REQ-001:AC-02] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] "
# 規範文風のtextは1つに固定し、抑止のcaseごとに周りの構文だけを変える。
CANDIDATE = "- [REQ-001:AC-99] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 候補にしない。"
SUPPRESSION = {
    "SINGLE-099-01": "```text\n" + CANDIDATE + "\n```",
    "SINGLE-099-02": "~~~text\n" + CANDIDATE + "\n~~~",
    "SINGLE-099-03": "> " + CANDIDATE,
    "SINGLE-099-04": "    " + CANDIDATE,
}
# ID: (16行目の内容, Diagnostic code, summary, anchor token, review済みの列)
CASES = {
    "SINGLE-096-02": (BASE + "ログに ``secret` を出力しない。", "EAI-CORE-SYNTAX-005",
                      "code spanが閉じられていません", "``", 73),
    "SINGLE-097-02": (BASE + "秘密情報を\\出力しない。", "EAI-CORE-SYNTAX-004",
                      "未知のescapeです", "\\", 74),
    "SINGLE-098-02": ('- [REQ-001:AC-02] [quality:LEVEL="basic] [ACTOR:TargetSystem] [ALWAYS] [MUST] '
                      "[CONSTRAINT] 秘密情報を出力しない。", "EAI-CORE-SYNTAX-004",
                      "extension値のquoteが閉じられていません", '"', 34),
    "SINGLE-099-01": (SUPPRESSION["SINGLE-099-01"], None, None, None, None),
    "SINGLE-099-02": (SUPPRESSION["SINGLE-099-02"], None, None, None, None),
    "SINGLE-099-03": (SUPPRESSION["SINGLE-099-03"], None, None, None, None),
    "SINGLE-099-04": (SUPPRESSION["SINGLE-099-04"], None, None, None, None),
    "SINGLE-100-01": ("- [REQ-01:AC-02] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。",
                      "EAI-CORE-ID-001", "規範文IDの形式が不正です", "[", 3),
    "SINGLE-100-02": ("- [UNKNOWN-001:AC-02] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。",
                      "EAI-CORE-ID-001", "規範文IDの形式が不正です", "[", 3),
    "SINGLE-100-03": ("- [REQ-001:AC-02:R-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。",
                      "EAI-CORE-ID-001", "規範文IDの形式が不正です", "[", 3),
    "SINGLE-100-04": ("- [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。",
                      "EAI-CORE-ID-001", "規範文IDの形式が不正です", "[", 3),
    "SINGLE-101-02": ("- [REQ-001:AC-02] [ACTOR:TargetSystem] [ALWAYS] [MUST] [REASON] 確認のため "
                      "[CONSTRAINT] 秘密情報を出力しない。", "EAI-CORE-SYNTAX-001",
                      "tagの順序が不正です", "[REASON]", 56),
    "SINGLE-101-03": ("- [REQ-001:AC-02] [ACTOR:TargetSystem] [ALWAYS] [MAY] [REASON] 確認のため "
                      "[CONSTRAINT] 秘密情報を出力しない。", "EAI-CORE-SYNTAX-001",
                      "tagの順序が不正です", "[REASON]", 55),
    "SINGLE-102": (BASE + "全角文字と\tタブの後に[未知tagを置かない。", "EAI-CORE-SYNTAX-004",
                   "tagが閉じられていません", "[未知", 80),
    "SINGLE-103-01": (BASE + "ログに `secret [TAG を出力しない。", "EAI-CORE-SYNTAX-005",
                      "code spanが閉じられていません", "`", 73),
    "SINGLE-103-02": ("- [REQ-01:AC-02 [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。",
                      "EAI-CORE-SYNTAX-004", "tagが閉じられていません", "[", 3),
}
DESCRIPTIONS = {
    "SINGLE-096-02": "開始runと同じ終了runがないcode spanを拒否する",
    "SINGLE-097-02": "未知escapeを拒否する",
    "SINGLE-098-02": "未閉鎖のquoted extension値を拒否する",
    "SINGLE-099-01": "backtick fence内の規範文様行を候補にしない",
    "SINGLE-099-02": "tilde fence内の規範文様行を候補にしない",
    "SINGLE-099-03": "引用内の規範文様行を候補にしない",
    "SINGLE-099-04": "4 SP indentの規範文様行を候補にしない",
    "SINGLE-100-01": "桁不足IDを候補化し形式不正として返す",
    "SINGLE-100-02": "未知prefix IDを候補化し形式不正として返す",
    "SINGLE-100-03": "3階層IDを候補化し形式不正として返す",
    "SINGLE-100-04": "ID欠落行を候補化し形式不正として返す",
    "SINGLE-101-02": "MUSTの直後の[REASON]をtag順序不正として返す",
    "SINGLE-101-03": "MAYの直後の[REASON]をtag順序不正として返す",
    "SINGLE-102": "全角文字とTABの後でもcode point単位の位置を返す",
    "SINGLE-103-01": "未閉鎖code spanをprimaryとして1件だけ返す",
    "SINGLE-103-02": "未閉鎖tagをprimaryとして1件だけ返す",
}


def reviewed_inputs(identifier):
    return {CONFIG_PATH: CONFIGS["SINGLE-001"].encode(),
            SPEC_PATH: reviewed_document("approved", CASES[identifier][0]).encode()}


def status_of(identifier):
    return "failed" if CASES[identifier][1] else "passed"


def reviewed_manifest(identifier):
    status = status_of(identifier)
    return {"fixtureId": identifier, "description": DESCRIPTIONS[identifier],
            "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
            "invocation": {"runner": "bitz", "cwd": ".",
                           "argv": ["check", "--full", "--base", "HEAD", "--format", "json"], "env": {}},
            "expect": {"status": status, "exitCode": 1 if status == "failed" else 0, "stdout": "json",
                       "resultFile": "expected/check.json", "reportFileCount": 0}}


def reviewed_result(identifier):
    _, code, summary, _, column = CASES[identifier]
    status = status_of(identifier)
    diagnostics = [] if code is None else [{
        "code": code, "severity": "error", "resultStatus": status, "summary": summary,
        "source": {"kind": "file", "workspaceId": "root", "path": SPEC_PATH,
                   "line": STATEMENT_LINE, "column": column}}]
    return {"schemaVersion": "1.0", "operation": "check", "status": status, "scope": "full",
            "workspace": {"id": "root", "path": "."},
            "revision": {"base": "0" * 40, "commit": "0" * 40, "dirty": False},
            "checkedDocumentCount": 0 if code else 1, "checkedStatementCount": 0 if code else 1,
            "durationMs": 0, "diagnostics": diagnostics}


def check_positions(identifier, document):
    """review済みの列を、固定した文書からコードポイント単位で導き直す。"""
    line_text, code, _, anchor, column = CASES[identifier]
    lines = document.decode().splitlines()
    if lines[STATEMENT_LINE - 1] != line_text.splitlines()[0]:
        raise ValueError("review済みの16行目が固定した文書と異なります")
    if code is None:
        if anchor is not None or column is not None:
            raise ValueError("成功するcaseはDiagnosticの位置を固定してはいけません")
        return
    position = lines[STATEMENT_LINE - 1].index(anchor) + 1
    if position != column:
        raise ValueError("Diagnosticの列がreview済みのtokenを指していません")


def check_suppression(identifier, document):
    """抑止のcaseの間で異なってよいのは、周りの構文だけである。"""
    if identifier not in SUPPRESSION:
        return
    block = SUPPRESSION[identifier].split("\n")
    if identifier in {"SINGLE-099-01", "SINGLE-099-02"}:
        fence = "```" if identifier.endswith("01") else "~~~"
        if block[0] != fence + "text" or block[-1] != fence or block[1] != CANDIDATE or len(block) != 3:
            raise ValueError("fenceのcaseは固定した候補textだけを囲む必要があります")
    elif identifier == "SINGLE-099-03":
        if len(block) != 1 or block[0] != "> " + CANDIDATE:
            raise ValueError("引用のcaseは固定した候補textだけに接頭辞を付ける必要があります")
    elif len(block) != 1 or block[0] != "    " + CANDIDATE or "\t" in block[0]:
        raise ValueError("indentのcaseには、先頭にちょうど4つの空白とTABのないことが必要です")
    text = document.decode()
    if text.count(CANDIDATE) != 1 or SUPPRESSION[identifier] not in text:
        raise ValueError("抑止するtextは、その構文の中にちょうど1回現れる必要があります")


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
            result = json.loads((fixture / "expected/check.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError("manifestまたは結果が審査済みの単一条件と異なります")
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / "repo").as_posix(): p
                     for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name]
                                                for name, p in files.items()):
                raise ValueError("入力が審査済みcorpusと異なります")
            check_positions(identifier, inputs[SPEC_PATH])
            check_suppression(identifier, inputs[SPEC_PATH])
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("候補の走査はfileを書いてはいけません")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-scanner-") as temporary:
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
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
