---
id: SDD-FR-164
version: 1.0
status: verified
domain: sync
priority: high
origin: SI-SDD-032（裁定I。.spec/reports/decision-2026-07-30-order8-design-foundation.md）
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-164 docs 同期の新旧判定をナノ秒精度で行う

- **説明**: `sdd_sync.py` は書き込み側の `atomic_write_document` で
  `os.utime(..., ns=source_mtime_ns)` を用いて `st_mtime_ns` を反映する一方、比較側の
  `get_mtime` は `st_mtime`（float 秒）を返していた。float64 は現在のエポック値では
  約 238ns の分解能しか持たないため、**同一実装内の精度が非対称**であり、同一秒内の変更や
  粗い粒度のファイルシステムでは「新しい方」を判別できず、pull / push が無音で上書きを
  スキップまたは実施しうる。無音のデータ損失は検証で気づけない種類の欠陥である。

  本要件は比較側を `st_mtime_ns`（整数ナノ秒）へ揃える。`SDD-FR-100`（mtime 比較による
  上書き制御）の意図「新しい方を残す」を精度面で満たしに行く変更であり、公開契約の
  受入基準は変えない。裁定I により、mtime 依存自体をやめる内容ハッシュ比較への移行は
  **採らない**（`SDD-FR-100` の破壊的変更となり V4 Design Gate 必須の論点になるため）。

  **workspace mutation lock への参加は本要件の範囲外とする（設計判断）**。lock 機構の実体は
  sdd-core の `spec_transaction.py` にあり、スキル自己完結原則（`CORE-CON-004`）により
  sdd-docs から相対パスで参照できない。共有 Python コードの配置は V4 の未裁定論点
  （ROADMAP「未裁定の設計論点」1: 配布単位）であり、そこで裁定するまで実装しない。
  適用範囲と残余リスクは受入基準および `sdd-docs/SKILL.md` に明記する。本要件は公開契約に該当する。
- **受入基準 (EARS)**:
  - WHEN `sdd_sync.py` が同期元と同期先の新旧を比較する THEN 比較は `st_mtime_ns`
    （整数ナノ秒）で行うこと SHALL
  - WHERE 2つの mtime の差が float 秒へ落とすと消える大きさ（約 238ns 未満）である場合
    THEN pull / push は同期元が新しいことを正しく判別し、無音でスキップしないこと SHALL
  - WHEN `diff` が同期状態を判定する THEN 判定は `st_mtime_ns` で行うこと SHALL
    （表示上の日時整形は秒精度でよい）
  - WHEN pull または push が完了した THEN 同期先の mtime は同期元と**ナノ秒単位で同値**に
    なり、直後の逆方向同期が起きないこと SHALL（既存の mtime 同値化契約の維持）
  - WHERE ファイルが存在しない場合 THEN `get_mtime` は 0 を返し、「未作成」判定が
    従来どおり成立すること SHALL
  - THEN `sdd_sync.py` および `migrate_docs.py` は workspace mutation lock へ参加しない
    ことを設計判断として文書に明記し、変更 CLI との同時実行を避ける運用制約と
    残余リスク（lost update）を利用者へ示すこと SHALL
- **検証手段**: `tests/test_sdd_sync.py` で unit-test する。(1) float 秒では同値になる ns 差で
  pull が同期を実施すること、(2) 同じ条件で push が逆反映すること、(3) 同期直後に mtime が
  ns 単位で同値となり逆方向同期が起きないこと、(4) `diff` が同条件を「pullが必要」と
  判定すること。ns 粒度を保持しないファイルシステムでは前提が成立しないため
  `pytest.skip` で明示的にスキップする（環境依存を黙って PASS にしない）。
  lock 不参加の明記は `sdd-docs/SKILL.md` の目視確認で担保する。
- **Revision History**:
  - 1.0 (2026-07-30) 初版（draft 起票）。SI-SDD-032 と裁定I から導出。
    lock 参加は追加裁定（2026-07-30）により V4 へ送り、本要件では設計判断として明記する。
  - 1.0 (2026-07-30) 代行可視化経路で approved 化
    （裁定記録 `.spec/reports/decision-2026-07-30-order8-design-foundation.md` 裁定I）。
  - 1.0 (2026-07-30) 実装・検証完了により verified 化。証跡
    `.spec/verification/pytest--f0aed06.json`（exit_code 0 / 43 passed）。
