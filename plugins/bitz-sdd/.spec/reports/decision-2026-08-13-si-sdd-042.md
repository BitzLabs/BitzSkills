# 裁定記録 — SI-SDD-042（レビュー指摘の受領検証）

- **日付**: 2026-08-13
- **裁定者**: hide
- **対象**: `SI-SDD-042`
- **裁定**: 推奨案で条件付き accept
- **裁定経路**: 対話確認（`open → accepted`）

## 裁定内容

1. gate precondition に `gp_kind`（`behavioral` / `artifact` / `process`）を加算する。
   型はレビュアーが宣言し、機械推定しない。
2. `behavioral` GP に限って EARS を必須とし、欠落は FAIL とする。`artifact` / `process` に
   空疎な EARS を要求しない。
3. blocking GP への応答は `accepted` / `rejected` / `deferred` を明示する。
   未応答または意味を失う改変は FAIL とする。
4. `accepted` は GP 原文または正規化表現と対応箇所を保持する。`rejected` は理由と再レビュー、
   `deferred` は追跡先・期限・ゲートを必須とする。
5. 既存レビューは遡及必須化せず段階移行し、schema は加算的に変更する。
6. `sdd-test` 接続と GP から要件への昇格経路は V4 の後続設計へ送る。
7. 本機構は独立レビューの代替ではなく、指摘の取り違えを防ぐ検査として位置づける。

## 波及と次の作業

- `sdd-review` の schema・観点定義・雛形を改訂する。
- `sdd-core` の `spec_inspect.py` に受領検証を追加する。
- `SI-SDD-041` の scaffold 設計と整合させる。
- bitz-sdd V4 ROADMAP にテーマ14として反映する。
- bitz-flow の `SI-FLW-052` が担当する汎用検査と責務を重複させず接続する。
