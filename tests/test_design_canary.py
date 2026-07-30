"""V4 設計 Ready canary（bitz-sdd ROADMAP 順序10 / R0）。

V4 のターゲット設計は `.spec/design/` へ多数の成果物を追加し、Root Workspace と
Component Workspace をまたいで検査する。その工程で使う
**design scaffold → recursive inspect → status** の連鎖が壊れていないことを、
V4 設計の着手前・着手中を通じて継続的に保証するのが本 canary の役割である。

単体の挙動は test_spec_scaffold.py / test_spec_inspect.py / test_spec_status.py が
個別に検査している。本ファイルはそれらを**通しの連鎖として**、かつ
**複数ワークスペース構成で**固定する点が異なる。連鎖のどこかが退行すると、
V4 設計中に採番衝突・走査漏れ・誤判定として現れるため、canary として分離する。

対象契約: SDD-FR-162（設計成果物の再帰走査・ID 一意性・frontmatter 基準の採番）、
SDD-FR-146（複数ワークスペースのクロスリファレンス解決）、
SDD-FR-136 / SDD-FR-163（phase_code の公開契約）。
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = (
    Path(__file__).resolve().parent.parent
    / "plugins" / "bitz-sdd" / "skills" / "sdd-core" / "scripts"
)
SCAFFOLD = SCRIPTS / "spec_scaffold.py"
INSPECT = SCRIPTS / "spec_inspect.py"
STATUS = SCRIPTS / "spec_status.py"

# fixture 用の ID プレフィックスは連結で組み立てる。リテラルで書くと、
# このリポジトリ自身の spec_inspect 走査が本ファイルを幽霊参照として誤検知する
# （test_spec_inspect.py と同じ理由）。
ROOT_DSN = "RTC-" + "DSN"
COMP_A_DSN = "CAC-" + "DSN"
COMP_B_DSN = "CBC-" + "DSN"
COMP_A_FR = "CAC-" + "FR"


def make_workspace(path: Path) -> Path:
    """`.spec/` を持つ最小ワークスペースを作る。"""
    for sub in ("requirements", "design", "tasks", "reviews"):
        (path / ".spec" / sub).mkdir(parents=True, exist_ok=True)
    (path / ".spec" / "PROJECT.md").write_text(
        f"# {path.name}\n\nCanary 用の最小ワークスペース。\n", encoding="utf-8"
    )
    return path


def make_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Root Workspace 1 つと Component Workspace 2 つのモノレポ構成を作る。"""
    root = make_workspace(tmp_path / "root")
    comp_a = make_workspace(tmp_path / "root" / "plugins" / "comp-a")
    comp_b = make_workspace(tmp_path / "root" / "plugins" / "comp-b")
    return root, comp_a, comp_b


def scaffold(workspace: Path, kind: str, prefix: str, *extra: str):
    return subprocess.run(
        [sys.executable, str(SCAFFOLD), str(workspace), kind,
         "--prefix", prefix, "--owner", "canary", *extra],
        capture_output=True, text=True,
    )


def inspect(*roots: Path):
    return subprocess.run(
        [sys.executable, str(INSPECT), "--workspace", *[str(r) for r in roots]],
        capture_output=True, text=True,
    )


def status_json(*roots: Path) -> dict:
    res = subprocess.run(
        [sys.executable, str(STATUS), "--workspace", *[str(r) for r in roots], "--json"],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def report_of(workspace: Path) -> str:
    return (workspace / ".spec" / "inspection-report.md").read_text(encoding="utf-8")


def write_design(path: Path, artifact_id: str, title: str) -> None:
    """ID をファイル名に持たない設計成果物を配置する（stories/ の慣行を模す）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nid: {artifact_id}\ntitle: \"{title}\"\nstatus: active\n"
        f"version: 1.0\nupdated: 2026-07-30\nowner: canary\n---\n\n# {title}\n",
        encoding="utf-8",
    )


def test_design_scaffold_works_in_root_and_component_workspaces(tmp_path: Path):
    """Root / Component のどのワークスペースでも設計成果物を採番生成できる。"""
    root, comp_a, comp_b = make_tree(tmp_path)

    for workspace, prefix in ((root, ROOT_DSN), (comp_a, COMP_A_DSN), (comp_b, COMP_B_DSN)):
        res = scaffold(workspace, "design", prefix, "--title", "初版設計")
        assert res.returncode == 0, res.stderr
        assert (workspace / ".spec" / "design" / f"{prefix}-001.md").exists()


def test_numbering_accounts_for_design_subdirectories(tmp_path: Path):
    """`design/` サブディレクトリの成果物を採番の根拠に含める（SDD-FR-162）。

    ここが退行すると、V4 設計中に既存 ID が再度払い出される。
    """
    _, comp_a, _ = make_tree(tmp_path)
    scaffold(comp_a, "design", COMP_A_DSN, "--title", "初版設計")
    write_design(
        comp_a / ".spec" / "design" / "stories" / "story-p1-happy.md",
        f"{COMP_A_DSN}-002", "ハッピーパス",
    )

    res = scaffold(comp_a, "design", COMP_A_DSN, "--title", "二番目の設計")

    assert res.returncode == 0, res.stderr
    assert (comp_a / ".spec" / "design" / f"{COMP_A_DSN}-003.md").exists(), \
        "サブディレクトリの成果物が採番から見えていない"


def test_recursive_inspect_registers_subdirectory_design_artifacts(tmp_path: Path):
    """サブディレクトリの設計成果物がレジストリへ登録される（SDD-FR-162）。"""
    root, comp_a, comp_b = make_tree(tmp_path)
    scaffold(comp_a, "design", COMP_A_DSN, "--title", "初版設計")
    write_design(
        comp_a / ".spec" / "design" / "stories" / "story-p1-happy.md",
        f"{COMP_A_DSN}-002", "ハッピーパス",
    )

    res = inspect(root, comp_a, comp_b)

    assert res.returncode == 0, res.stdout
    assert f"{COMP_A_DSN}-002" in report_of(comp_a)


def test_duplicate_design_id_across_subdirectories_fails_with_both_paths(tmp_path: Path):
    """同一 ID が別ディレクトリに現れたら FAIL し、両方のパスを示す（SDD-FR-162）。"""
    root, comp_a, comp_b = make_tree(tmp_path)
    scaffold(comp_a, "design", COMP_A_DSN, "--title", "初版設計")
    write_design(
        comp_a / ".spec" / "design" / "stories" / "dup.md",
        f"{COMP_A_DSN}-001", "重複した ID",
    )

    res = inspect(root, comp_a, comp_b)

    assert res.returncode == 1, res.stdout
    report = report_of(comp_a)
    assert "FAIL" in report
    assert f".spec/design/{COMP_A_DSN}-001.md" in report
    assert ".spec/design/stories/dup.md" in report


def test_multi_workspace_inspect_passes_for_every_workspace(tmp_path: Path):
    """Root / Component を一括検査しても、各ワークスペースが独立に PASS する。"""
    root, comp_a, comp_b = make_tree(tmp_path)
    scaffold(root, "design", ROOT_DSN, "--title", "共通設計")
    scaffold(comp_a, "design", COMP_A_DSN, "--title", "A の設計")
    scaffold(comp_b, "design", COMP_B_DSN, "--title", "B の設計")
    write_design(
        comp_a / ".spec" / "design" / "stories" / "story-p1-happy.md",
        f"{COMP_A_DSN}-002", "ハッピーパス",
    )

    res = inspect(root, comp_a, comp_b)

    assert res.returncode == 0, res.stdout
    for workspace in (root, comp_a, comp_b):
        assert "PASS" in report_of(workspace)


def test_component_design_id_is_not_a_ghost_in_sibling_workspace(tmp_path: Path):
    """Component の設計 ID が兄弟ワークスペースの幽霊参照として現れない。"""
    root, comp_a, comp_b = make_tree(tmp_path)
    scaffold(comp_a, "design", COMP_A_DSN, "--title", "A の設計")
    scaffold(comp_b, "design", COMP_B_DSN, "--title", "B の設計")

    res = inspect(root, comp_a, comp_b)

    assert res.returncode == 0, res.stdout
    assert f"{COMP_A_DSN}-001 ←" not in report_of(comp_b)
    assert f"{COMP_B_DSN}-001 ←" not in report_of(comp_a)


def test_status_reports_design_phase_per_workspace(tmp_path: Path):
    """設計成果物だけを持つワークスペースは `design` フェーズと判定される。

    `phase_code` は JSON 出力の公開契約（SDD-FR-136）であるため、
    表示ラベルではなくコードで固定する。
    """
    root, comp_a, comp_b = make_tree(tmp_path)
    scaffold(root, "design", ROOT_DSN, "--title", "共通設計")
    scaffold(comp_a, "design", COMP_A_DSN, "--title", "A の設計")
    scaffold(comp_a, "requirement", COMP_A_FR, "--title", "A の要件",
             "--verification-method", "unit-test", "--status", "draft")

    payload = status_json(root, comp_a, comp_b)

    phases = {Path(w["root"]).name: w["phase_code"] for w in payload["workspaces"]}
    assert phases["root"] == "design", "設計成果物のみのワークスペースは design"
    assert phases["comp-a"] == "plan", "draft 要件があるワークスペースは plan"
    assert phases["comp-b"] == "map", "成果物が無いワークスペースは map"
