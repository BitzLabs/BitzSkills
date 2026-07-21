---
id: SDD-FR-136
version: 1.0
status: verified
domain: workflow
priority: high
origin: SI-SDD-020（bitz-sdd .spec/spec-issues/。2026-07-21 SI-CORE-018 の対訳表作成時に発見）
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-136 spec_status のフェーズ語彙の正規化と設計フェーズの追加

- **説明**: sdd-core の正規フェーズ定義（`sdd-core/SKILL.md` のフェーズ・ルーティング表と
  `references/gates.md`）と `spec_status.py` の `determine_phase()` が返すフェーズ語彙が
  食い違っている。①設計フェーズ（正規モデルの `Discuss`）が実装に存在せず、`sdd-design` /
  `sdd-data` / `sdd-ops` / `sdd-review` の4スキルの居場所が機械集計に無い ②`discovery` が
  正規語彙に無い ③`done` が正規語彙に無い、の3点。結果として、ディスカバリー完了後に設計を
  進めている最中のワークスペースは `discovery` または `plan` と誤判定され、Design Gate の
  手前・奥のどちらにいるかを機械集計が報告できない。

  Design Gate（2026-07-21 人間裁定）で **`phase_code` の後方互換を優先する方針**を採り、
  正規語彙を実装側（成果物ベース）に寄せる。すなわち `discovery` を正規語彙へ昇格させ、
  `design` を新規追加し、`done` を維持したうえで、SKILL.md / gates.md の文言を実装に整合させる。
  既存 `phase_code` 値（`map` / `discovery` / `plan` / `execute` / `verify` / `done`）は
  削除・改名しないため、この変更は純粋に加算的であり既存の消費者を壊さない。

- **受入基準 (EARS)**:
  - WHEN `determine_phase()` がフェーズを判定するとき THEN 返す `phase_code` は `map` / `discovery` / `design` / `plan` / `execute` / `verify` / `done` の7語のいずれかである SHALL
  - WHERE 要件とタスクがいずれも0件の場合 THE `determine_phase()` は `.spec/design/` に Markdown 成果物があれば `design` を、無く `.spec/discovery/` に Markdown 成果物があれば `discovery` を、どちらも無ければ `map` を返す SHALL（優先順位は design > discovery > map）
  - WHERE 要件が1件以上存在する場合 THE `determine_phase()` は `.spec/design/` の成果物の有無にかかわらず `plan` 以降（`plan` / `execute` / `verify` / `done`）の判定を適用する SHALL（要件の起票をもって Plan フェーズ入りとみなし、既存判定の挙動を変更しない）
  - WHEN `phase_code` が `design` と判定されたとき THEN `next_actions()` は Design Gate 通過の準備（`sdd-review` の実施と統合判定の取得）を次アクションとして提示する SHALL
  - WHEN `phase_code` が `done` と判定されたとき THEN その表示ラベルは Promotion Gate 待ちであることを示す SHALL
  - THE `sdd-core/SKILL.md` のフェーズ・ルーティング表と `references/gates.md` のゲート説明は `determine_phase()` が返す7語と同一の語彙を用いる SHALL（正規語彙の定義箇所を1つに閉じる）
  - IF 既存の `phase_code` 値（`map` / `discovery` / `plan` / `execute` / `verify` / `done`）を削除または改名する変更が加えられたとき THEN 本要件に違反する SHALL（`phase_code` は JSON 出力の公開契約であり、本要件の変更は加算のみとする）

- **検証手段**: `tests/test_spec_status.py` に回帰テストを先行追加し `.venv/bin/pytest` で検証する。
  fixture は ①設計成果物のみ（→ `design`）②discovery 成果物のみ（→ `discovery`）
  ③設計と discovery の両方（→ `design`）④設計成果物 + draft 要件（→ `plan`。既存挙動の維持）
  ⑤どちらも無し（→ `map`）の5系統。既存の `phase_code` アサーション（`map` / `plan` /
  `execute` / `verify` / `done` / `discovery`）が改変なしで PASS し続けることを後方互換の
  証跡とする。加えて `phase_code` の値集合が7語であることを表明するテストを1件置く。
  文書側（SKILL.md / gates.md の語彙一致）は `spec inspect --workspace . plugins/*` PASS と
  目視確認で担保する。

- **Revision History**:
  - 1.0 (2026-07-21) 初版（draft 起票）
