"""複合ワークスペースのコマンドの`cwd`の所有領域を固定する（Coreの公開操作は実行しない）。

実装の確認事項C82・C86に対応する。複合ワークスペースでは、`cwd`はそのワークスペースの所有領域だけを指せる。
`cwd`が`../..`、絶対パス、または所有領域の外へ解決するシンボリックリンクのとき、`verify`はテストのコマンドを所有領域の外で起動していた。
ルートワークスペースの`cwd`がメンバーのルートの配下を指す場合も、同じく所有領域の外である。

- 複合ワークスペース仕様 §5・§5.1: `cwd`のシンボリックリンクは同じ所有領域内へ解決する場合だけ許可する。ルートワークスペースの`cwd`は、
  実パスがメンバーのルートの配下にあれば所有領域の外とする。違反は診断`SPEC-MULTI-OWNERSHIP-001`とし、`verify`がテスト割当ての起動前に判定する。
  違反したテスト割当ては起動せず、独立したテスト割当てを続ける。`cwd`の字句の違反は設定の検査で診断`SPEC-CONFIG-SCHEMA-001`とする。
- ワークスペース・設定仕様 §6: `cwd`の字句は、単独の`.`、または空のセグメント、`.`、`..`、NULを含む制御文字（U+0000〜U+001F、U+007F）、globの文字`*?[]`を含まない、`/`で始まらないパスに限る。
- 診断レジストリ: `MULTI-OWNERSHIP-CWD`（`SPEC-MULTI-OWNERSHIP-001`、`error`／`failed`、`skip-binding`、`file`）。
- `verify` §5.1: `source`は設定ファイルの`verify.commands.<名前>.cwd`。§6: `skip-binding`の診断は、複合ワークスペースではテスト割当てを所有する
  ワークスペースへ1件だけ置き、影響を受ける検証対象は診断を複製せず、状態を`blocked`、`bindingRefs: []`とする。`commands[]`へ実行結果を作らない。
  単独の`verify`（`scope: selected`）は、ワークスペースの配列を持たないので、最上位の`diagnostics`へ置く。
- 結果・診断・終了コード §2・§3: 最上位と各ワークスペースの状態は最悪値（`failed`は`blocked`より重い）で集約し、`failed`は終了コード1。
  全体事前検査（設定の検査）で止まる結果は`workspaces: []`。複合ワークスペース仕様 §9: ルートの設定が型・構文などで有効な同一性を構成できないときは
  `multiWorkspace`を`{id: null, path: .}`、`source.workspaceId`を`null`とする。

| fixture | 操作と実行ディレクトリ | 入力 | 期待 |
|---|---|---|---|
| `MULTI-051-01` | `verify --all-workspaces`、`.` | ルート`platform`の`cwd`が`apps/web`（メンバー`web`のルートの配下） | `failed`／1。`platform`に`SPEC-MULTI-OWNERSHIP-001`が1件、`web`のテスト割当ては実行して`passed` |
| `MULTI-051-02` | `verify platform::REQ-001`、`.` | ルートの`cwd`がシンボリックリンク`lk -> apps/web` | `failed`／1。最上位に`SPEC-MULTI-OWNERSHIP-001`が1件、`commands`は空 |
| `MULTI-051-03` | `verify --all-workspaces`、`.` | `web`の`cwd`がシンボリックリンク`esc -> ../..`（メンバーのルートの外） | `failed`／1。`web`に`SPEC-MULTI-OWNERSHIP-001`が1件、`platform`のテスト割当ては実行して`passed` |
| `MULTI-051-04` | `verify --workspace web web::REQ-101`、`.` | `MULTI-051-03`と同じ入力 | `failed`／1。最上位に`SPEC-MULTI-OWNERSHIP-001`が1件、`commands`は空 |
| `MULTI-051-05` | `verify --all-workspaces`、`.` | ルートの`cwd`が絶対パス`/tmp`（字句の違反） | `error`／3。設定の検査で`SPEC-CONFIG-SCHEMA-001`が1件、`workspaces`は空 |
| `MULTI-051-06` | `verify --all-workspaces`、`.` | 両方の`cwd`が`tests`（対照） | `passed`／0。2つのテスト割当てをどちらも実行 |

基本のリポジトリは、ルート`platform`（`.`）とメンバー`web`（`apps/web`）で、すべてコミットする。両方がコマンド`t`（`/bin/true`と`{tests}`）を持ち、
`platform`の`REQ-001`と`web`の`REQ-101`が、それぞれ自身の所有領域のテストを`tests`で宣言する。
違反したテスト割当ての`REQ-001`（または`REQ-101`）は、`cwd`の違反とテストが`cwd`の配下にないことの両方が成り立つ場合があるが、
`cwd`自身が所有領域の外であれば、`cwd`を前提とするテストの配下の判定には進まず、`cwd`の違反だけを1件返す
（`verify` §5.1。`cwd`の判定は、テストのパスと`cwd`の包含の判定の前提である）。

期待値の根拠は規範文と、このモジュールの参照計算だけである（Coreの出力は根拠にしない）。ハッシュ値は、独立に書いた2系統の参照計算
（リテラルのA、入力の木構造から導出するB。`multi_crosscheck`）のバイト列の一致を要求する。
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from . import multi_crosscheck, multi_reference, multi_verify_fixtures as verify_fixtures
from .command_cwd_fixtures import lexical_violation, within
from .harness import setup
from .initial_fixtures import compare_state, observe
from .schemas import schema_path

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
ROOT_ID = "platform"
MEMBER = ("web", "apps/web")
CONFIG_PATH = ".spec/bitz.yaml"
COMMAND = "t"
KEY = f"verify.commands.{COMMAND}.cwd"
ROOT_REQ = ("platform", "REQ-001", "プラットフォームの基準", ".spec/requirements/REQ-001.md", "tests/test_platform.py")
WEB_REQ = ("web", "REQ-101", "Webの基準", "apps/web/.spec/requirements/REQ-101.md", "tests/test_web.py")
WORKSPACE_ROOTS = {"platform": ".", "web": "apps/web"}
OWNERSHIP_SUMMARY = "パス{path}の解決先がワークスペース{workspace}の所有領域の外です"
LEXICAL_SUMMARY = "作業ディレクトリのパスの形式が不正です"
EXIT_BY_STATUS = {"passed": 0, "failed": 1, "blocked": 2, "error": 3}

# id: dict(argv, root_cwd, web_cwd, links, kind, description)。`links`は(置く場所, 解決先)の列（`repo/`のルートからの相対パス）。
#   violated: 所有領域の外の`cwd`を持つワークスペース。`kind`: `ownership`（実パスの違反）、`lexical`（字句の違反）、`passed`（対照）。
CASES = {
    "MULTI-051-01": dict(argv=["verify", "--all-workspaces"], root_cwd="apps/web", web_cwd=".", links=[], kind="ownership", violated="platform",
                         description="ルートワークスペースのcwdがメンバーのルートの配下なら所有領域の外とし、そのテスト割当てだけを起動しない"),
    "MULTI-051-02": dict(argv=["verify", "platform::REQ-001"], root_cwd="lk", web_cwd=".", links=[("lk", "apps/web")], kind="ownership",
                         violated="platform",
                         description="ルートワークスペースのcwdがメンバーのルートの配下へ解決するシンボリックリンクなら所有領域の外とする"),
    "MULTI-051-03": dict(argv=["verify", "--all-workspaces"], root_cwd=".", web_cwd="esc", links=[("apps/web/esc", "../..")], kind="ownership",
                         violated="web",
                         description="メンバーのcwdがメンバーのルートの外へ解決するシンボリックリンクなら、そのテスト割当てだけを起動せず独立したテスト割当てを続ける"),
    "MULTI-051-04": dict(argv=["verify", "--workspace", "web", "web::REQ-101"], root_cwd=".", web_cwd="esc",
                         links=[("apps/web/esc", "../..")], kind="ownership", violated="web",
                         description="メンバーの単独のverifyも、cwdが所有領域の外へ解決するならテスト割当てを起動しない"),
    "MULTI-051-05": dict(argv=["verify", "--all-workspaces"], root_cwd="/tmp", web_cwd=".", links=[], kind="lexical", violated="platform",
                         description="ルートワークスペースのcwdが絶対パスなら設定の検査で止め、どのワークスペースも処理しない"),
    "MULTI-051-06": dict(argv=["verify", "--all-workspaces"], root_cwd="tests", web_cwd="tests", links=[], kind="passed", violated=None,
                         description="対照: 両方のcwdが自身の所有領域の中なら、どちらのテスト割当ても実行する"),
}


# --- 入力 -------------------------------------------------------------------------------

def command_block(cwd, quoted):
    text = f'"{cwd}"' if quoted else cwd
    return f'verify:\n  commands:\n    {COMMAND}:\n      argv: ["/bin/true", "{{tests}}"]\n      cwd: {text}\n'


def requirement_text(workspace, local, title, test_path):
    head = (f"---\nid: {local}\ntitle: {title}\nstatus: approved\n"
            f"tests:\n  - path: {test_path}\n    covers: [{local}:AC-01]\n    command: {COMMAND}\n---\n")
    return head + "\n" + requirement_body_text(local, title)


def requirement_body_text(local, title):
    return verify_fixtures.requirement_body(local, title, f"{local}:AC-01")


def reviewed_inputs(identifier):
    case = CASES[identifier]
    quoted = case["kind"] == "lexical"
    inputs = {
        multi_reference.ROOT_CONFIG_PATH: (multi_reference.root_config([MEMBER]) + command_block(case["root_cwd"], quoted)).encode(),
        multi_reference.WEB_CONFIG_PATH: (multi_reference.plain_config("web") + command_block(case["web_cwd"], False)).encode(),
    }
    for workspace, local, title, path, test_path in (ROOT_REQ, WEB_REQ):
        inputs[path] = requirement_text(workspace, local, title, test_path).encode()
    inputs["tests/test_platform.py"] = b"def test_platform():\n    assert True\n"
    inputs["apps/web/tests/test_web.py"] = b"def test_web():\n    assert True\n"
    return inputs


def reviewed_links(identifier):
    return dict(CASES[identifier]["links"])


def reviewed_manifest(identifier):
    case = CASES[identifier]
    status = reviewed_result(identifier)["status"]
    return {
        "fixtureId": identifier, "description": case["description"],
        "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
        "invocation": {"runner": "bitz", "cwd": ".", "argv": [*case["argv"], "--format", "json"], "env": {}},
        "expect": {"status": status, "exitCode": EXIT_BY_STATUS[status], "stdout": "json",
                   "resultFile": "expected/verify.json", "reportFileCount": 0},
    }


# --- 参照計算A: レビュー済みのハッシュ値の材料 -------------------------------------------------

def workspace_cwd(identifier, workspace):
    case = CASES[identifier]
    return case["root_cwd"] if workspace == "platform" else case["web_cwd"]


def digest_input(identifier, workspace):
    """検証対象`<workspace>::<REQ>`の、目的`verify`のハッシュ値の材料。到達するワークスペースは、そのワークスペースだけである。"""
    _, local, title, _, test_path = ROOT_REQ if workspace == "platform" else WEB_REQ
    qualified = f"{workspace}::{local}"
    document = verify_fixtures.document_material(
        None, qualified, workspace, "requirement", title, requirement_body_text(local, title),
        tests=[(test_path, f"{workspace}::{local}:AC-01", COMMAND)],
        statements=[verify_fixtures.statement_material(f"{workspace}::{local}:AC-01", "秘密情報を出力しない")])
    return {
        "digestVersion": "1.0", "specSchemaVersion": "1.0", "earsAiVersion": "1.0", "resolverVersion": "1.0",
        "purpose": "verify", "requestWorkspaceId": workspace, "roots": [qualified],
        "workspaces": [{"id": workspace, "path": WORKSPACE_ROOTS[workspace]}],
        "documents": [document], "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [{"id": workspace, "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [{"workspaceId": workspace, "timeoutSeconds": 300}],
            "commands": [{"workspaceId": workspace, "name": COMMAND, "argv": ["/bin/true", "{tests}"],
                          "cwd": workspace_cwd(identifier, workspace)}],
        },
    }


def digest(identifier, workspace):
    return multi_reference.digest(multi_reference.canonical_bytes(digest_input(identifier, workspace)))


# --- レビュー済みの期待結果 ---------------------------------------------------------------

def ownership_diagnostic(identifier, workspace):
    path = workspace_cwd(identifier, workspace)
    return {"code": "SPEC-MULTI-OWNERSHIP-001", "severity": "error", "resultStatus": "failed",
            "summary": OWNERSHIP_SUMMARY.format(path=path, workspace=workspace),
            "source": {"kind": "file", "workspaceId": workspace, "path": CONFIG_PATH, "key": KEY}}


def lexical_diagnostic():
    return {"code": "SPEC-CONFIG-SCHEMA-001", "severity": "error", "resultStatus": "error", "summary": LEXICAL_SUMMARY,
            "source": {"kind": "file", "workspaceId": None, "path": CONFIG_PATH, "key": KEY}}


def target_entry(identifier, workspace, blocked):
    _, local, _, _, _ = ROOT_REQ if workspace == "platform" else WEB_REQ
    return {"target": f"{workspace}::{local}", "status": "blocked" if blocked else "passed",
            "contextDigest": digest(identifier, workspace), "statements": [f"{workspace}::{local}:AC-01"],
            "bindingRefs": [] if blocked else [f"{workspace}::{COMMAND}"], "diagnostics": []}


def command_entry(identifier, workspace):
    _, local, _, _, test_path = ROOT_REQ if workspace == "platform" else WEB_REQ
    cwd = workspace_cwd(identifier, workspace)
    # `cwd`が`tests`のときは、テストのパスを`cwd`からの相対で展開する（ワークスペース・設定仕様 §6）。
    expanded = test_path.removeprefix("tests/") if cwd == "tests" else test_path
    return {
        "bindingId": f"{workspace}::{COMMAND}", "workspaceId": workspace, "name": COMMAND, "status": "passed",
        "termination": "exit", "cwd": cwd, "argv": ["/bin/true", expanded], "tests": [test_path],
        "covers": [f"{workspace}::{local}:AC-01"], "exitCode": 0, "timeoutSeconds": 300,
        "stdoutExcerpt": "", "stderrExcerpt": "", "stdoutTruncated": False, "stderrTruncated": False, "durationMs": 0}


def reviewed_result(identifier):
    case = CASES[identifier]
    revision = {"commit": COMMIT, "dirty": False}
    if case["kind"] == "lexical":
        # 全体事前検査（設定の検査）で止まるので、ワークスペースの処理を始めない。
        return {"schemaVersion": "1.0", "operation": "verify", "scope": "all-workspaces", "status": "error",
                "multiWorkspace": {"id": None, "path": "."}, "workspaces": [], "revision": revision,
                "durationMs": 0, "diagnostics": [lexical_diagnostic()]}
    violated = case["violated"]
    status = "failed" if violated else "passed"
    if "--all-workspaces" not in case["argv"]:
        # 単独の`verify`: ワークスペースの配列を持たず、最上位の`diagnostics`へ置く。
        workspace = case["violated"]
        return {"schemaVersion": "1.0", "operation": "verify", "scope": "selected", "status": status,
                "workspace": {"id": workspace, "path": WORKSPACE_ROOTS[workspace]},
                "targetResults": [target_entry(identifier, workspace, True)], "revision": revision, "commands": [],
                "durationMs": 0, "diagnostics": [ownership_diagnostic(identifier, workspace)]}
    entries = []
    for workspace in ("platform", "web"):
        blocked = workspace == violated
        entries.append({
            "id": workspace, "path": WORKSPACE_ROOTS[workspace], "status": "failed" if blocked else "passed",
            "targetResults": [target_entry(identifier, workspace, blocked)],
            "commands": [] if blocked else [command_entry(identifier, workspace)],
            "durationMs": 0, "diagnostics": [ownership_diagnostic(identifier, workspace)] if blocked else []})
    return {"schemaVersion": "1.0", "operation": "verify", "scope": "all-workspaces", "status": status,
            "multiWorkspace": {"id": ROOT_ID, "path": "."}, "workspaces": entries, "revision": revision,
            "durationMs": 0, "diagnostics": []}


def reviewed_effects(identifier, state):
    return {"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}


# --- 参照計算（準備手順の後の入力から導く） -----------------------------------------------------

def configured_cwd(repository, config_path):
    text = (repository / config_path).read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("cwd:")]
    if len(lines) != 1:
        raise ValueError("設定は`cwd`を1件だけ持つ必要があります")
    value = lines[0].split(":", 1)[1].strip()
    return value[1:-1] if value[:1] == '"' else value


def reference_violations(repository):
    """入力の`cwd`と実パスから、(字句の違反のワークスペース, 所有領域の外のワークスペース)を導く（複合ワークスペース仕様 §5.1）。"""
    cwds = {"platform": configured_cwd(repository, multi_reference.ROOT_CONFIG_PATH),
            "web": configured_cwd(repository, multi_reference.WEB_CONFIG_PATH)}
    lexical = sorted(name for name, cwd in cwds.items() if lexical_violation(cwd))
    roots = {name: os.path.realpath(repository / path) for name, path in WORKSPACE_ROOTS.items()}
    outside = []
    for name, cwd in cwds.items():
        if name in lexical:
            continue
        real = os.path.realpath(repository / WORKSPACE_ROOTS[name] / cwd)
        # 所有領域は自身のルートの配下。ルートワークスペースは、メンバーのルートの配下を所有しない。
        violated = not within(real, roots[name])
        if name == "platform":
            violated = violated or any(within(real, root) for other, root in roots.items() if other != name)
        if violated:
            outside.append(name)
    return lexical, sorted(outside)


def check_conditions(identifier, repository, manifest, result):
    case = CASES[identifier]
    lexical, outside = reference_violations(repository)
    expected = ([case["violated"]], []) if case["kind"] == "lexical" else ([], [case["violated"]] if case["violated"] else [])
    if (lexical, outside) != expected:
        raise ValueError(f"入力から導く違反が期待と異なります: {lexical}, {outside}")
    for name, target in reviewed_links(identifier).items():
        path = repository / name
        if not path.is_symlink() or os.readlink(path) != target:
            raise ValueError("シンボリックリンクがレビュー済みの入力と異なります")
    status = "error" if lexical else "failed" if outside else "passed"
    if result["status"] != status or (manifest["expect"]["status"], manifest["expect"]["exitCode"]) != (status, EXIT_BY_STATUS[status]):
        raise ValueError("状態または終了コードが参照計算と異なります")
    # 違反の診断は1件だけで、違反していないワークスペースの診断・コマンドは変わらない。
    diagnostics = list(result["diagnostics"]) + [d for entry in result.get("workspaces", []) for d in entry["diagnostics"]]
    if len(diagnostics) != len(lexical) + len(outside):
        raise ValueError("診断は違反1件につき1件である必要があります")
    commands = [c for entry in result.get("workspaces", []) for c in entry["commands"]] + list(result.get("commands", []))
    started = {c["workspaceId"] for c in commands}
    if "--all-workspaces" not in case["argv"] or status == "error":
        want = set()
    else:
        want = {"platform", "web"} - set(outside)
    if started != want:
        raise ValueError("起動するテスト割当てが参照計算と異なります")


def check_digests(identifier, repository, result):
    entries = [t for e in result.get("workspaces", []) for t in e["targetResults"]] + list(result.get("targetResults", []))
    for entry in entries:
        derived = multi_crosscheck.canonical_bytes(multi_crosscheck.build(repository, entry["target"]))
        if multi_crosscheck.digest(derived) != entry["contextDigest"]:
            raise ValueError(f"{entry['target']}のハッシュ値が参照計算Bと一致しません")
        if multi_reference.canonical_bytes(digest_input(identifier, entry["target"].partition("::")[0])) != derived:
            raise ValueError(f"{entry['target']}のハッシュ値の参照計算AとBが一致しません")
    return len(entries)


# --- 書き出しと監査 ---------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def generate(root=HERE):
    for identifier in CASES:
        fixture = root / "multi" / identifier
        for name, content in reviewed_inputs(identifier).items():
            path = fixture / "repo" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        for name, target in reviewed_links(identifier).items():
            link = fixture / "repo" / name
            link.parent.mkdir(parents=True, exist_ok=True)
            if link.is_symlink():
                link.unlink()
            link.symlink_to(target)
        manifest = reviewed_manifest(identifier)
        (fixture / "expected").mkdir(parents=True, exist_ok=True)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected/verify.json").write_text(_dump(reviewed_result(identifier)))
        with tempfile.TemporaryDirectory(prefix="bitz-multi-command-cwd-") as temporary:
            sandbox = Path(temporary)
            repository = setup(fixture, manifest, sandbox / "repo")
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            state = observe(repository, external)
        (fixture / "side-effects.json").write_text(_dump(reviewed_effects(identifier, state)))


def actual_entries(fixture):
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
        fixture = root / "multi" / identifier
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / "expected/verify.json").read_text())
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
            if {path.relative_to(fixture).as_posix() for path in (fixture / "expected").glob("*")} != {"expected/verify.json"}:
                raise ValueError("期待値のファイルがレビュー済みの集合と異なります")
            if effects["before"] != effects["after"]:
                raise ValueError("既に存在したパスはすべて不変である必要があります")
            previous = None
            with tempfile.TemporaryDirectory(prefix="bitz-multi-command-cwd-") as temporary:
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
                    if CASES[identifier]["kind"] != "lexical":
                        check_digests(identifier, repository, result)
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "references": 2, "status": "Passed" if not errors else "Failed", "errors": errors}
