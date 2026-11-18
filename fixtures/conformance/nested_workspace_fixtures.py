"""入れ子のワークスペースをTASK境界から除くことと、予約したディレクトリ`.spec/journal`と`.spec/plans`を固定する（Coreの公開操作は実行しない）。

[ADR-074](../../docs/02.設計書/10_決定記録/ADR-074_入れ子のワークスペースをTASK境界から除き、経過の記録と計画の置き場を予約する.md)、
[`check`仕様 §7](../../docs/03.詳細設計/03_操作仕様/02_check.md#7-task境界)の入れ子のワークスペースの段落、
[ワークスペース・設定仕様 §3](../../docs/03.詳細設計/02_仕様文書モデル/01_ワークスペース・設定仕様.md#3-探索対象)、
診断レジストリの`WORKSPACE-ENTRY-UNKNOWN`を根拠とする。

TASK境界（`SINGLE-184-*`、`check TASK-001 --base HEAD`）:

| fixture | 入力と変更 | 期待 |
|---|---|---|
| `SINGLE-184-01` | 基準版に`sandbox/exp1/.spec/bitz.yaml`と`sandbox/exp1/note.md`。`note.md`を変える（未ステージ） | `passed`。入れ子のワークスペースの配下の変更を除く |
| `SINGLE-184-02` | 対照: `01`から`sandbox/exp1/.spec/bitz.yaml`を除く | `failed`。`sandbox/exp1/note.md`の`SPEC-TASK-BOUNDARY-001` |
| `SINGLE-184-03` | 基準版に`note.md`だけ。`sandbox/exp1/.spec/bitz.yaml`を追加してステージし、`note.md`を変える | `passed`。基準版になくインデックスと作業ツリーにある設定でも入れ子とし、設定自身の追加も除く |
| `SINGLE-184-04` | `01`の基準版。`sandbox/exp1/.spec/bitz.yaml`を作業ツリーで削除する（未ステージ） | `passed`。設定自身の削除を除く |
| `SINGLE-184-05` | `01`の基準版。設定の削除をステージし、`note.md`を変える | `passed`。基準版にだけある設定でも入れ子とする |
| `SINGLE-184-06` | `01`の設定をシンボリックリンク（`../../../.spec/bitz.yaml`）にする | `failed`。入れ子にしない |
| `SINGLE-184-07` | `sandbox/exp1/.spec`をシンボリックリンク（`../cfg`、`sandbox/cfg/bitz.yaml`あり）にする | `failed`。シンボリックリンクをたどらない |
| `SINGLE-184-08` | `a/.spec/bitz.yaml`と`a/b/.spec/bitz.yaml`。`a/top.md`と`a/b/deep.md`を変える | `passed`。入れ子の入れ子も除く |
| `SINGLE-184-09` | `tools/lab/exp/.spec/bitz.yaml`（2段の下位）。`tools/lab/exp/n.md`と`tools/lab/other.md`を変える | `failed`。`tools/lab/other.md`の1件だけ |
| `SINGLE-184-10` | `sandbox/exp1`だけが入れ子。`sandbox/exp1/note.md`と`sandbox/exp10/note.md`を変える | `failed`。`sandbox/exp10/note.md`の1件だけ（セグメントの境界） |
| `SINGLE-184-11` | 入れ子の設定のYAMLの構文が不正（`SINGLE-127-43`と同じ設定）。`note.md`を変える | `passed`。診断なし（設定の内容を読まない） |
| `SINGLE-184-12` | 入れ子の設定を作業ツリーで構文の不正な設定へ変える。ほかの変更はない | `passed`。診断なし |
| `SINGLE-184-13` | ワークスペースのルートは`app/`（リポジトリのルートの下位）。`app/sandbox/x/.spec/bitz.yaml`。`app/sandbox/x/note.md`を変え、`app`で実行 | `passed` |
| `SINGLE-184-14` | `13`に`app/sandbox/y.md`を足し、両方を変える | `failed`。ワークスペース相対の`sandbox/y.md`の1件だけ |
| `SINGLE-184-15` | TASKの`changes`が`[src/, sandbox/exp1/note.md]`（入れ子の配下を指す）。`note.md`と`src2/outside.py`を変える | `failed`。`src2/outside.py`の1件だけ |
| `SINGLE-184-16` | `01`の基準版。作業ワークスペース自身の`.spec/bitz.yaml`と`note.md`を変える | `failed`。`.spec/bitz.yaml`の1件だけ（自身のルートは入れ子に含めない） |
| `SINGLE-184-17` | `01`の基準版。`sandbox/exp1/new.md`を未追跡で作る | `passed`。未追跡の変更も除く |

予約したディレクトリ（`SINGLE-185-*`、`MULTI-070-01`）:

| fixture | 操作 | 入力 | 期待 |
|---|---|---|---|
| `SINGLE-185-01` | `check --full --base HEAD` | `.spec/journal/`にMarkdown（`REQ-001`と同じID、種別のディレクトリの名前の下位も含む）、壊れたフロントマターのMarkdown、サブディレクトリのテキスト | `passed`。診断0件、検査文書1 |
| `SINGLE-185-02` | 同上 | `.spec/plans/`に同じ形の中身 | 同上 |
| `SINGLE-185-03` | 同上 | `.spec/journal`が通常のファイル | 同上 |
| `SINGLE-185-04` | 同上 | `.spec/journal`がシンボリックリンク（`../docs/journal`。重複したIDと壊れたフロントマターのMarkdownを持つ） | 同上 |
| `SINGLE-185-05` | 同上 | `01`の`.spec/journal/`と、似た名前の未知のファイル`.spec/journal.txt`、`.spec/plans.txt` | `passed_with_warnings`。未知のファイルの2件だけ |
| `SINGLE-185-06` | `context REQ-001 --purpose verify` | `SINGLE-042`の入力に`.spec/journal/`と`.spec/plans/` | `SINGLE-042`と同じ結果 |
| `SINGLE-185-07` | `verify REQ-001` | `SINGLE-055`の入力に同じ2つのディレクトリ | `SINGLE-055`と同じ結果 |
| `SINGLE-185-08` | `doctor` | `SINGLE-001`の入力に同じ2つのディレクトリ | `SINGLE-001`と同じ結果 |
| `MULTI-070-01` | `check --all-workspaces --base HEAD` | `MULTI-053-04`の入力から、メンバー`web`の設定の警告の原因（BOM、`profiles`）と未知のファイルを除き、`web`の`.spec/journal/`と`.spec/plans/`を置く | `passed`。どのワークスペースにも診断なし |

期待値の根拠は規範文と、このモジュールの参照計算（`reference_violations`、`unknown_entries`）だけである。Coreの出力は根拠にしない。
参照計算は、隔離した準備手順の後のGitの`HEAD`の木構造、インデックス、作業ツリーから、§5の変更集合、入れ子のワークスペースのルート
（`HEAD`またはインデックスと作業ツリーにある通常のファイルの`.spec/bitz.yaml`。シンボリックリンクを経由しない）、境界の外の変更を導き、
レビュー済みのリテラルの診断と一致することを確かめる。未追跡の`.spec/bitz.yaml`と、無視された`.spec/bitz.yaml`を入れ子のルートに数えるかは
仕様が一意に決めないので（レビュー記録）、そのような入力を置かない。参照計算もそれを拒否する。

`SINGLE-185-06`〜`08`と`MULTI-070-01`は、レビュー済みの既存のfixture（`SINGLE-042`・`055`・`001`・`MULTI-053-04`）の入力に予約したディレクトリを足し、
期待結果をそこから導く。予約したディレクトリは読まないので、コンテキストのハッシュ値を含めて結果は変わらない。基のfixtureが変われば、この群の監査が失敗する。
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

from jsonschema import Draft202012Validator, ValidationError

from .document_fixtures import DOCUMENT, REQ_PATH
from .harness import git, setup
from .initial_fixtures import CONFIGS, compare_state, observe
from .schemas import schema_path
from .workspace_selection_fixtures import SYNTAX_CONFIG

HERE = Path(__file__).resolve().parent
COMMIT = "0" * 40
CONFIG_PATH = ".spec/bitz.yaml"
CONFIG = CONFIGS["SINGLE-001"].encode()
TASK_PATH = ".spec/tasks/TASK-001.md"
BOUNDARY = "SPEC-TASK-BOUNDARY-001"
UNKNOWN = "SPEC-WORKSPACE-UNKNOWN-001"
# 承認済みの文言（Coreの出力文言のレビュー記録.md #137、#151）。
BOUNDARY_SUMMARY = "パス{path}はTASK-001の変更許可パスの外です"
UNKNOWN_FILE_SUMMARY = ".spec/内の未知のファイルを仕様文書として読みません"
# ワークスペース・設定仕様 §3の既知のエントリ（`.spec/`の直下）。
KNOWN_ENTRIES = {"bitz.yaml", "requirements", "technical", "decisions", "tasks", "reports", "journal", "plans"}
RESERVED = ("journal", "plans")


class Link(str):
    """シンボリックリンクのリンク先（入力の木構造の値）。"""


def task(changes):
    listed = ", ".join(changes)
    return (f"---\nid: TASK-001\ntitle: 変更境界の検査\nstatus: open\nchanges: [{listed}]\n---\n\n"
            "# TASK-001 変更境界の検査\n\n## Objective\n\n入れ子のワークスペースを除いた変更境界を確認する。\n").encode()


INSIDE = b"# unchanged allowed path\n"
OUTSIDE_BEFORE, OUTSIDE_AFTER = b"# before\n", b"# after\n"
NOTE_BEFORE, NOTE_AFTER = "# 検証のメモ\n\n変更前。\n".encode(), "# 検証のメモ\n\n変更後。\n".encode()
NEW_NOTE = "# 新しい検証のメモ\n".encode()
BROKEN_CONFIG = SYNTAX_CONFIG.encode()
# 作業ワークスペース自身の設定へ、既定値と同じ標準のキーを足す（ワークスペース・設定仕様 §5。設定の診断を出さない）。
OUTER_CONFIG_AFTER = CONFIG + b"context:\n  maxDocuments: 20\n"
BASE_TASK = {CONFIG_PATH: CONFIG, TASK_PATH: task(["src/"]), "src/inside.py": INSIDE}
NESTED = "sandbox/exp1"


def nested(prefix=NESTED, config=CONFIG):
    return {f"{prefix}/.spec/bitz.yaml": config, f"{prefix}/note.md": NOTE_BEFORE}


def prefixed(prefix, tree):
    return {f"{prefix}/{path}": value for path, value in tree.items()}


def update(path, source):
    return {"op": "update", "path": path, "source": source}


# 予約したディレクトリの中身。仕様文書として読めば、IDの重複（`REQ-001`）、ファイル名とIDの不一致、フロントマターの構文の不正になる。
BROKEN_DOCUMENT = "---\nid: REQ-009\ntitle: [閉じていない\n---\n\n# 壊れたフロントマター\n".encode()
TEXT = "経過の記録の中身の形式はCore 1.0では定めない。\n".encode()


def reserved(name):
    base = f".spec/{name}"
    return {f"{base}/2026-11-18.md": DOCUMENT.encode(), f"{base}/requirements/REQ-001.md": DOCUMENT.encode(),
            f"{base}/broken.md": BROKEN_DOCUMENT, f"{base}/sub/notes.txt": TEXT}


BASE_DOCUMENT = {CONFIG_PATH: CONFIG, REQ_PATH: DOCUMENT.encode()}

# TASK境界: id -> dict(repo, changes, operations, cwd, workspace（リポジトリ相対のワークスペースのルート）, violations, description)
TASK_CASES = {
    "SINGLE-184-01": dict(repo={**BASE_TASK, **nested()}, changes={"note.md": NOTE_AFTER},
                          operations=[update(f"{NESTED}/note.md", "changes/note.md")], violations=[],
                          description="作業ツリーと基準版に.spec/bitz.yamlを持つ入れ子のワークスペースの配下の変更は、TASK境界の比較から除く"),
    "SINGLE-184-02": dict(repo={**BASE_TASK, f"{NESTED}/note.md": NOTE_BEFORE}, changes={"note.md": NOTE_AFTER},
                          operations=[update(f"{NESTED}/note.md", "changes/note.md")], violations=[f"{NESTED}/note.md"],
                          description="対照: .spec/bitz.yamlのないディレクトリの配下の変更は、今どおりTASK境界の外になる"),
    "SINGLE-184-03": dict(repo={**BASE_TASK, f"{NESTED}/note.md": NOTE_BEFORE},
                          changes={"bitz.yaml": CONFIG, "note.md": NOTE_AFTER},
                          operations=[{"op": "create", "path": f"{NESTED}/.spec/bitz.yaml", "source": "changes/bitz.yaml"},
                                      {"op": "stage", "paths": [f"{NESTED}/.spec/bitz.yaml"]},
                                      update(f"{NESTED}/note.md", "changes/note.md")], violations=[],
                          description="基準版になく、ステージして作業ツリーにある.spec/bitz.yamlも入れ子のワークスペースとし、設定自身の追加も除く"),
    "SINGLE-184-04": dict(repo={**BASE_TASK, **nested()}, changes={},
                          operations=[{"op": "delete", "path": f"{NESTED}/.spec/bitz.yaml"}], violations=[],
                          description="基準版にある入れ子のワークスペースの.spec/bitz.yamlを作業ツリーで削除しても、設定自身の削除として除く"),
    "SINGLE-184-05": dict(repo={**BASE_TASK, **nested()}, changes={"note.md": NOTE_AFTER},
                          operations=[{"op": "delete", "path": f"{NESTED}/.spec/bitz.yaml"},
                                      {"op": "stage", "paths": [f"{NESTED}/.spec/bitz.yaml"]},
                                      update(f"{NESTED}/note.md", "changes/note.md")], violations=[],
                          description="基準版にだけある.spec/bitz.yamlも入れ子のワークスペースとし、削除をステージしても配下の変更を除く"),
    "SINGLE-184-06": dict(repo={**BASE_TASK, f"{NESTED}/.spec/bitz.yaml": Link("../../../.spec/bitz.yaml"),
                                f"{NESTED}/note.md": NOTE_BEFORE}, changes={"note.md": NOTE_AFTER},
                          operations=[update(f"{NESTED}/note.md", "changes/note.md")], violations=[f"{NESTED}/note.md"],
                          description="シンボリックリンクの.spec/bitz.yamlを持つディレクトリは入れ子のワークスペースにせず、配下の変更はTASK境界の外になる"),
    "SINGLE-184-07": dict(repo={**BASE_TASK, f"{NESTED}/.spec": Link("../cfg"), "sandbox/cfg/bitz.yaml": CONFIG,
                                f"{NESTED}/note.md": NOTE_BEFORE}, changes={"note.md": NOTE_AFTER},
                          operations=[update(f"{NESTED}/note.md", "changes/note.md")], violations=[f"{NESTED}/note.md"],
                          description=".specがシンボリックリンクのディレクトリはリンクをたどらず入れ子のワークスペースにしない"),
    "SINGLE-184-08": dict(repo={**BASE_TASK, "a/.spec/bitz.yaml": CONFIG, "a/b/.spec/bitz.yaml": CONFIG,
                                "a/top.md": NOTE_BEFORE, "a/b/deep.md": NOTE_BEFORE},
                          changes={"top.md": NOTE_AFTER, "deep.md": NOTE_AFTER},
                          operations=[update("a/top.md", "changes/top.md"), update("a/b/deep.md", "changes/deep.md")],
                          violations=[], description="入れ子のワークスペースの中の入れ子のワークスペースの配下の変更も除く"),
    "SINGLE-184-09": dict(repo={**BASE_TASK, "tools/lab/exp/.spec/bitz.yaml": CONFIG, "tools/lab/exp/n.md": NOTE_BEFORE,
                                "tools/lab/other.md": NOTE_BEFORE},
                          changes={"n.md": NOTE_AFTER, "other.md": NOTE_AFTER},
                          operations=[update("tools/lab/exp/n.md", "changes/n.md"),
                                      update("tools/lab/other.md", "changes/other.md")],
                          violations=["tools/lab/other.md"],
                          description="2段の下位の入れ子のワークスペースの配下だけを除き、その外の上位のディレクトリの変更はTASK境界の外になる"),
    "SINGLE-184-10": dict(repo={**BASE_TASK, **nested(), "sandbox/exp10/note.md": NOTE_BEFORE},
                          changes={"note.md": NOTE_AFTER},
                          operations=[update(f"{NESTED}/note.md", "changes/note.md"),
                                      update("sandbox/exp10/note.md", "changes/note.md")],
                          violations=["sandbox/exp10/note.md"],
                          description="入れ子のワークスペースのルートの除外はセグメントの境界で行い、sandbox/exp10を除かない"),
    "SINGLE-184-11": dict(repo={**BASE_TASK, **nested(config=BROKEN_CONFIG)}, changes={"note.md": NOTE_AFTER},
                          operations=[update(f"{NESTED}/note.md", "changes/note.md")], violations=[],
                          description="入れ子のワークスペースの設定のYAMLの構文が不正でも内容を読まず、有無だけで除き、設定の診断を出さない"),
    "SINGLE-184-12": dict(repo={**BASE_TASK, **nested()}, changes={"bitz.yaml": BROKEN_CONFIG},
                          operations=[update(f"{NESTED}/.spec/bitz.yaml", "changes/bitz.yaml")], violations=[],
                          description="入れ子のワークスペースの設定を構文の不正な設定へ変えても、配下の変更として除き、設定の診断を出さない"),
    "SINGLE-184-13": dict(repo={**prefixed("app", BASE_TASK), **nested("app/sandbox/x")}, changes={"note.md": NOTE_AFTER},
                          operations=[update("app/sandbox/x/note.md", "changes/note.md")], cwd="app", workspace="app",
                          violations=[], description="リポジトリのルートがワークスペースのルートより上にあっても、入れ子のワークスペースの配下の変更を除く"),
    "SINGLE-184-14": dict(repo={**prefixed("app", BASE_TASK), **nested("app/sandbox/x"), "app/sandbox/y.md": NOTE_BEFORE},
                          changes={"note.md": NOTE_AFTER},
                          operations=[update("app/sandbox/x/note.md", "changes/note.md"),
                                      update("app/sandbox/y.md", "changes/note.md")], cwd="app", workspace="app",
                          violations=["sandbox/y.md"],
                          description="リポジトリのルートがワークスペースのルートより上にあるとき、入れ子の外の変更をワークスペース相対のパスで報告する"),
    "SINGLE-184-15": dict(repo={**BASE_TASK, TASK_PATH: task(["src/", f"{NESTED}/note.md"]), **nested(),
                                "src2/outside.py": OUTSIDE_BEFORE},
                          changes={"note.md": NOTE_AFTER, "outside.py": OUTSIDE_AFTER},
                          operations=[update(f"{NESTED}/note.md", "changes/note.md"),
                                      update("src2/outside.py", "changes/outside.py")],
                          violations=["src2/outside.py"],
                          description="TASKのchangesが入れ子のワークスペースの配下を指しても検査は今どおりで、ほかの境界の外の変更を検出する"),
    "SINGLE-184-16": dict(repo={**BASE_TASK, **nested()}, changes={"bitz.yaml": OUTER_CONFIG_AFTER, "note.md": NOTE_AFTER},
                          operations=[update(CONFIG_PATH, "changes/bitz.yaml"), update(f"{NESTED}/note.md", "changes/note.md")],
                          violations=[CONFIG_PATH],
                          description="作業ワークスペース自身のルートは入れ子のワークスペースに含めず、自身の設定の変更はTASK境界の外になる"),
    "SINGLE-184-17": dict(repo={**BASE_TASK, **nested()}, changes={"new.md": NEW_NOTE},
                          operations=[{"op": "create", "path": f"{NESTED}/new.md", "source": "changes/new.md"}], violations=[],
                          description="入れ子のワークスペースの配下の未追跡のファイルも、TASK境界の比較から除く"),
}

# 予約したディレクトリ: id -> dict(kind, ...)。`check`は`BASE_DOCUMENT`に`extra`を足す。`derived`は基のfixtureの入力に足し、期待結果を基から導く。
RESERVED_CASES = {
    "SINGLE-185-01": dict(kind="check", extra=reserved("journal"), unknown=[],
                          description=".spec/journal/の中のファイル、サブディレクトリ、Markdown、壊れたフロントマターを読まず、未知のエントリにしない"),
    "SINGLE-185-02": dict(kind="check", extra=reserved("plans"), unknown=[],
                          description=".spec/plans/の中のファイル、サブディレクトリ、Markdown、壊れたフロントマターを読まず、未知のエントリにしない"),
    "SINGLE-185-03": dict(kind="check", extra={".spec/journal": TEXT}, unknown=[],
                          description=".spec/journalが通常のファイルでも既知のエントリとし、未知のエントリにしない"),
    "SINGLE-185-04": dict(kind="check", extra={".spec/journal": Link("../docs/journal"),
                                               "docs/journal/2026-11-18.md": DOCUMENT.encode(),
                                               "docs/journal/broken.md": BROKEN_DOCUMENT}, unknown=[],
                          description=".spec/journalがシンボリックリンクでも既知のエントリとし、リンクをたどらず、未知のエントリにしない"),
    "SINGLE-185-05": dict(kind="check", extra={**reserved("journal"), ".spec/journal.txt": TEXT, ".spec/plans.txt": TEXT},
                          unknown=[".spec/journal.txt", ".spec/plans.txt"],
                          description="対照: 予約した名前と完全に一致しない.spec/journal.txtと.spec/plans.txtは未知のファイルとして警告する"),
    "SINGLE-185-06": dict(kind="derived", base="SINGLE-042",
                          description="contextは.spec/journal/と.spec/plans/を読まず、SINGLE-042と同じ結果とコンテキストのハッシュ値を返す"),
    "SINGLE-185-07": dict(kind="derived", base="SINGLE-055",
                          description="verifyは.spec/journal/と.spec/plans/を読まず、SINGLE-055と同じ結果を返す"),
    "SINGLE-185-08": dict(kind="derived", base="SINGLE-001",
                          description="doctorは.spec/journal/と.spec/plans/があっても、SINGLE-001と同じ結果を返す"),
}
MULTI_BASE = "MULTI-053-04"
MULTI_MEMBER = "apps/web"
MULTI_CASES = {
    "MULTI-070-01": dict(description="複合ワークスペースのメンバーの.spec/journal/と.spec/plans/を読まず、未知のエントリにしない"),
}
CASES = {**TASK_CASES, **RESERVED_CASES, **MULTI_CASES}
BOM = b"\xef\xbb\xbf"
PROFILES_LINE = b"profiles: legacy-profile\n"


def fixture_dir(root, identifier):
    return root / ("multi" if identifier.startswith("MULTI-") else "single") / identifier


# --- 入力 -------------------------------------------------------------------------------------

def read_tree(directory):
    """(パス -> bytes（通常のファイル。実行ビットは別）またはLink)と、実行ビットの集合。シンボリックリンクはたどらない。"""
    tree, executable = {}, set()
    if not directory.is_dir():
        return tree, executable
    for current, directories, files in os.walk(directory, followlinks=False):
        for name in sorted(directories + files):
            path = Path(current) / name
            relative = path.relative_to(directory).as_posix()
            if path.is_symlink():
                tree[relative] = Link(os.readlink(path))
            elif path.is_file():
                tree[relative] = path.read_bytes()
                if path.stat().st_mode & 0o111:
                    executable.add(relative)
    return tree, executable


def base_fixture(identifier):
    base = RESERVED_CASES[identifier]["base"] if identifier in RESERVED_CASES else MULTI_BASE
    return fixture_dir(HERE, base)


def reviewed_inputs(identifier):
    """`repo/`の木構造、実行ビットの集合、`changes/`の木構造。"""
    if identifier in TASK_CASES:
        case_ = TASK_CASES[identifier]
        return dict(case_["repo"]), set(), dict(case_["changes"])
    if identifier in RESERVED_CASES:
        case_ = RESERVED_CASES[identifier]
        if case_["kind"] == "check":
            return {**BASE_DOCUMENT, **case_["extra"]}, set(), {}
        tree, executable = read_tree(base_fixture(identifier) / "repo")
        if any(path.startswith((".spec/journal", ".spec/plans")) for path in tree):
            raise ValueError("基のfixtureがすでに予約したディレクトリを持っています")
        return {**tree, **reserved("journal"), **reserved("plans")}, executable, {}
    # 複合ワークスペース: 基の`MULTI-053-04`から、`web`の設定の警告の原因と未知のファイルを除き、予約したディレクトリを置く。
    tree, executable = read_tree(base_fixture(identifier) / "repo")
    member_config = f"{MULTI_MEMBER}/{CONFIG_PATH}"
    content = tree[member_config]
    if not content.startswith(BOM) or content.count(PROFILES_LINE) != 1:
        raise ValueError("基のfixtureのメンバーの設定がレビュー済みの形と異なります")
    tree[member_config] = content[len(BOM):].replace(PROFILES_LINE, b"")
    for name in ("aaa.txt", "notes.txt"):
        del tree[f"{MULTI_MEMBER}/.spec/{name}"]
    tree.update(prefixed(MULTI_MEMBER, {**reserved("journal"), **reserved("plans")}))
    return tree, executable, {}


def write_tree(directory, tree, executable=()):
    for relative, value in sorted(tree.items()):
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, Link):
            path.symlink_to(str(value))
        else:
            path.write_bytes(value)
            path.chmod(0o755 if relative in executable else 0o644)


# --- 起動と期待値 ---------------------------------------------------------------------------

def base_manifest(identifier):
    return json.loads((base_fixture(identifier) / "manifest.json").read_text())


def reviewed_manifest(identifier):
    description = CASES[identifier]["description"]
    if identifier in TASK_CASES:
        case_ = TASK_CASES[identifier]
        status = "failed" if case_["violations"] else "passed"
        return {"fixtureId": identifier, "description": description,
                "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]},
                          "operations": copy.deepcopy(case_["operations"])},
                "invocation": {"runner": "bitz", "cwd": case_.get("cwd", "."),
                               "argv": ["check", "TASK-001", "--base", "HEAD", "--format", "json"], "env": {}},
                "expect": {"status": status, "exitCode": 1 if status == "failed" else 0, "stdout": "json",
                           "resultFile": "expected/check.json", "reportFileCount": 0}}
    if identifier in RESERVED_CASES and RESERVED_CASES[identifier]["kind"] == "check":
        status = "passed_with_warnings" if RESERVED_CASES[identifier]["unknown"] else "passed"
        return {"fixtureId": identifier, "description": description,
                "setup": {"git": True, "baseCommit": {"message": "base", "paths": ["."]}, "operations": []},
                "invocation": {"runner": "bitz", "cwd": ".",
                               "argv": ["check", "--full", "--base", "HEAD", "--format", "json"], "env": {}},
                "expect": {"status": status, "exitCode": 0, "stdout": "json",
                           "resultFile": "expected/check.json", "reportFileCount": 0}}
    manifest = base_manifest(identifier)
    manifest["fixtureId"] = identifier
    manifest["description"] = description
    if identifier in MULTI_CASES:
        manifest["expect"]["status"] = "passed"
    return manifest


def operation(identifier):
    return reviewed_manifest(identifier)["invocation"]["argv"][0]


def expected_name(identifier):
    return f"expected/{operation(identifier)}.json"


def diagnostic(code, severity, status, summary, path):
    return {"code": code, "severity": severity, "resultStatus": status, "summary": summary,
            "source": {"kind": "file", "workspaceId": "root", "path": path}}


def reviewed_result(identifier):
    if identifier in TASK_CASES:
        violations = TASK_CASES[identifier]["violations"]
        # 明示したTASKは`scope: selected`。完全検査の対象はTASK-001だけ（規範文0）。作業ツリーに変更があるので`dirty`は真。
        return {"schemaVersion": "1.0", "operation": "check", "status": "failed" if violations else "passed",
                "scope": "selected", "workspace": {"id": "root", "path": "."},
                "revision": {"base": COMMIT, "commit": COMMIT, "dirty": True},
                "checkedDocumentCount": 1, "checkedStatementCount": 0, "durationMs": 0,
                "diagnostics": [diagnostic(BOUNDARY, "error", "failed", BOUNDARY_SUMMARY.format(path=path), path)
                                for path in violations]}
    if identifier in RESERVED_CASES and RESERVED_CASES[identifier]["kind"] == "check":
        unknown = RESERVED_CASES[identifier]["unknown"]
        status = "passed_with_warnings" if unknown else "passed"
        return {"schemaVersion": "1.0", "operation": "check", "status": status, "scope": "full",
                "workspace": {"id": "root", "path": "."},
                "revision": {"base": COMMIT, "commit": COMMIT, "dirty": False},
                "checkedDocumentCount": 1, "checkedStatementCount": 1, "durationMs": 0,
                "diagnostics": [diagnostic(UNKNOWN, "warning", "passed_with_warnings", UNKNOWN_FILE_SUMMARY, path)
                                for path in unknown]}
    result = json.loads((base_fixture(identifier) / expected_name(identifier)).read_text())
    if identifier in MULTI_CASES:
        # 基の`web`の診断は、除いた3つの原因（未知のファイル2件、BOM、`profiles`）の4件だけである。ほかのワークスペースは`passed`。
        member = next(entry for entry in result["workspaces"] if entry["path"] == MULTI_MEMBER)
        causes = sorted((d["code"], d["source"]["path"]) for d in member["diagnostics"])
        if causes != [("SPEC-CONFIG-UNKNOWN-001", CONFIG_PATH), ("SPEC-INPUT-BOM-001", CONFIG_PATH),
                      (UNKNOWN, ".spec/aaa.txt"), (UNKNOWN, ".spec/notes.txt")]:
            raise ValueError("基のfixtureのメンバーの診断がレビュー済みの原因と異なります")
        member.update(status="passed", diagnostics=[])
        if any(entry["status"] != "passed" or entry["diagnostics"] for entry in result["workspaces"]) or result["diagnostics"]:
            raise ValueError("基のfixtureにほかの診断があります")
        result["status"] = "passed"
    return result


# --- 参照計算 -------------------------------------------------------------------------------

def _git_list(repository, *args):
    return [name for name in git(repository, *args).decode().split("\0") if name]


def _plain_file(repository, relative):
    """シンボリックリンクを経由しない通常のファイルか（途中のどのセグメントもシンボリックリンクでない）。"""
    path = repository
    for part in relative.split("/"):
        path = path / part
        if path.is_symlink():
            return False
    return path.is_file()


def nested_roots(repository, workspace):
    """作業ワークスペースの下位で、`HEAD`またはインデックスと作業ツリーに通常のファイルの`.spec/bitz.yaml`を持つディレクトリ（リポジトリ相対）。

    未追跡または無視された`.spec/bitz.yaml`だけを持つディレクトリは、仕様が一意に決めないので入力に置かない（置けば拒否する）。
    """
    prefix = "" if workspace == "." else workspace + "/"
    own = prefix + CONFIG_PATH
    roots = set()
    for line in git(repository, "ls-tree", "-r", "-z", "HEAD").decode().split("\0"):
        if not line:
            continue
        meta, name = line.split("\t", 1)
        if name.endswith("/" + CONFIG_PATH) and name.startswith(prefix) and name != own and meta.split()[0] != "120000":
            roots.add(name[: -len("/" + CONFIG_PATH)])
    indexed = set(_git_list(repository, "ls-files", "-z"))
    for current, directories, files in os.walk(repository, followlinks=False):
        directories[:] = [d for d in directories if d != ".git"]
        if Path(current).name == ".spec" and "bitz.yaml" in files:
            name = (Path(current) / "bitz.yaml").relative_to(repository).as_posix()
            if not name.startswith(prefix) or name == own or not _plain_file(repository, name):
                continue
            if name not in indexed:
                raise ValueError("未追跡または無視された.spec/bitz.yamlを入力に置いています")
            roots.add(name[: -len("/" + CONFIG_PATH)])
    return roots


def change_set(repository):
    """§5の変更集合: 基準版からインデックスと作業ツリーへの変更、未追跡かつ無視されていないパス（リネームを検出しない）。"""
    changed = set(_git_list(repository, "diff", "--name-only", "--no-renames", "-z", "HEAD"))
    changed |= set(_git_list(repository, "ls-files", "--others", "--exclude-standard", "-z"))
    return changed


def allowed(path, changes):
    return any(path == entry or (entry.endswith("/") and path.startswith(entry)) for entry in changes)


def reference_violations(repository, workspace, changes):
    """境界の外の変更（ワークスペース相対、辞書順）。TASK自身、ワークスペースの外、入れ子のワークスペースの配下を除く（§7）。"""
    prefix = "" if workspace == "." else workspace + "/"
    roots = nested_roots(repository, workspace)
    violations = []
    for path in sorted(change_set(repository)):
        if not path.startswith(prefix):
            continue
        if any(path == root or path.startswith(root + "/") for root in roots):
            continue
        relative = path[len(prefix):]
        if relative == TASK_PATH or allowed(relative, changes):
            continue
        violations.append(relative)
    return violations


def task_changes(content):
    line = next(line for line in content.decode().splitlines() if line.startswith("changes: ["))
    return [entry.strip() for entry in line[len("changes: ["):-1].split(",")]


def unknown_entries(repository, workspace="."):
    """`.spec/`の直下の未知のエントリ（ワークスペース相対、辞書順）。ワークスペース・設定仕様 §3。"""
    directory = repository / workspace / ".spec"
    return sorted(f".spec/{entry.name}" for entry in directory.iterdir() if entry.name not in KNOWN_ENTRIES)


# --- 生成と監査 ---------------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def prepared_states(fixture, manifest, inspect=None):
    states = []
    with tempfile.TemporaryDirectory(prefix="bitz-nested-workspace-") as temporary:
        for run in range(2):
            sandbox = Path(temporary) / str(run)
            sandbox.mkdir()
            repository = setup(fixture, manifest, sandbox / "repo")
            if inspect is not None:
                inspect(repository)
            external = {name: sandbox / name for name in ("home", "cache", "temporary")}
            for path in external.values():
                path.mkdir()
            states.append(observe(repository, external))
    if states[0] != states[1]:
        raise ValueError("隔離した2回の準備手順が一致しません")
    return states[0]


def inspector(identifier):
    """準備した後のリポジトリで、レビュー済みのリテラルの期待値を参照計算と比べる。"""
    def inspect(repository):
        if identifier in TASK_CASES:
            case_ = TASK_CASES[identifier]
            workspace = case_.get("workspace", ".")
            prefix = "" if workspace == "." else workspace + "/"
            changes = task_changes((repository / (prefix + TASK_PATH)).read_bytes())
            if reference_violations(repository, workspace, changes) != case_["violations"]:
                raise ValueError("境界の外の変更が参照計算と異なります")
            if not change_set(repository):
                raise ValueError("作業ツリーに変更がありません")
            if identifier == "SINGLE-184-02" and nested_roots(repository, workspace):
                raise ValueError("対照に入れ子のワークスペースがあります")
        elif identifier in RESERVED_CASES and RESERVED_CASES[identifier]["kind"] == "check":
            if unknown_entries(repository) != RESERVED_CASES[identifier]["unknown"]:
                raise ValueError("未知のエントリが参照計算と異なります")
            if change_set(repository):
                raise ValueError("全体の検査の入力はコミット済みのクリーンなリポジトリです")
        elif identifier in MULTI_CASES:
            if unknown_entries(repository, MULTI_MEMBER) or unknown_entries(repository):
                raise ValueError("複合ワークスペースの入力に未知のエントリがあります")
        else:
            if unknown_entries(repository):
                raise ValueError("基のfixtureの入力に未知のエントリがあります")
    return inspect


def generate(root=HERE, identifiers=None):
    """レビュー済みの入力と期待値からfixtureを書き出す。副作用の期待値は隔離した準備手順の観測で作る（Coreは実行しない）。"""
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = fixture_dir(root, identifier)
        fixture.mkdir(parents=True, exist_ok=False)
        tree, executable, changes = reviewed_inputs(identifier)
        write_tree(fixture / "repo", tree, executable)
        if changes:
            write_tree(fixture / "changes", changes)
        manifest = reviewed_manifest(identifier)
        (fixture / "manifest.json").write_text(_dump(manifest))
        (fixture / "expected").mkdir()
        (fixture / expected_name(identifier)).write_text(_dump(reviewed_result(identifier)))
        state = prepared_states(fixture, manifest, inspector(identifier))
        (fixture / "side-effects.json").write_text(
            _dump({"schemaVersion": "1.0", "policy": "read-only", "before": state, "after": state}))


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ("manifest", "result", "side-effects")}
    schema = json.loads(schema_path(root, "frontmatter").read_text())
    task_schema = Draft202012Validator({"$ref": "#/$defs/taskFrontmatter", "$defs": schema["$defs"]})
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = fixture_dir(root, identifier)
        try:
            manifest = json.loads((fixture / "manifest.json").read_text())
            result = json.loads((fixture / expected_name(identifier)).read_text())
            effects = json.loads((fixture / "side-effects.json").read_text())
            for name, value in (("manifest", manifest), ("result", result), ("side-effects", effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier):
                raise ValueError("マニフェストがレビュー済みの起動と異なります")
            if result != reviewed_result(identifier):
                raise ValueError("期待結果がレビュー済みの期待値と異なります")
            if {path.name for path in (fixture / "expected").iterdir()} != {Path(expected_name(identifier)).name}:
                raise ValueError("期待値のファイルがレビュー済みの1件と異なります")
            tree, executable, changes = reviewed_inputs(identifier)
            if read_tree(fixture / "repo") != (tree, executable):
                raise ValueError("`repo`の入力がレビュー済みの入力と異なります")
            if read_tree(fixture / "changes") != (changes, set()):
                raise ValueError("`changes`の入力がレビュー済みの入力と異なります")
            if {path.name for path in fixture.iterdir()} - {"repo", "changes", "expected", "manifest.json", "side-effects.json"}:
                raise ValueError("fixtureにレビューしていないファイルがあります")
            if identifier in TASK_CASES:
                for path, content in tree.items():
                    if path.endswith(TASK_PATH):
                        # YAMLと値の固定した組だけをレビューする。汎用のYAMLの構文解析器ではない。
                        task_schema.validate({"id": "TASK-001", "title": "変更境界の検査", "status": "open",
                                              "changes": task_changes(content)})
            if effects["policy"] != "read-only" or effects["before"] != effects["after"]:
                raise ValueError("読取り専用の期待値が書込みを許しています")
            state = prepared_states(fixture, manifest, inspector(identifier))
            if compare_state(effects["before"], state):
                raise ValueError("隔離した準備手順が固定したスナップショットと異なります")
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, StopIteration, ValidationError,
                subprocess.SubprocessError) as error:
            errors.append(f"{identifier}: {str(error).split(chr(10))[0]}")
    return {"prepared": prepared, "setups_per_fixture": 2, "core_execution": "Not run",
            "status": "Passed" if not errors else "Failed", "errors": errors}
