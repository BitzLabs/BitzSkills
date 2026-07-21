---
id: SDD-FR-138
version: 1.0
status: draft
domain: workflow
priority: medium
origin: SI-CORE-018（ルート .spec/spec-issues/。ルート→サブ委任）
verification_method: unit-test
derived_from: SDD-FR-137
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-138 spec_update.py の日本語ラベル入力の正規化

- **説明**: SDD-FR-137 で表示が日本語化されると、人間は画面上で「採用」「承認済み」を見ながら
  `--to accepted` と英語で打つことになり、表示と入力が乖離する。`spec_update.py` が日本語
  ラベル入力を機械値へ正規化して受理できるようにする。

  恩恵を受けるのは人間専用遷移（`draft→approved` / `open→accepted` / `verified→promoted` /
  `*→deprecated`）＝必ず人間がタイプするコマンドであり、対象読者と受益者が一致する。
  純粋に加算的な変更で、英語の機械値を渡す既存の呼び出しは正規化辞書にヒットせず素通りする
  ため挙動が変わらない。

- **受入基準 (EARS)**:
  - WHEN `spec_update.py` の `--to` に対訳辞書上の日本語ラベル（例: `採用`）が渡されたとき THEN 対応する機械値（例: `accepted`）へ正規化してから権限マトリクスを照合する SHALL
  - THE 正規化は現在 status と遷移先の同値判定（`cur == new`）より前に適用される SHALL（後段に置くと「遷移不要」であるべきケースが「不正遷移」の誤ったエラーになるため）
  - WHERE 受理する表記は機械値と純粋な日本語ラベルの2種に限る THE 併記形（例: `採用（accepted）`）は受理しない SHALL
  - IF 辞書にも機械値にも一致しない未知語が `--to` に渡されたとき THEN 権限マトリクスの照合で不正遷移として非ゼロ終了する SHALL（曖昧な状態値の混入防止）
  - THE `.spec/STATE.md` に追記される遷移ログは正規化後の機械値で記録される SHALL
  - THE `spec_update.py` は対訳辞書を自前で再定義せず SDD-FR-137 の `spec_labels.py` を唯一の参照元とする SHALL
  - THE 日本語ラベルから機械値への逆引きは種別（要件 / spec-issue / タスク）ごとに一意に定まる SHALL（`実装中` は要件とタスクの双方に現れるが機械値はいずれも `implementing` で衝突しない）

- **検証手段**: `tests/test_spec_update.py` に回帰テストを先行追加し `.venv/bin/pytest` で検証する。
  ①日本語ラベル入力（`--to 承認済み --by-human`）が機械値と同じ遷移結果になること
  ②併記形の入力が拒否されること ③未知語が非ゼロ終了すること ④現在 status と同値の
  日本語ラベルを渡したとき「遷移不要」（不正遷移ではない）と判定されること ⑤`STATE.md` の
  記録が機械値であること ⑥英語機械値を渡す既存テストが改変なしで PASS し続けること。

- **Revision History**:
  - 1.0 (2026-07-21) 初版（draft 起票）
