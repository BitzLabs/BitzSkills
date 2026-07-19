#!/usr/bin/env python3
"""ENV-FR-013 の manual-check ハーネス（使い捨て・決定的モデル）。

env-update SKILL.md 手順4.3〜4.4 が規定する「git 管理状態の実確認 → rollback 手段の
対提示」を、合成フィクスチャ（gitignore されたレジストリを持つ模擬リポジトリ）上で
そのままモデル化して確認する。本番の実行コードではない。

観点:
  G1: gitignore されたレジストリ（.claude/bitz-env.local.md）に「rollback 手段 = .bak」が
      提示される（SI-ENV-025 の誤提示「git」が再発しない）
  G2: git 管理下のファイル（AGENTS.md）には「rollback 手段 = git」が提示される
  G3: 未追跡（ignore 対象外）ファイルにも「rollback 手段 = .bak」が提示される
  G4: SKILL.md 手順4 に実確認コマンドと対提示・推測禁止が、手順5.1 に手順4.3 との接続が
      明文化されている（ドキュメント検査）
"""

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_MD = REPO_ROOT / "plugins/bitz-env/skills/env-update/SKILL.md"
RUNBOOK = REPO_ROOT / "plugins/bitz-env/skills/env-update/references/migration-runbook.md"


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )


def rollback_means(repo: Path, path: str) -> str:
    """SKILL.md 手順4.3 の実確認をそのまま実装: 追跡判定 → ignore 判定 → 手段決定。

    推測（パスがリポジトリ内かどうか）は一切使わない。
    """
    tracked = git(repo, "ls-files", "--error-unmatch", path).returncode == 0
    if tracked:
        return "git"
    return ".bak"  # 未追跡（ignore 対象含む）は管理外 → .bak 必取得


def check(name: str, cond: bool, detail: str) -> bool:
    print(f"{name}: {'PASS' if cond else 'FAIL'} — {detail}")
    return cond


def main() -> int:
    results = []
    with tempfile.TemporaryDirectory(prefix="env-update-dryrun-") as tmp:
        repo = Path(tmp)
        git(repo, "init", "-q")
        # env-init 既定相当のフィクスチャ: レジストリは gitignore 対象のローカルファイル
        (repo / ".gitignore").write_text(".claude/*.local.md\n", encoding="utf-8")
        (repo / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
        (repo / ".claude").mkdir()
        (repo / ".claude/bitz-env.local.md").write_text(
            "---\nbitz-env-version: \"0.7.0\"\n---\n", encoding="utf-8"
        )
        (repo / ".claude/agents").mkdir()
        (repo / ".claude/agents/advisor.md").write_text("---\n---\n", encoding="utf-8")
        git(repo, "add", ".gitignore", "AGENTS.md")
        git(
            repo, "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "-qm", "fixture",
        )

        ignored = git(repo, "check-ignore", ".claude/bitz-env.local.md").returncode == 0
        results.append(
            check(
                "G1",
                ignored and rollback_means(repo, ".claude/bitz-env.local.md") == ".bak",
                "gitignore されたレジストリの rollback 手段は .bak（誤提示 git の再発なし）",
            )
        )
        results.append(
            check(
                "G2",
                rollback_means(repo, "AGENTS.md") == "git",
                "git 管理下の AGENTS.md の rollback 手段は git",
            )
        )
        results.append(
            check(
                "G3",
                rollback_means(repo, ".claude/agents/advisor.md") == ".bak",
                "未追跡（ignore 対象外）の advisor.md の rollback 手段は .bak",
            )
        )

    skill = SKILL_MD.read_text(encoding="utf-8")
    runbook = RUNBOOK.read_text(encoding="utf-8")
    doc_ok = (
        "git ls-files --error-unmatch" in skill
        and "git check-ignore" in skill
        and "推測や既定値での判定" in skill
        and "手順4.3 で実確認した git 管理状態に従い" in skill
        and "gitignore 対象" in skill
        and "git ls-files --error-unmatch" in runbook
        and "git check-ignore" in runbook
    )
    results.append(
        check(
            "G4",
            doc_ok,
            "SKILL.md 手順4（実確認・対提示・推測禁止・レジストリ注記）と手順5.1 の接続、"
            "runbook の同期が明文化されている",
        )
    )

    ok = all(results)
    print(f"総合: {'PASS' if ok else 'FAIL'}（{sum(results)}/{len(results)}）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
