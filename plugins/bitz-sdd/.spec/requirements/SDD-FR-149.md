---
id: SDD-FR-149
version: 1.0
status: verified
domain: sync
priority: high
origin: SI-SDD-011
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-149 Discovery成果物のdocs同期マッピング網羅

- **説明**: sdd-discovery が定めるステップの成果物すべてを docs ナラティブ層へ展開できなければ、
  正常終了した pull のあとでも Discovery の結論の一部が docs に現れず、利用者が欠落に気づけない。
  そのため `sdd_sync.py` の同期マッピングは vision / metrics / constraints / scope / personas /
  positioning の6成果物を網羅する。制約は `scope.md` に同居させず
  `.spec/discovery/constraints.md` として独立させ、同期の対応を常に 1:1 に保つ
  （1つの `.spec` 文書を複数の docs 文書へ分割すると push の逆反映先が決まらないため）。
  判定エビデンスである `assumptions.md` は docs へ同期しない。本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - WHEN `sdd_sync.py pull` が実行され `.spec/discovery/metrics.md` が同期対象となるとき THEN システムは `docs/00_はじめに/成功指標.md` へ展開する SHALL
  - WHEN `sdd_sync.py pull` が実行され `.spec/discovery/constraints.md` が同期対象となるとき THEN システムは `docs/00_はじめに/制約.md` へ展開する SHALL
  - WHEN `sdd_sync.py pull` が実行され `.spec/discovery/personas.md` が同期対象となるとき THEN システムは `docs/00_はじめに/ペルソナ・ジャーニー.md` へ展開する SHALL
  - WHEN `sdd_sync.py pull` が実行され `.spec/discovery/positioning.md` が同期対象となるとき THEN システムは `docs/00_はじめに/ポジショニング.md` へ展開する SHALL
  - WHEN `sdd_sync.py pull` が実行されるとき THEN システムは `constraints.md` と `scope.md` をそれぞれ `制約.md` と `対象外.md` へ独立に展開し、一方の同期が他方の同期先を変更しないこと SHALL
  - WHEN `sdd_sync.py push` が実行され Discovery の docs 文書が同期元より新しいとき THEN システムは対応する単一の `.spec/discovery/` 文書へ本文を逆反映する SHALL
  - IF `pull` の対象となる `.spec/discovery/` 成果物が存在しない THEN システムは当該マッピングを SKIP と報告し、失敗として数えず他のマッピングの処理を継続する SHALL
  - IF `push` の対象となる docs 文書が存在しない THEN システムは当該マッピングを SKIP と報告し、失敗として数えず他のマッピングの処理を継続する SHALL
  - WHEN `sdd_sync.py diff` が実行されたとき THEN システムは Discovery 6成果物すべての同期状態を出力し、`.spec/` と `docs/` のいずれも変更しない SHALL
  - WHEN 日本語6章テンプレート上で Discovery 全成果物を `pull` した直後に `docs_inspect.py --strict` を実行したとき THEN システムは ERROR / WARN とも0件で終了する SHALL
- **検証手段**: `tests/test_sdd_sync.py` の SDD-FR-149 unit-test（6成果物の pull / push を
  パラメタライズ検証、constraints と scope の独立展開、pull・push それぞれの欠損時 SKIP、
  diff の網羅と読み取り専用性、pull 後の `docs_inspect.py --strict` PASS）。
- **Revision History**:
  - 1.0 (2026-07-29) 初版（draft 起票）。SI-SDD-011 から導出。
