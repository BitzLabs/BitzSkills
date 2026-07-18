---
id: CORE-FR-013
version: 1.0
status: implementing
domain: tooling
priority: medium
origin: SI-CORE-007
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-FR-013 release_check.py によるプラグイン間依存の宣言と検証

- **説明**: 並行開発するプラグイン間の依存関係（例: bitz-ddd → bitz-sdd、将来の
  bitz-sdd → bitz-flow）は現状 description の文言でしか表現されておらず、依存切れ・循環を
  機械検出できない。本要件は、マニフェスト `metadata.dependencies`
  （例: `["bitz-sdd>=1.4"]` — プラグイン名 + 任意の semver 制約）の書式を規定し、
  `scripts/release_check.py` に依存グラフ検証を追加する。依存宣言を持たない既存プラグインは
  従来どおり PASS する（後方互換・非破壊的追加）。
- **受入基準 (EARS)**:
  - WHEN プラグインのマニフェストに `metadata.dependencies` が宣言されている THEN release_check は3マニフェスト（`.claude-plugin/plugin.json` / `plugin.json` / `.codex-plugin/plugin.json`）で同値であることを検証し、不一致なら FAIL とすること SHALL
  - WHEN 宣言された依存先プラグインが `plugins/` 実体（= marketplace 登録対象）に存在しない THEN release_check は FAIL とすること SHALL
  - WHEN 依存宣言が semver 制約（`>=` / `==` 等）を含み、依存先プラグインの現行 version がその制約を満たさない THEN release_check は FAIL とすること SHALL
  - WHEN 依存グラフに循環（例: A → B → A）が存在する THEN release_check は FAIL とすること SHALL
  - WHEN プラグインが `metadata.dependencies` を宣言していない THEN 依存検証はそのプラグインについて何も報告せず、既存チェックの結果のみで PASS / FAIL が決まること SHALL（後方互換）
  - THEN `metadata.dependencies` の書式は plugin-creator の plugin-structure reference に、init / doctor / update 時の依存確認手順は標準ライフサイクル契約（lifecycle-skills.md。CORE-CON-008）に記載されること SHALL
- **検証手段**: `tests/test_release_check.py` に依存検証の回帰テストを**テスト先行**で追加する
  （依存先不在 → FAIL、循環 → FAIL、semver 制約不満足 → FAIL、3マニフェスト不一致 → FAIL、
  依存宣言なしの既存5プラグイン構成 → PASS のまま）。加えて本リポジトリで
  `python3 scripts/release_check.py` を実行し PASS を確認する（example-test）。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票。SI-CORE-007 起票時は2マニフェストだったが、
    SI-CORE-024 で Codex が第3の配布対象になったため3マニフェスト同値検証に更新）
