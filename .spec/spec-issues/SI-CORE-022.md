---
id: SI-CORE-022
raised_by: 2026-07-14 SI-CORE-021 開発の振り返り（plugin cache パスを毎回ハードコードして回避）
target: 検証ツールの実行パス案内（scripts/ 前提 vs プラグイン消費側 dogfooding の食い違い）
proposed_change_type: fix
status: accepted
---
- **目的**: SDD 検証ツールの実行案内が `python3 scripts/<tool>.py` 前提だが、bitz-sdd を
  **インストール済みプラグインとして消費**する本リポ（ドッグフーディング）ではスクリプト実体が
  プラグインキャッシュ側にあり、案内どおりのパスでは実行できない。毎回の摩擦を解消する。
- **背景（実事例）**: 2026-07-14 の SI-CORE-021 開発で、`python3 scripts/spec_status.py .` が
  「No such file」で失敗。実体は `~/.claude/plugins/cache/bitzskills/bitz-sdd/<ver>/skills/sdd-core/scripts/`
  にあり、`spec_status`/`spec_scaffold`/`spec_update`/`spec_inspect` の**呼び出しのたびに絶対パスを
  ハードコードして回避**した（バージョン番号込みで、更新に脆い）。
- **提案する修正（人間が取捨選択）**:
  1. **リポジトリにラッパーを置く**: `scripts/sdd`（またはツール名ごとの薄いラッパー）を用意し、
     インストール済み bitz-sdd の実スクリプトへ**バージョン非依存に解決**して委譲する。
     案内は `python3 scripts/sdd status .` 等に統一。
  2. **または案内の明確化**: sdd-core/SKILL.md に「プラグイン消費側では実体が
     `${CLAUDE_PLUGIN_ROOT}` 配下」であることと解決手順を明記（`.spec/PROJECT.md` の固定版方針と整合）。
  3. どちらを採るかは設計分岐（人間裁定）。ラッパー案は摩擦を恒久的に消すが実装が要る。
- **対象ファイル**: 新規 `scripts/sdd*`（ラッパー案）、`.spec/PROJECT.md`（版固定方針との整合）、
  `plugins/bitz-sdd/skills/sdd-core/SKILL.md`（案内。※プラグイン側変更を伴う場合は SI-SDD へ派生）。
- **確認観点**:
  - バージョン番号をハードコードせずに実スクリプトへ解決できること
  - 通常の（vendoring した）利用形態を壊さないこと
  - 案内パスと実体が一致すること
- **影響推定・ロールバック**: ラッパー追加または doc 追記。既存挙動不変・単独 revert 可能。
- **依存**: なし。
