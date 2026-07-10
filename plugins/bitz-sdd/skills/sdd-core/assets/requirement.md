---
id: FR-000            # 凍結。プレフィックス=FR|NFR|CON。type フィールドは持たない
version: 1.0          # 意味を変えない改訂で bump（判定: 緑を赤にし得ない）
status: draft         # draft|approved|implementing|verified|promoted|deprecated
domain: core          # domains.md の統制語彙のみ
priority: medium      # high|medium|low
origin:               # docs/…@SHA / 会話ログ日付 / reverse-derived
verification_method:  # pbt|example-test|benchmark|sast|dep-audit|load-test|manual-check（必須）
derived_from:         # docs/…@SHA
supersedes:           # 継承時: 旧ID
superseded_by:        # deprecated 時に記入
confidence:           # reverse-derived の場合のみ high|medium|low
---

### FR-000 <タイトル>

- **説明**: <1〜2文>
- **受入基準 (EARS)**:
  - WHEN <単一トリガ> THEN システムは <観測可能な応答> SHALL
- **検証閾値**: <benchmark/load-test の場合は数値を明記>
- **Revision History**:
  - 1.0 (YYYY-MM-DD) 初版
