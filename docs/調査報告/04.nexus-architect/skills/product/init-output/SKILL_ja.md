---
description: |
  プロダクトの方向性（product-direction）の出力ツリー、パイプラインの progress ファイル、および adapt-change で使用されるトレーサビリティグラフを初期化します。
  /product:init-output [project_name]。再初期化するには --reset を使用します。
model: sonnet
user_invocable: true
---

# Output Initialization

## Expected Outcome

`product` パイプラインを実行するために必要なディレクトリ構造と状態（state）ファイルを作成します。

## Execution Steps

1. 以下のディレクトリを作成します（まだ存在しないもののみ）:
   - `reports/00_core/`
   - `reports/01_ux/`
   - `reports/01_ux/domain-stories/`
   - `reports/02_spec/ui-mocks/`
   - `reports/03_domain/`
   - `reports/04_quality/`
   - `reports/05_adaptation/`
   - `reports/report/`
   - `work/`

2. このスキーマで `work/pipeline-progress.json` を初期化します（`@skills/product/common/skill-dependencies.yaml` からのすべてのフェーズを `"pending"` として登録します）:

   ```json
   {
     "schema_version": 1,
     "options": { "output_language": "en", "no_research": false, "profile": "full", "design_system": null, "frontend": null },
     "phases": {
       "define-vision": { "status": "pending", "outputs": [], "updated_at": null }
     },
     "gates": { "validate-assumptions": { "verdict": "pending", "open_assumptions": [] } }
   }
   ```

   `output_language` がすでに設定されているか `--lang` で渡されていない限り、どの `output_language` を使用するかをユーザーに尋ねます（デフォルト `en` / `ja`）。

3. `work/traceability.json` を空のグラフとして初期化します — これが `/product:adapt-change` を機能させるものであり、すべての Skill がこれに追記します:

   ```json
   { "schema_version": 1, "nodes": [] }
   ```

4. `work/context.md` を空のファイルとして作成します（フェーズ間の決定事項を運びます）。

## Options

- `--reset`: 再初期化する前に、既存の `work/pipeline-progress.json` と `work/traceability.json` をバックアップします（`*.bak` にコピーします）。

## Completion Criteria

ディレクトリツリー、`work/pipeline-progress.json`、`work/traceability.json`、および `work/context.md` がすべて存在していること。

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `/product:start` | フェーズを実行する前に、これを自動的に呼び出します |
