---
id: SI-CORE-024
raised_by: 2026-07-15 Codex を第3の配布対象に追加する変更（codex:rescue 起点。approved 要件を直接改版していたため事後起票）
target: 配布対象プラットフォームの2系統（Claude Code / Antigravity）→3系統化（+ OpenAI Codex CLI）と、それに伴う規約・マニフェスト・検証機構の拡張
proposed_change_type: new
status: accepted
---
- **目的**: 本モノレポのプラグインを **OpenAI Codex CLI** からも導入・利用できるようにし、
  配布対象を「Claude Code / Antigravity 2.0」の2系統から「+ Codex CLI」の3系統へ拡張する。
  併せて、2マニフェスト前提だった規約・定型手順・検証機構を3マニフェスト前提へ更新する。
- **背景（実事例）**: 2026-07-15、`codex:rescue`（Codex への委譲）で
  「3 CLI から使用できるプラグインへ変更」タスクを実行し、作業ブランチ
  `feat/codex-plugin-distribution` に全5プラグインの `.codex-plugin/plugin.json` 追加・
  marketplace/README/AGENTS.md 更新・`bump_version.py`/`release_check.py`/テストの3マニフェスト対応を
  Codex が実装した。この過程で **approved 済み要件 CORE-CON-001 / 003 を spec-issue 起票・裁定を経ずに
  直接改版**しており、ドッグフーディング中の SDD 手続き（SI 起票→裁定→改版）を逸脱していた。
  本 ISSUE はその決定を事後に正規化するもの。
- **提案する修正（人間裁定済み）**:
  1. **配布方式**: 各プラグインに Codex CLI 用マニフェスト `.codex-plugin/plugin.json`
     （`skills: "./skills/"`）を追加。既存 `.claude-plugin/marketplace.json` を Codex CLI が
     互換カタログとして認識する（Codex CLI 0.144.4 で実機確認済み）ため、Claude Code と**共有**する
     最小構成とする。導入は `codex plugin marketplace add <repo>` → `codex plugin add <plugin名>@bitzskills`。
  2. **規約の要件化**: CORE-CON-001（マニフェスト version 同値）を **2→3マニフェスト**へ、
     CORE-CON-003（marketplace 整合）を **Claude Code / Codex 共有カタログ**へ改版（いずれも version 1.1）。
  3. **定型手順の3マニフェスト化**: `bump_version.py`（3マニフェスト原子更新）、
     `release_check.py`（3者 version 一致・Codex skills パス検証）、対応テストを拡張。
  4. **版整合**: Codex 配布追加は各プラグインのリリース対象変更。version bump を全5プラグインへ揃える
     （skill-creator は SKILL.md 実変更で既に bump 済み。残4件を bump する）。
  5. **委譲方針との整合**: CLAUDE.md の「Codex は使用しない」を実態（配布対象かつ利用可能な
     プラットフォーム）に合わせて更新。委譲レジストリ上のクロスモデル検証の既定は引き続き
     antigravity（Gemini）とし、Codex はレジストリと**分離管理**（antigravity と同じ扱い）とする。
- **対象ファイル**: 全5プラグインの `.codex-plugin/plugin.json`（新規）・各 README、
  `.claude-plugin/marketplace.json`、`AGENTS.md`、ルート `CLAUDE.md`、
  `.spec/requirements/CORE-CON-001.md` / `CORE-CON-003.md`、
  `scripts/bump_version.py` / `scripts/release_check.py`、
  `tests/{conftest,test_bump_version,test_release_check}.py`、
  `plugins/skill-creator/skills/skill-packager` 関連 / `skill-instrumenter`。
- **確認観点**:
  - `release_check.py` PASS（3者 version 一致・Codex skills パス・marketplace 整合）
  - `pytest` GREEN
  - approved 要件の改版が Revision History に記録されていること
  - version bump が全5プラグインで揃っていること
  - CLAUDE.md の委譲レジストリ（クロス検証＝antigravity 既定）と矛盾しないこと
- **影響推定・ロールバック**: マニフェスト追加＋規約・スクリプト・テストの拡張。既存の
  Claude Code / Antigravity 導入フローは不変（共有カタログを壊さない）。単独 revert 可能。
- **依存**: なし。SI-CORE-022（検証ツール実行パス案内）とは別関心事。

---

## 裁定・確定設計（2026-07-15 チャット裁定）

**採否**: accept。Codex を第3の配布対象として正式サポートする。上記「提案する修正」1〜5 を確定。

**確定事項**:

1. **共有カタログ方式を採用**: Codex 専用カタログ（公式推奨位置 `.agents/plugins/marketplace.json`）は
   現時点では追加せず、`.claude-plugin/marketplace.json` を Claude Code / Codex で共有する。
   将来 Codex CLI が互換認識を廃止した場合に専用カタログ追加を再検討する（残課題として記録）。
2. **委譲レジストリとの分離**: 「配布対象としての Codex」と「委譲/クロス検証エージェントとしての
   モデル選択」は別軸。委譲レジストリ（CLAUDE.md）のクロスモデル検証の既定は antigravity（Gemini）の
   ままとし、Codex は antigravity と同様レジストリの相対階層と直交する扱いとする。
3. **プロセス**: approved 要件（CORE-CON-001/003）の改版を含むため通常フロー。
   本 ISSUE の裁定をもって改版を正規化し、後続コミットで反映する。

**残課題**:
- Codex 公式の新規カタログ推奨位置は `.agents/plugins/marketplace.json`。共有カタログ互換が
  将来廃止された場合は専用カタログ追加が必要（実機では現行 CLI での互換を確認済み）。
- ルート単体 `spec_inspect .` の `ENV-*` 幽霊参照 5 件は本変更と無関係（SI-CORE-023 で別途扱う）。
