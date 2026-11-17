"""単一ワークスペースのコマンドの`cwd`の字句と所有領域を固定する（Coreの公開操作は実行しない）。

実装の確認事項C82・C86に対応する。`verify.commands.<名前>.cwd`は、型しか検査されず、`../..`、絶対パス、globの文字、外へ出る
シンボリックリンクの`cwd`でも、どの操作も止まらず、`verify`がテストのコマンドを所有領域の外で起動していた。
規範は次のとおり定めた。

- ワークスペース・設定仕様 §6: `cwd`の字句は、単独の`.`、または空のセグメント、`.`、`..`、NULを含む制御文字（U+0000〜U+001F、U+007F）、globの文字`*?[]`を含まず、`/`で始まらない
  パスに限る。字句の違反は設定の検査で診断`SPEC-CONFIG-SCHEMA-001`とし、どの操作もコマンドの実行へ進まない。`cwd`のシンボリックリンクは辿らない
  （ADR-071。2026-11-15の訂正）。`cwd`がディレクトリとして存在しなければ（途中または末端がシンボリックリンクを含む）、`verify`がテスト割当ての起動前に
  診断`SPEC-VERIFY-BLOCKED-001`（`blocked`）とする。単一ワークスペースでは、字句の検査を通った`cwd`は常にルートの配下にあるので、所有の違反は生じない
  （`VERIFY-CWD-OUTSIDE`は診断レジストリから除いた）。
- 診断レジストリ: `CONFIG-FIELD-TYPE`系の`SPEC-CONFIG-SCHEMA-001`（重大度`error`、結果への効果`error`）、
  `VERIFY-CWD-UNAVAILABLE`（`SPEC-VERIFY-BLOCKED-001`、`blocked`、`skip-binding`、`file`）。
- `verify` §5.1: `VERIFY-CWD-UNAVAILABLE`の`source`は設定ファイルの`verify.commands.<名前>.cwd`。§6: `skip-binding`は単一ワークスペースでは
  最上位の`diagnostics`へ1件だけ置き、影響を受ける検証対象は診断を複製せず、状態を`blocked`、`bindingRefs: []`とする。`commands[]`へ実行結果を作らない。
- 結果・診断・終了コード §2: 設定の構文・型などでワークスペースの同一性を構成する前に停止した単独結果は、`workspace.id`を`null`、`path`を`.`とする。
  §3: `SPEC-CONFIG-SCHEMA-001`は終了コード3（`error`）。

| fixture | 操作 | `cwd` | 期待 |
|---|---|---|---|
| `SINGLE-167-01` | `verify REQ-001` | `../..` | 設定の検査で`SPEC-CONFIG-SCHEMA-001`、`error`／3、起動しない |
| `SINGLE-167-02` | `doctor` | `/tmp`（絶対パス） | 同上（`doctor`の結果の形） |
| `SINGLE-167-03` | `check --full --base HEAD` | `t*`（globの文字） | 同上（`check`の結果の形） |
| `SINGLE-167-04` | `context REQ-001 --purpose verify` | `tests//`（空のセグメント） | 同上（`context`の結果の形） |
| `SINGLE-167-05` | `verify REQ-001` | `./tests`（`.`のセグメント） | 同上 |
| `SINGLE-167-06` | `verify REQ-001` | `a]`（閉じ括弧だけ。globの文字は`*?[]`の4つ） | 同上 |
| `SINGLE-167-07` | `verify REQ-001` | シンボリックリンク`up -> ..`（ワークスペースのルートの親） | `VERIFY-CWD-UNAVAILABLE`、`blocked`／2、`commands`は空（診断のJSONは訂正の前と同じ） |
| `SINGLE-167-08` | `verify REQ-001` | `tests`（対照） | `passed`／0、`commands[].cwd`は`tests` |
| `SINGLE-167-09` | `verify REQ-001` | シンボリックリンク`inner -> real`（テストのパスは`inner/`配下。2026-11-15に`passed`から`failed`へ訂正） | `failed`／1。テストのパスの途中がシンボリックリンクなので、`TECH-001`の`tests[0].path`・`tests[1].path`が`SPEC-PATH-INVALID-001`（`cwd`は判定しない）。`commands`は空 |

全ケースは`SINGLE-042`のcorpus（`REQ-001`と`TECH-001`、テストは`TECH-001`が宣言する）を基にコマンドの`cwd`だけを替え、`SINGLE-126`と同じく
インデックスへステージしてから実行する（`check`は基準版のコミットを作る）。診断の`summary`は、字句の違反が新しい文言
`作業ディレクトリのパスの形式が不正です`、実パスの違反が既存の`コマンドの作業ディレクトリが利用できません`である（ユーザー承認済み）。

停止する結果の形は、同じ原因（設定の型の不正）の既存のfixtureがレビュー済みの形を引き継ぐ: `doctor`は`SINGLE-092`、`check`は`SINGLE-004-01`、
`context`は`SINGLE-150`（目的だけ`verify`）、`verify`は`SINGLE-126-01`。診断だけを新しい診断に置き換える。

`SINGLE-167-07`の`up -> ..`は、準備手順の後は準備手順で作る隔離したリポジトリの親（`home`などの隣のディレクトリを持つ）を指す。リンクを辿らないので、
リンク先がどこかは判定に使わない（`cwd`が利用できないのは、末端がシンボリックリンクだから）。このとき、テストのパスは字句では`cwd`の配下にもないが、
`cwd`の判定がその前提なので、`cwd`だけが原因になる。`SINGLE-167-09`は、`cwd`の`inner`配下にテストを置くため、テストのパスの途中がシンボリックリンクになり、
起動前の検査より前のテストのパスの検査（`verify` §4の4.）が先に止める。

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。ハッシュ値は、独立に書いた2系統の参照計算
（リテラルのA、入力の木構造から導出するB）のバイト列の一致を要求する。
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .schemas import schema_path
from . import digest_crosscheck, digest_reference
from . import lexical_path_reference as lexical
from .harness import setup
from .initial_fixtures import compare_state, observe

HERE = Path(__file__).resolve().parent
SINGLE = HERE / "single"
CONFIG_PATH = digest_reference.CONFIG_PATH
TECH_PATH = digest_reference.TECH_PATH
CWD_LINE = "      cwd: .\n"
KEY = "verify.commands.default.cwd"
STATEMENTS = ["REQ-001:AC-01", "REQ-001:AC-02"]
TEST_NAMES = ["test_auth.py", "test_session.py"]
GLOB_CHARACTERS = "*?[]"
LEXICAL_SUMMARY = "作業ディレクトリのパスの形式が不正です"
OUTSIDE_SUMMARY = "コマンドの作業ディレクトリが利用できません"

# id: dict(op, argv, cwd, kind, base, description)。
#   kind: `lexical`（字句の違反で設定の検査が止める）、`unavailable`（`cwd`が利用できない。末端がシンボリックリンク）、`invalid`（テストのパスの途中がシンボリックリンク）、
#   `passed`（対照）。
#   link: 入力に置くシンボリックリンク(名前, 解決先)。tests: テストを置くディレクトリ。
#   base: 停止の結果の形を引き継ぐ元のfixture。
CASES = {
    "SINGLE-167-01": dict(op="verify", argv=["verify", "REQ-001"], cwd="../..", kind="lexical", base="SINGLE-126-01", tests="tests",
                          description="cwdに..があれば設定の検査が止めverifyはコマンドを起動しない"),
    "SINGLE-167-02": dict(op="doctor", argv=["doctor"], cwd="/tmp", kind="lexical", base="SINGLE-092", tests="tests",
                          description="cwdが絶対パスならdoctorは設定の検査で止まりコマンドの検査へ進まない"),
    "SINGLE-167-03": dict(op="check", argv=["check", "--full", "--base", "HEAD"], cwd="t*", kind="lexical", base="SINGLE-004-01", tests="tests",
                          description="cwdにglobの文字があればcheckは設定の検査で止まる"),
    "SINGLE-167-04": dict(op="context", argv=["context", "REQ-001", "--purpose", "verify"], cwd="tests//", kind="lexical", base="SINGLE-150",
                          tests="tests", description="cwdに空のセグメントがあればcontextは設定の検査で止まる"),
    "SINGLE-167-05": dict(op="verify", argv=["verify", "REQ-001"], cwd="./tests", kind="lexical", base="SINGLE-126-01", tests="tests",
                          description="cwdに.のセグメントがあれば設定の検査が止めverifyはコマンドを起動しない"),
    "SINGLE-167-06": dict(op="verify", argv=["verify", "REQ-001"], cwd="a]", kind="lexical", base="SINGLE-126-01", tests="tests",
                          description="cwdに閉じ括弧だけがあってもglobの文字なので設定の検査が止める"),
    "SINGLE-167-07": dict(op="verify", argv=["verify", "REQ-001"], cwd="up", kind="unavailable", base=None, tests="tests", link=("up", ".."),
                          description="cwdがシンボリックリンクなら、辿らずにcwdが利用できないものとして起動前にblockedとする"),
    "SINGLE-167-08": dict(op="verify", argv=["verify", "REQ-001"], cwd="tests", kind="passed", base=None, tests="tests",
                          description="対照: cwdがルート配下の通常のディレクトリならverifyは通る"),
    "SINGLE-167-09": dict(op="verify", argv=["verify", "REQ-001"], cwd="inner", kind="invalid", base=None, tests="inner", link=("inner", "real"),
                          description="cwdの配下のテストのパスの途中がシンボリックリンクなら、リンク先がルートの中でも存在しないパスと同じにし、verifyの対象をfailedにする"),
    "SINGLE-167-10": dict(op="verify", argv=["verify", "REQ-001"], cwd="lnk/sub", kind="unavailable", base=None, tests="tests", link=("lnk", "real"),
                          files={"real/sub/keep.txt": b"keep\n"},
                          description="cwdの途中のセグメントがシンボリックリンクなら、リンク先に実在するディレクトリでも、辿らずにcwdが利用できないものとして起動前にblockedとする"),
}
EXIT_BY_STATUS = {"passed": 0, "failed": 1, "blocked": 2, "error": 3}


# --- 規範の独立した適用 ---------------------------------------------------------------------

def lexical_violation(cwd):
    """ワークスペース・設定仕様 §6の`cwd`の字句の規則（参照計算）。違反なら`True`。"""
    if cwd == ".":
        return False
    if cwd.startswith("/") or any(ord(char) < 0x20 or ord(char) == 0x7F for char in cwd):
        return True
    return any(segment in ("", ".", "..") or any(char in segment for char in GLOB_CHARACTERS) for segment in cwd.split("/"))


def within(path, base):
    """字句のパスのセグメントの境界での包含（境界自身を含む）。NFCにしたセグメントのコードポイントの完全一致で比べ、ファイルシステムを読まない。"""
    return lexical.within(path, base)


# --- 入力 -------------------------------------------------------------------------------

def tests_directory(identifier):
    return CASES[identifier]["tests"]


def config(identifier):
    cwd = CASES[identifier]["cwd"]
    text = cwd if CASES[identifier]["kind"] in ("passed", "invalid") else '"' + cwd + '"'
    return digest_reference.CONFIG.replace(CWD_LINE, f"      cwd: {text}\n")


def reviewed_inputs(identifier):
    """通常のファイルの(パス→バイト列)。`link`のシンボリックリンクは`reviewed_links`が別に持つ。"""
    inputs = dict(digest_reference.reviewed_inputs("SINGLE-042"))
    inputs[CONFIG_PATH] = config(identifier).encode()
    inputs.update(CASES[identifier].get("files", {}))
    directory = tests_directory(identifier)
    if directory != "tests":
        # テストの実体を`real/`へ移し、`TECH-001`が宣言するテストのパスをシンボリックリンク`inner/`経由にする。
        for name in TEST_NAMES:
            inputs[f"real/{name}"] = inputs.pop(f"tests/{name}")
        inputs[TECH_PATH] = inputs[TECH_PATH].decode().replace("path: tests/", f"path: {directory}/").encode()
    return inputs


def reviewed_links(identifier):
    link = CASES[identifier].get("link")
    return {link[0]: link[1]} if link else {}


def test_paths(identifier):
    return [f"{tests_directory(identifier)}/{name}" for name in TEST_NAMES]


def reviewed_manifest(identifier):
    case = CASES[identifier]
    status = reviewed_result(identifier)["status"]
    argv = [*case["argv"], "--format", "json"]
    if case["op"] == "check":
        setup_plan = {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []}
    elif case["op"] in ("doctor", "context"):
        setup_plan = {"git": True, "operations": []}
    else:
        # `verify`は、テスト割当てを所有するワークスペースの設定がインデックスで未追跡だと起動を遮断するため、入力をステージする。
        setup_plan = {"git": True, "operations": [{"op": "stage", "paths": ["."]}]}
    return {
        "fixtureId": identifier, "description": case["description"], "setup": setup_plan,
        "invocation": {"runner": "bitz", "cwd": ".", "argv": argv, "env": {}},
        "expect": {"status": status, "exitCode": EXIT_BY_STATUS[status], "stdout": "json",
                   "resultFile": f"expected/{case['op']}.json", "reportFileCount": 0},
    }


# --- レビュー済みの期待結果 -----------------------------------------------------------------

def reviewed_digest_input(identifier):
    """参照計算A。`SINGLE-042`のレビュー済みの材料に、コマンドの`cwd`とテストのパスだけを加える。"""
    payload = copy.deepcopy(digest_reference.reviewed_digest_input("SINGLE-042"))
    payload["settings"]["commands"][0]["cwd"] = CASES[identifier]["cwd"]
    directory = tests_directory(identifier)
    for entry in payload["documents"][1]["frontmatter"]["tests"]:
        entry["path"] = entry["path"].replace("tests/", f"{directory}/", 1)
    return payload


def context_digest(identifier):
    return digest_reference.digest(digest_reference.canonical_bytes(reviewed_digest_input(identifier)))


def stop_diagnostic():
    return {"code": "SPEC-CONFIG-SCHEMA-001", "severity": "error", "resultStatus": "error", "summary": LEXICAL_SUMMARY,
            "source": {"kind": "file", "workspaceId": None, "path": CONFIG_PATH, "key": KEY}}


def outside_diagnostic():
    return {"code": "SPEC-VERIFY-BLOCKED-001", "severity": "error", "resultStatus": "blocked", "summary": OUTSIDE_SUMMARY,
            "source": {"kind": "file", "workspaceId": "root", "path": CONFIG_PATH, "key": KEY}}


def stop_result(identifier):
    """設定の検査で止まる結果。同じ原因（設定の型の不正）の既存のfixtureがレビュー済みの形を引き継ぎ、診断だけを置き換える。"""
    case = CASES[identifier]
    base = json.loads((SINGLE / case["base"] / f"expected/{case['op']}.json").read_text())
    base["diagnostics"] = [stop_diagnostic()]
    if case["op"] == "context":
        base["purpose"] = "verify"
    return base


def invalid_diagnostics(identifier):
    """テストのパスの途中がシンボリックリンクのとき、`TECH-001`のエントリごとの診断（`verify` §4の4.）。"""
    return [{"code": "SPEC-PATH-INVALID-001", "severity": "error", "resultStatus": "failed", "summary": "テストのパスが存在しません",
             "source": {"kind": "file", "workspaceId": "root", "path": TECH_PATH, "key": f"tests[{index}].path"}}
            for index in range(len(TEST_NAMES))]


def verify_result(identifier):
    kind = CASES[identifier]["kind"]
    blocked, invalid = kind == "unavailable", kind == "invalid"
    status = "blocked" if blocked else "failed" if invalid else "passed"
    entry = {"target": "REQ-001", "status": status, "contextDigest": context_digest(identifier),
             "statements": list(STATEMENTS), "bindingRefs": [] if blocked or invalid else ["root::default"],
             "diagnostics": invalid_diagnostics(identifier) if invalid else []}
    result = {"schemaVersion": "1.0", "operation": "verify", "status": status, "scope": "selected",
              "workspace": {"id": "root", "path": "."}, "targetResults": [entry], "revision": None, "commands": [],
              "durationMs": 0, "diagnostics": [outside_diagnostic()] if blocked else []}
    if status == "passed":
        result["commands"] = [{
            "bindingId": "root::default", "workspaceId": "root", "name": "default", "status": "passed",
            "termination": "exit", "cwd": CASES[identifier]["cwd"], "argv": ["/bin/true", *TEST_NAMES],
            "tests": test_paths(identifier), "covers": list(STATEMENTS), "exitCode": 0, "timeoutSeconds": 300,
            "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}]
    return result


def reviewed_result(identifier):
    if CASES[identifier]["kind"] == "lexical":
        return stop_result(identifier)
    return verify_result(identifier)


def reviewed_effects(identifier, state):
    return {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}


# --- 参照計算（準備手順の後の入力から導く） -----------------------------------------------------

def configured_cwd(repository):
    text = (repository / CONFIG_PATH).read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("cwd:")]
    if len(lines) != 1:
        raise ValueError("設定は`cwd`を1件だけ持つ必要があります")
    value = lines[0].split(":", 1)[1].strip()
    return value[1:-1] if value[:1] == '"' else value


def reference_outcome(repository, tests):
    """設定の`cwd`と宣言したテストのパスから、操作の結果の種類を字句の規則で導く: `lexical`、`invalid`、`unavailable`、`passed`。

    テストのパスの検査（`verify` §4の4.）は、`cwd`の検査（§5.1）より前に行う。リンクを辿らず、実パスを使わない。
    """
    cwd = configured_cwd(repository)
    if lexical_violation(cwd):
        return "lexical"
    if any(lexical.lookup(repository, path, "file") != "ok" for path in tests):
        return "invalid"
    if lexical.lookup(repository, cwd, "directory") != "ok":
        return "unavailable"
    return "passed"


def check_conditions(identifier, repository, manifest, result):
    """名乗る条件を、散文ではなく準備手順の後の入力から確かめる。"""
    case = CASES[identifier]
    if configured_cwd(repository) != case["cwd"]:
        raise ValueError("設定の`cwd`がレビュー済みの値と異なります")
    outcome = reference_outcome(repository, test_paths(identifier))
    if outcome != case["kind"]:
        raise ValueError(f"入力から導く結果の種類が期待と異なります: {outcome}")
    link = case.get("link")
    if link:
        path = repository / link[0]
        if not path.is_symlink() or os.readlink(path) != link[1]:
            raise ValueError("シンボリックリンクがレビュー済みの入力と異なります")
    elif case["kind"] == "passed" and not (repository / case["cwd"]).is_dir():
        raise ValueError("対照の`cwd`は通常のディレクトリである必要があります")
    if case["kind"] == "unavailable" and lexical.lookup(repository, case["cwd"], "directory") != "link":
        raise ValueError("途中または末端がシンボリックリンクの`cwd`である必要があります")
    if case["kind"] == "unavailable" and not os.path.isdir(repository / case["cwd"]):
        raise ValueError("リンクを辿れば実在するディレクトリの`cwd`である必要があります")
    if case["kind"] == "invalid" and not all(os.path.isfile(repository / path) for path in test_paths(identifier)):
        raise ValueError("リンクを辿れば実在する通常のファイルである必要があります")
    if case["kind"] == "passed":
        # テストのパスは、実効`cwd`の字句の配下に実在する。
        for path in test_paths(identifier):
            if lexical.lookup(repository, path, "file") != "ok" or not within(path, case["cwd"]):
                raise ValueError("テストのパスは実効`cwd`の配下の通常のファイルである必要があります")
    if case["kind"] == "lexical":
        if result["diagnostics"] != [stop_diagnostic()] or result["status"] != "error":
            raise ValueError("字句の違反は設定の検査の診断1件だけを返す必要があります")
    status = {"lexical": "error", "unavailable": "blocked", "invalid": "failed", "passed": "passed"}[outcome]
    if (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != (status, EXIT_BY_STATUS[status]) or result["status"] != status:
        raise ValueError("状態または終了コードが参照計算と異なります")
    if outcome != "passed" and result.get("commands"):
        raise ValueError("起動しないケースは`commands`が空である必要があります")
    # 基準版のコミットの有無: `check`だけがコミットを持つ。
    if manifest["setup"].get("baseCommit") and case["op"] != "check":
        raise ValueError("基準版のコミットは`check`だけが持ちます")
    if case["base"]:
        base = json.loads((SINGLE / case["base"] / f"expected/{case['op']}.json").read_text())
        if base["diagnostics"][0]["code"] != "SPEC-CONFIG-SCHEMA-001" or base["status"] != "error":
            raise ValueError("引き継ぐ元のfixtureは設定の検査で止まる結果である必要があります")


def check_digest(identifier, repository, result):
    if CASES[identifier]["kind"] == "lexical":
        return
    derived = digest_crosscheck.canonical_bytes(digest_crosscheck.build(repository))
    if digest_crosscheck.digest(derived) != result["targetResults"][0]["contextDigest"]:
        raise ValueError("検証対象のハッシュ値が参照計算Bと一致しません")
    if digest_reference.canonical_bytes(reviewed_digest_input(identifier)) != derived:
        raise ValueError("検証対象のハッシュ値の参照計算AとBが一致しません")


# --- 書き出しと監査 ---------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = root / "single" / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        for name, target in reviewed_links(identifier).items():
            link = fixture / "repo" / name
            if link.is_symlink():
                link.unlink()
            link.symlink_to(target)
        manifest = reviewed_manifest(identifier)
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / f"expected/{CASES[identifier]['op']}.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-command-cwd-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(_dump(reviewed_effects(identifier, state)))


def actual_entries(fixture):
    """`repo/`の通常のファイル(パス→バイト列)とシンボリックリンク(パス→解決先)。"""
    files, links = {}, {}
    for path in sorted((fixture / "repo").rglob("*")):
        relative = path.relative_to(fixture / "repo").as_posix()
        if path.is_symlink():
            links[relative] = os.readlink(path)
        elif path.is_file():
            if path.stat().st_mode & 0o111:
                raise ValueError(f"{relative}は実行ビットを持ってはいけません")
            files[relative] = path.read_bytes()
    return files, links


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "single" / identifier
        try:
            case = CASES[identifier]
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / f"expected/{case['op']}.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            if effects != reviewed_effects(identifier, effects["before"]):
                raise ValueError("副作用の期待値がレビュー済みのポリシーと異なります")
            files, links = actual_entries(fixture)
            if files != reviewed_inputs(identifier) or links != reviewed_links(identifier):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if {path.relative_to(fixture).as_posix() for path in (fixture / "expected").glob("*")} != {f"expected/{case['op']}.json"}:
                raise ValueError("期待値のファイルがレビュー済みの集合と異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("既に存在したパスはすべて不変である必要があります")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-command-cwd-") as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / "repo")
                    external = {key: sandbox / key for key in ("home", "cache", "temporary")}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects["before"], actual) or (previous is not None and previous != actual):
                        raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
                    previous = actual
                    check_conditions(identifier, repository, manifest, result)
                    check_digest(identifier, repository, result)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
