"""SI-CORE-021 委譲レジストリ整合の機械検証（check_delegation_registry）の回帰テスト。

CLAUDE.md の「委譲レジストリ」節（Claude 側の委譲判断の SSOT）と
.claude/agents/*.md の実体が食い違っていないかを検証する純関数の単体テスト。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from release_check import check_delegation_registry  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _claude_md(body: str) -> str:
    return (
        "# CLAUDE.md\n\n"
        "## オーケストレーター運用\n\n"
        "### 委譲レジストリ（機械検証対象 = SSOT）\n\n"
        f"{body}\n"
        "### 相対選択（司令塔ティア基準）\n\n"
        "後続セクション本文（無関係）。\n"
    )


def _agent_md(model: str) -> str:
    return f"---\nname: dummy\ndescription: dummy\nmodel: {model}\neffort: high\n---\n\n本文\n"


def make_repo(tmp_path: Path, *, ladder: str, table_rows: list[str],
              agents: dict[str, str] | None = None,
              routing_md: str | None = None) -> Path:
    table = "| 役割 | 委譲先 | ティア |\n|---|---|---|\n" + "\n".join(table_rows)
    body = f"**ティアはしご**（上位→下位）: `{ladder}`\n\n{table}\n\n"
    _write(tmp_path / "CLAUDE.md", _claude_md(body))
    for name, model in (agents or {}).items():
        _write(tmp_path / ".claude" / "agents" / f"{name}.md", _agent_md(model))
    if routing_md is not None:
        _write(
            tmp_path / "plugins" / "bitz-sdd" / "skills" / "sdd-implement"
            / "references" / "delegation-routing.md",
            routing_md,
        )
    return tmp_path


DEFAULT_LADDER = "Fable 5 > Opus > Sonnet > Haiku"
DEFAULT_ROWS = [
    "| 深い推論 | `deep-reasoner` サブエージェント | Opus |",
    "| 定型修正 | `fast-worker` サブエージェント | Sonnet |",
    "| コードベースの探索 | 組み込み `Explore` エージェント | — |",
    "| 量産系 | `antigravity-delegate` / `/antigravity:delegate` | 別PF |",
    "| セカンドオピニオン | `/antigravity:review` | 別PF |",
]
DEFAULT_AGENTS = {"deep-reasoner": "opus", "fast-worker": "sonnet"}


def test_registry_consistent_no_violations(tmp_path):
    """整合したレジストリ + agent 実体 → 違反ゼロ"""
    repo = make_repo(tmp_path, ladder=DEFAULT_LADDER, table_rows=DEFAULT_ROWS,
                      agents=DEFAULT_AGENTS)
    assert check_delegation_registry(repo) == []


def test_agent_missing_is_violation(tmp_path):
    """表にある agent が .claude/agents に無い → 違反あり"""
    repo = make_repo(tmp_path, ladder=DEFAULT_LADDER, table_rows=DEFAULT_ROWS,
                      agents={"fast-worker": "sonnet"})  # deep-reasoner を欠落させる
    violations = check_delegation_registry(repo)
    assert violations
    assert any("deep-reasoner" in v for v in violations)


def test_tier_mismatch_is_violation(tmp_path):
    """表は Opus だが agent frontmatter が sonnet → 違反あり"""
    repo = make_repo(tmp_path, ladder=DEFAULT_LADDER, table_rows=DEFAULT_ROWS,
                      agents={"deep-reasoner": "sonnet", "fast-worker": "sonnet"})
    violations = check_delegation_registry(repo)
    assert violations
    assert any("ティア不一致" in v for v in violations)


def test_ladder_duplicate_is_violation(tmp_path):
    """ティアはしごに重複トークンがある → 違反あり"""
    repo = make_repo(tmp_path, ladder="Opus > Opus > Sonnet", table_rows=DEFAULT_ROWS,
                      agents=DEFAULT_AGENTS)
    violations = check_delegation_registry(repo)
    assert violations
    assert any("重複" in v for v in violations)


def test_model_name_hardcoded_in_routing_doc_is_violation(tmp_path):
    """delegation-routing.md にモデル名を直書き → 違反あり"""
    repo = make_repo(tmp_path, ladder=DEFAULT_LADDER, table_rows=DEFAULT_ROWS,
                      agents=DEFAULT_AGENTS,
                      routing_md="# 委譲ルーティング\n\nこのタスクは Sonnet に委譲する。\n")
    violations = check_delegation_registry(repo)
    assert violations
    assert any("直書き" in v for v in violations)


def test_routing_doc_absent_is_skipped(tmp_path):
    """delegation-routing.md が存在しない → 検査スキップで正常系は違反ゼロ"""
    repo = make_repo(tmp_path, ladder=DEFAULT_LADDER, table_rows=DEFAULT_ROWS,
                      agents=DEFAULT_AGENTS, routing_md=None)
    assert not (repo / "plugins" / "bitz-sdd" / "skills" / "sdd-implement"
                / "references" / "delegation-routing.md").exists()
    assert check_delegation_registry(repo) == []


def test_claude_md_absent_is_skipped(tmp_path):
    """CLAUDE.md（委譲レジストリの置き場）が無い環境 → 検査対象外＝違反ゼロ"""
    assert not (tmp_path / "CLAUDE.md").exists()
    assert check_delegation_registry(tmp_path) == []


def test_registry_section_absent_is_skipped(tmp_path):
    """CLAUDE.md はあるが委譲レジストリ節が無い → 検査対象外＝違反ゼロ"""
    _write(tmp_path / "CLAUDE.md", "# CLAUDE.md\n\n## 別の節\n\n本文のみ。\n")
    assert check_delegation_registry(tmp_path) == []
