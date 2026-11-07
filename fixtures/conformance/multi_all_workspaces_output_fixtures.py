"""複合ワークスペース全体の`check`・`verify`のtext出力と、全体の`verify`の起動した後の診断の置き場所を固定する（Coreの公開操作は実行しない）。

実装の確認事項C94・C89と、ADR-051の追加に対応する。ユーザーの決定により、規範は次のとおりに明記された。

- text出力（結果・診断・終了コード §7）: 要約行の`targets`と`diagnostics`はJSONからの導出式に固定する。`check`／`all-workspaces`はすべての`workspaces[].checkedDocumentCount`の和、
  `verify`／`all-workspaces`はすべての`workspaces[].targetResults.length`の和。`diagnostics`は結果の木構造に実在する診断の総数（最上位、すべての`workspaces[].diagnostics`、
  すべての`targetResults[].diagnostics`）で、診断を複製して件数を合わせない。診断の行は、最上位の診断を先に置き、続けてワークスペースの処理順にワークスペースの診断を置く。
  `verify`の検証対象固有の診断は、所有する最上位またはワークスペースの診断に続けて、検証対象のID順に出す。
- 起動した後の診断（`verify` §6）: `VERIFY-SPAWN-ERROR`・`VERIFY-SIGNAL`・`VERIFY-TIMEOUT`（継続単位は`skip-binding`）も、起動前の`skip-binding`と同じ場所
  （単一ワークスペースでは最上位、複合ワークスペースではテスト割当てを所有するワークスペース）へ1件だけ置き、最上位へ複製しない。複合ワークスペースの単独の操作は最上位に置く。

修正前のCoreは、全体操作のtextで最上位の診断と最上位の`targetResults`だけを数え（ワークスペースの診断と件数を落とし）、全体の`verify`で起動した後の診断を最上位へ残した。
`MULTI-063-01`〜`03`は既存のfixture（`MULTI-053-06`、`MULTI-039-02`、`MULTI-016`）の入力と完全結果をそのまま使い、textの期待値だけを足す。
`MULTI-063-04`〜`06`は新しい入力を持つ。コマンドの終了はfixtureが決定的に起こす（`SINGLE-057`〜`059`と同じ。実行形式をOSが拒否するファイル、自分に`SIGTERM`を送るシェルスクリプト、`/bin/sleep`）。

| fixture | 操作 | 入力 | 期待 |
|---|---|---|---|
| `MULTI-063-01` | `check --all-workspaces --base HEAD`（text） | `MULTI-053-06`と同じ | `failed`／1。`targets=3 diagnostics=3`。`api`の警告とエラー、`web`の警告の3行 |
| `MULTI-063-02` | `verify --all-workspaces`（text） | `MULTI-039-02`と同じ | `blocked`／2。`targets=3 diagnostics=5`。`platform`の警告、`api`の1件、`web`の3件の順 |
| `MULTI-063-03` | `verify --all-workspaces`（text） | `MULTI-016`と同じ | `blocked`／2。`targets=0 diagnostics=4`。最上位の1件を先に、続けてワークスペース3件 |
| `MULTI-063-04` | `verify --all-workspaces`（JSON） | `platform`はシグナルで終了、`api`は起動に失敗、`web`はタイムアウトするコマンド | `error`／3。3件の診断は所有ワークスペースの`diagnostics`へ1件ずつ。最上位は空 |
| `MULTI-063-05` | 同上（text） | `MULTI-063-04`と同じ | `error`／3。`targets=3 diagnostics=3`。`platform`、`api`、`web`の順 |
| `MULTI-063-06` | `verify web::REQ-101`（JSON） | `MULTI-063-04`と同じ | 対照: `error`／3。複合ワークスペースの単独の操作は、診断を最上位へ置く（修正前のCoreも通る） |

期待値は、規範と承認済みの文言から導く。textは、結果のJSONから規範の導出式だけで組み立てる参照計算（`reference_text`）で求め、Coreの描画処理は使わない。
`MULTI-063-04`〜`06`の`contextDigest`は、リテラルの参照計算Aと、入力の木構造から導く参照計算Bの両方で照合する。
"""
import copy
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import digest_reference, multi_crosscheck, multi_reference
from . import multi_verify_fixtures as mverify
from .harness import setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path
from .verify_test_check_fixtures import MEMBERS, REQ_TEXT, TEST_CONTENT, doc_text, mdoc

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
EXIT = {"passed": 0, "passed_with_warnings": 0, "failed": 1, "blocked": 2, "error": 3}
BAD_FORMAT = "this file is executable but is not a program\n"
SIGNAL_SCRIPT = "#!/bin/sh\nkill -TERM $$\n"
SLEEP = ["/bin/sleep", "60"]
# 承認済みの文言（`Coreの出力文言のレビュー記録.md`。SINGLE-057〜059が使う）。
SUMMARIES = {
    "spawn_error": "コマンドの実行形式をOSが拒否しプロセスを生成できません",
    "signal": "コマンドがシグナルで終了しました",
    "timeout": "コマンドが実効タイムアウト1秒で終了しませんでした",
}
CODES = {"spawn_error": "SPEC-VERIFY-COMMAND-001", "signal": "SPEC-VERIFY-COMMAND-001", "timeout": "SPEC-VERIFY-TIMEOUT-001"}

# 既存のfixtureの入力と完全結果をそのまま使い、textの期待値を足すケース。
DERIVED = {
    "MULTI-063-01": dict(source="MULTI-053-06", operation="check", expected_text=(
        "check failed scope=all-workspaces targets=3 diagnostics=3 (0ms)\n"
        "api:.spec/bitz.yaml::: warning: SPEC-CONFIG-UNKNOWN-001: 未知の設定キーです\n"
        "api:.spec/requirements/REQ-001.md::: error: SPEC-RELATION-MISSING-001: 強い関係の参照先が存在しません\n"
        "web:.spec/bitz.yaml::: warning: SPEC-INPUT-BOM-001: 設定ファイル先頭のBOMを除いて解析を続行します\n"),
        description="全体のcheckのtext出力が、ワークスペースの診断を数えて出し、件数をJSONの結果と一致させる"),
    "MULTI-063-02": dict(source="MULTI-039-02", operation="verify", expected_text=(
        "verify blocked scope=all-workspaces targets=3 diagnostics=5 (0ms)\n"
        "platform:.spec/bitz.yaml::: warning: SPEC-VERIFY-BLOCKED-002: 検証対象がありません\n"
        "api:.spec/technical/TECH-001.md::: error: SPEC-VERIFY-BLOCKED-001: コマンド名absentが設定に定義されていません\n"
        "api:.spec/technical/TECH-001.md::: error: SPEC-VERIFY-BLOCKED-001: コマンド名absentが設定に定義されていません\n"
        "web:.spec/technical/TECH-001.md::: error: SPEC-VERIFY-BLOCKED-001: コマンド名missingが設定に定義されていません\n"
        "web:.spec/technical/TECH-001.md::: error: SPEC-VERIFY-BLOCKED-001: コマンド名missingが設定に定義されていません\n"),
        description="全体のverifyのtext出力が、ワークスペースの診断と検証対象の診断を数え、ワークスペースの処理順に続けて出す"),
    "MULTI-063-03": dict(source="MULTI-016", operation="verify", expected_text=(
        "verify blocked scope=all-workspaces targets=0 diagnostics=4 (0ms)\n"
        "platform:.spec/bitz.yaml::: error: SPEC-VERIFY-BLOCKED-002: 検証対象がありません\n"
        "platform:.spec/bitz.yaml::: warning: SPEC-VERIFY-BLOCKED-002: 検証対象がありません\n"
        "api:.spec/bitz.yaml::: warning: SPEC-VERIFY-BLOCKED-002: 検証対象がありません\n"
        "web:.spec/bitz.yaml::: warning: SPEC-VERIFY-BLOCKED-002: 検証対象がありません\n"),
        description="全体のverifyのtext出力が、最上位の診断を先に置き、続けてワークスペースの診断を出す"),
}
# 新しい入力を持つケース。`launch`は、各ワークスペースのコマンドが起こす終了。
LAUNCH = {
    "platform": dict(path=".", prefix="", document=("REQ-001", "認証の基準"), termination="signal", argv=["bin/signal.sh", "{tests}"], timeout=300,
                     executable=("bin/signal.sh", SIGNAL_SCRIPT)),
    "api": dict(path="services/api", prefix="services/api/", document=("REQ-201", "APIの基準"), termination="spawn_error", argv=["bin/badformat", "{tests}"], timeout=300,
                executable=("bin/badformat", BAD_FORMAT)),
    "web": dict(path="apps/web", prefix="apps/web/", document=("REQ-101", "Webの基準"), termination="timeout", argv=SLEEP, timeout=1, executable=None),
}
WORKSPACE_ORDER = ["platform", "api", "web"]
CASES = {
    **{identifier: dict(kind="derived", **case) for identifier, case in DERIVED.items()},
    "MULTI-063-04": dict(kind="launch", form="json", argv=["verify", "--all-workspaces"],
                         description="全体のverifyで、起動した後の診断（シグナル・起動失敗・タイムアウト）を、テスト割当てを所有するワークスペースのdiagnosticsへ1件だけ置き、最上位へ残さない"),
    "MULTI-063-05": dict(kind="launch", form="text", argv=["verify", "--all-workspaces"],
                         description="全体のverifyのtext出力が、起動した後の診断を所有するワークスペースの診断として数え、ワークスペースの処理順に出す"),
    "MULTI-063-06": dict(kind="launch", form="control", argv=["verify", "web::REQ-101"],
                         description="対照: 複合ワークスペースの単独のverifyでは、起動した後の診断を最上位の診断へ置く"),
}
LAUNCH_TEXT = (
    "verify error scope=all-workspaces targets=3 diagnostics=3 (0ms)\n"
    f"command:::: error: {CODES['signal']}: {SUMMARIES['signal']}\n"
    f"command:::: error: {CODES['spawn_error']}: {SUMMARIES['spawn_error']}\n"
    f"command:::: error: {CODES['timeout']}: {SUMMARIES['timeout']}\n")


def source_fixture(identifier, root=HERE):
    return root / "multi" / DERIVED[identifier]["source"]


# --- 参照計算（Coreの`textrender`に依存しない） -----------------------------------------------

def escape_field(value):
    return "".join(f"\\u{ord(c):04x}" if ord(c) < 32 or 127 <= ord(c) <= 159 else c for c in value)


def diagnostic_lines(diagnostic):
    source = diagnostic["source"]
    if source["kind"] == "file":
        head = f"{escape_field(source.get('workspaceId') or '')}:{escape_field(source.get('path', ''))}:{source.get('line', '')}:{source.get('column', '')}"
    elif source["kind"] == "environment":
        head = f"{source['component']}:::"
    else:
        head = "invocation:::"
    lines = [f"{head}: {diagnostic['severity']}: {escape_field(diagnostic['code'])}: {escape_field(diagnostic['summary'])}"]
    if diagnostic.get("suggestedAction"):
        lines.append(f"  -> {escape_field(diagnostic['suggestedAction'])}")
    return lines


def tree_diagnostics(result):
    """§7の順: 最上位の診断を先に、続けてワークスペースの処理順に、ワークスペースの診断、そのワークスペースの検証対象の診断（検証対象のID順）。"""
    found = list(result["diagnostics"])
    for workspace in result["workspaces"]:
        found += workspace["diagnostics"]
        for target in sorted(workspace.get("targetResults", []), key=lambda entry: entry["target"]):
            found += target["diagnostics"]
    return found


def reference_text(result):
    """全体操作のtextを、結果のJSONから§7の導出式だけで組み立てる。"""
    if result["operation"] == "check":
        targets = sum(workspace["checkedDocumentCount"] for workspace in result["workspaces"])
    else:
        targets = sum(len(workspace["targetResults"]) for workspace in result["workspaces"])
    found = tree_diagnostics(result)
    lines = [f"{result['operation']} {result['status']} scope={result['scope']} targets={targets} diagnostics={len(found)} ({result['durationMs']}ms)"]
    for diagnostic in found:
        lines += diagnostic_lines(diagnostic)
    return "\n".join(lines) + "\n"


# --- 新しい入力（launch） --------------------------------------------------------------------

def launch_documents():
    return {ws: mdoc(ws, "requirement", info["document"][0], info["document"][1],
                     tests=[("tests/ok.py", [f"{info['document'][0]}:AC-01"])]) for ws, info in LAUNCH.items()}


def config_text(ws):
    info = LAUNCH[ws]
    argv = json.dumps(info["argv"], ensure_ascii=False)
    timeout = f"  timeoutSeconds: {info['timeout']}\n" if info["timeout"] != 300 else ""
    body = f"verify:\n{timeout}  commands:\n    default:\n      argv: {argv}\n      cwd: .\n"
    if ws == "platform":
        return multi_reference.root_config(MEMBERS) + body
    return multi_reference.plain_config(ws) + body


def launch_inputs():
    inputs = {}
    for ws, info in LAUNCH.items():
        inputs[info["prefix"] + ".spec/bitz.yaml"] = config_text(ws).encode()
        inputs[info["prefix"] + ".spec/requirements/" + info["document"][0] + ".md"] = doc_text(launch_documents()[ws]).encode()
        inputs[info["prefix"] + "tests/ok.py"] = TEST_CONTENT
        if info["executable"]:
            inputs[info["prefix"] + info["executable"][0]] = info["executable"][1].encode()
    return inputs


def launch_executables():
    return {info["prefix"] + info["executable"][0] for info in LAUNCH.values() if info["executable"]}


def target_name(ws):
    return f"{ws}::{LAUNCH[ws]['document'][0]}"


def digest_input(ws):
    """参照計算A。起点の文書と、そのワークスペースの設定、使うコマンドだけを収録する（閉包は起点のみ）。"""
    info = LAUNCH[ws]
    identifier, title = info["document"]
    statement = f"{ws}::{identifier}:AC-01"
    material = mverify.document_material(None, f"{ws}::{identifier}", ws, "requirement", title,
                                         mverify.requirement_body(identifier, title, f"{identifier}:AC-01", REQ_TEXT),
                                         statements=[mverify.statement_material(statement, REQ_TEXT)])
    material["frontmatter"]["tests"] = [{"path": "tests/ok.py", "covers": [statement], "command": "default"}]
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0", "purpose": "verify",
        "requestWorkspaceId": ws, "roots": [f"{ws}::{identifier}"], "workspaces": [{"id": ws, "path": info["path"]}],
        "documents": [material], "crossWorkspaceEdges": [],
        "settings": {"workspaces": [{"id": ws, "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
                     "context": {"maxDocuments": 20, "maxBytes": 131072},
                     "verifyTimeouts": [{"workspaceId": ws, "timeoutSeconds": info["timeout"]}],
                     "commands": [{"workspaceId": ws, "name": "default", "argv": list(info["argv"]), "cwd": "."}]},
    }


def context_digest(ws):
    return digest_reference.digest(digest_reference.canonical_bytes(digest_input(ws)))


def command_entry(ws):
    info = LAUNCH[ws]
    statement = f"{ws}::{info['document'][0]}:AC-01"
    argv = [info["argv"][0], "tests/ok.py"] if "{tests}" in info["argv"] else list(info["argv"])
    return {"bindingId": f"{ws}::default", "workspaceId": ws, "name": "default", "status": "error", "termination": info["termination"], "cwd": ".",
            "argv": argv, "tests": ["tests/ok.py"], "covers": [statement], "exitCode": None, "timeoutSeconds": info["timeout"],
            "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}


def target_entry(ws):
    return {"target": target_name(ws), "status": "error", "contextDigest": context_digest(ws), "statements": [f"{ws}::{LAUNCH[ws]['document'][0]}:AC-01"],
            "bindingRefs": [f"{ws}::default"], "diagnostics": []}


def launch_diagnostic(ws):
    termination = LAUNCH[ws]["termination"]
    return {"code": CODES[termination], "severity": "error", "resultStatus": "error", "summary": SUMMARIES[termination],
            "source": {"kind": "environment", "component": "command", "identifier": f"{ws}::default"}}


def launch_result(form):
    if form == "control":
        return {"schemaVersion": "1.0", "operation": "verify", "status": "error", "scope": "selected", "workspace": {"id": "web", "path": "apps/web"},
                "targetResults": [target_entry("web")], "revision": {"commit": COMMIT, "dirty": False}, "commands": [command_entry("web")], "durationMs": 0,
                "diagnostics": [launch_diagnostic("web")]}
    workspaces = [mverify.workspace_result(ws, LAUNCH[ws]["path"], "error", targets=[target_entry(ws)], commands=[command_entry(ws)], diagnostics=[launch_diagnostic(ws)])
                  for ws in WORKSPACE_ORDER]
    return {"schemaVersion": "1.0", "operation": "verify", "scope": "all-workspaces", "status": "error", "multiWorkspace": {"id": "platform", "path": "."},
            "workspaces": workspaces, "revision": {"commit": COMMIT, "dirty": False}, "durationMs": 0, "diagnostics": []}


# --- 共通 ----------------------------------------------------------------------------------

def read_source(identifier, root=HERE):
    """既存のfixtureの`repo/`の通常のファイル（パス→バイト列）、実行ビットのあるパス、完全結果、副作用の期待値、マニフェスト。"""
    directory = source_fixture(identifier, root)
    operation = DERIVED[identifier]["operation"]
    files, executables = {}, set()
    for path in sorted((directory / "repo").rglob("*")):
        if path.is_symlink():
            raise ValueError("元のfixtureはシンボリックリンクを持たない前提です")
        if path.is_file():
            relative = path.relative_to(directory / "repo").as_posix()
            files[relative] = path.read_bytes()
            if path.stat().st_mode & 0o111:
                executables.add(relative)
    return (files, executables, json.loads((directory / f"expected/{operation}.json").read_text()),
            json.loads((directory / "side-effects.json").read_text()), json.loads((directory / "manifest.json").read_text()))


def operation_of(identifier):
    return DERIVED[identifier]["operation"] if identifier in DERIVED else "verify"


def reviewed_inputs(identifier, root=HERE):
    return read_source(identifier, root)[0] if identifier in DERIVED else launch_inputs()


def reviewed_executables(identifier, root=HERE):
    return read_source(identifier, root)[1] if identifier in DERIVED else launch_executables()


def reviewed_result(identifier, root=HERE):
    if identifier in DERIVED:
        return read_source(identifier, root)[2]
    return launch_result(CASES[identifier]["form"])


def reviewed_text(identifier):
    if identifier in DERIVED:
        return DERIVED[identifier]["expected_text"]
    return LAUNCH_TEXT if CASES[identifier]["form"] == "text" else None


def reviewed_manifest(identifier, root=HERE):
    operation = operation_of(identifier)
    text = reviewed_text(identifier) is not None
    if identifier in DERIVED:
        manifest = copy.deepcopy(read_source(identifier, root)[4])
        argv = [item for index, item in enumerate(manifest["invocation"]["argv"])
                if item != "--format" and manifest["invocation"]["argv"][index - 1] != "--format"]
        manifest["fixtureId"], manifest["description"] = identifier, CASES[identifier]["description"]
        manifest["invocation"]["argv"] = argv
        manifest["expect"].update(stdout="text", textFile=f"expected/{operation}.txt")
        return manifest
    case = CASES[identifier]
    status = reviewed_result(identifier)["status"]
    argv = list(case["argv"]) + ([] if text else ["--format", "json"])
    expect = {"status": status, "exitCode": EXIT[status], "stdout": "text" if text else "json", "resultFile": "expected/verify.json", "reportFileCount": 0}
    if text:
        expect["textFile"] = "expected/verify.txt"
    return {"fixtureId": identifier, "description": case["description"],
            "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
            "invocation": {"runner": "bitz", "cwd": ".", "argv": argv, "env": {}}, "expect": expect}


def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は、既存のfixtureのものを使うか、隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        fixture = root / "multi" / identifier
        executables = reviewed_executables(identifier, root)
        for name, content in reviewed_inputs(identifier, root).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            path.chmod(0o755 if name in executables else 0o644)
        manifest = reviewed_manifest(identifier, root)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / f"expected/{operation_of(identifier)}.json").write_text(_dump(reviewed_result(identifier, root)))
        text = reviewed_text(identifier)
        if text is not None:
            (fixture / f"expected/{operation_of(identifier)}.txt").write_text(text)
        if identifier in DERIVED:
            state = read_source(identifier, root)[3]
        else:
            with tempfile.TemporaryDirectory(prefix="bitz-all-workspaces-output-") as temporary:
                sandbox = Path(temporary)
                repository = setup(fixture, manifest, sandbox / "repo")
                external = {name: sandbox / name for name in ("home", "cache", "temporary")}
                for path in external.values():
                    path.mkdir()
                state = {"schemaVersion": "1.0", "policy": "read-only", "before": observe(repository, external)}
                state["after"] = state["before"]
        (fixture / "side-effects.json").write_text(_dump(state))


# --- 監査 ----------------------------------------------------------------------------------

def observe_terminations(repository):
    """fixture自身のコマンドが、レビュー済みの終了を起こすことを、Coreを介さず直接実行して確かめる（入力の観測であり、Coreの`verify`の実行ではない）。"""
    for ws, info in LAUNCH.items():
        root = repository / info["prefix"] if info["prefix"] else repository
        termination = info["termination"]
        if termination == "timeout":
            sleeper = Path(SLEEP[0])
            if not (sleeper.is_file() and os.access(sleeper, os.X_OK)) or int(SLEEP[1]) <= info["timeout"]:
                raise ValueError("タイムアウトのコマンドは、実効タイムアウトより長く動く実行可能なファイルである必要があります")
            continue
        executable = root / info["executable"][0]
        if not (executable.is_file() and os.access(executable, os.X_OK)):
            raise ValueError(f"{ws}のコマンドのファイルは実行可能な通常のファイルである必要があります")
        if termination == "spawn_error":
            try:
                subprocess.run([str(executable)], cwd=root, capture_output=True, timeout=10)
            except OSError:
                continue
            raise ValueError("コマンドのファイルをOSが受理したので、プロセスの生成のエラーが起きません")
        completed = subprocess.run([str(executable)], cwd=root, capture_output=True, timeout=10)
        if completed.returncode != -signal.SIGTERM:
            raise ValueError("コマンドがシグナルで終了しませんでした")


def check_launch(identifier, repository, result):
    """起動した後の診断の置き場所と、ハッシュ値を、入力から確かめる。"""
    form = CASES[identifier]["form"]
    config = multi_crosscheck.read_yaml((repository / "services/api/.spec/bitz.yaml").read_text(encoding="utf-8"))
    if config["verify"]["commands"]["default"]["argv"][0] != "bin/badformat":
        raise ValueError("apiのコマンドが入力と異なります")
    entries = list(result["workspaces"]) if form != "control" else [result]
    expected_binding = {f"{ws}::default" for ws in (WORKSPACE_ORDER if form != "control" else ["web"])}
    commands = [command for entry in entries for command in entry["commands"]]
    if {command["bindingId"] for command in commands} != expected_binding or any(command["termination"] == "exit" for command in commands):
        raise ValueError("起動した後に終了するコマンドが、期待と異なります")
    found = [diagnostic for entry in entries for diagnostic in entry["diagnostics"]] + (list(result["diagnostics"]) if form != "control" else [])
    if sorted(d["source"]["identifier"] for d in found) != sorted(expected_binding):
        raise ValueError("起動した後の診断は、コマンドごとに1件だけ必要です（複製しない）")
    if form != "control":
        if result["diagnostics"]:
            raise ValueError("全体のverifyは、起動した後の診断を最上位へ置いてはいけません")
        for workspace in result["workspaces"]:
            if [d["source"]["identifier"] for d in workspace["diagnostics"]] != [f"{workspace['id']}::default"]:
                raise ValueError("起動した後の診断は、テスト割当てを所有するワークスペースの診断へ置く必要があります")
    elif [d["source"]["identifier"] for d in result["diagnostics"]] != ["web::default"] or result["workspace"]["id"] != "web":
        raise ValueError("複合ワークスペースの単独のverifyは、診断を最上位へ置く必要があります")
    loaded = multi_crosscheck.load_workspaces(repository)
    for entry in (target for e in entries for target in e["targetResults"]):
        ws = entry["target"].partition("::")[0]
        derived = multi_crosscheck.canonical_bytes(multi_crosscheck.build(repository, entry["target"], loaded=loaded))
        if multi_crosscheck.digest(derived) != entry["contextDigest"]:
            raise ValueError(f"{entry['target']}のハッシュ値が参照計算Bと一致しません")
        if multi_reference.canonical_bytes(digest_input(ws)) != derived:
            raise ValueError(f"{entry['target']}のハッシュ値の参照計算AとBが一致しません")


def check_text(identifier, result, text):
    if text != reference_text(result) or text != reviewed_text(identifier):
        raise ValueError("textが参照計算またはレビュー済みの期待値と異なります")
    first = text.split("\n", 1)[0]
    found = tree_diagnostics(result)
    if f"diagnostics={len(found)} " not in first or not first.startswith(f"{result['operation']} {result['status']} scope=all-workspaces "):
        raise ValueError("要約行がJSONの結果と一致しません")


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text())) for name in ("manifest", "result", "side-effects")}
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / "multi" / identifier
        operation = operation_of(identifier)
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / f"expected/{operation}.json").read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier, root):
                raise ValueError("起動条件がレビュー済みの期待値と異なります")
            if result != reviewed_result(identifier, root):
                raise ValueError("完全結果がレビュー済みの期待値と異なります")
            text = reviewed_text(identifier)
            expected_files = {f"{operation}.json"} | ({f"{operation}.txt"} if text is not None else set())
            if {path.name for path in (fixture / "expected").glob("*")} != expected_files:
                raise ValueError("期待結果のファイルの構成がレビュー済みの形と異なります")
            if text is not None:
                check_text(identifier, result, (fixture / f"expected/{operation}.txt").read_bytes().decode("utf-8"))
            files = {p.relative_to(fixture / "repo").as_posix(): p for p in (fixture / "repo").rglob("*") if p.is_file() or p.is_symlink()}
            inputs, executables = reviewed_inputs(identifier, root), reviewed_executables(identifier, root)
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name] for name, p in files.items()):
                raise ValueError("入力がレビュー済みのcorpusと異なります")
            if any(bool(p.stat().st_mode & 0o111) != (name in executables) for name, p in files.items()):
                raise ValueError("実行ビットがレビュー済みの入力と異なります")
            if identifier in DERIVED and effects != read_source(identifier, root)[3]:
                raise ValueError("副作用の期待値が元のfixtureと異なります")
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("検査はファイルを書いてはいけません")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-all-workspaces-output-") as temporary:
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
                    if CASES[identifier]["kind"] == "launch":
                        check_launch(identifier, repository, result)
                        if run == 0:
                            observe_terminations(repository)
                            if compare_state(effects["after"], observe(repository, external)):
                                raise ValueError("コマンドの観測でfixtureの状態が変わりました")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run", "references": 2,
            "status": "Passed" if not errors else "Failed", "errors": errors}
