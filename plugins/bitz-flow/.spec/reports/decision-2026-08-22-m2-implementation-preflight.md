# 裁定記録 — M2実装前の契約・変更境界補正

- **日付**: 2026-08-22
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `SI-FLW-080`、`SI-FLW-081`、`SI-FLW-082`
- **裁定原文**: 「OK」
- **提示済み提案**: 新規schemaと既存inventory testの変更境界、承認方式非対応時の
  公開result写像、実装PRごとのrelease metadata境界を、各spec-issueの推薦案どおり補正する。
- **記録者**: codex（裁定者の明示指示に基づく代行記録・実行者未検証）

## 裁定

1. `SI-FLW-080`をacceptedとする。`tests/test_flow_m2_contract_v2.py`を
   `FLW-TSK-106/107`の変更境界へ追加し、legacy schemaの実在とactive bundle membershipを
   分離する。bundleの期待member集合はcode-owned一覧として明示し、欠落・余剰を拒否する。
2. `SI-FLW-081`をacceptedとする。内部reasonは`UNSUPPORTED_APPROVAL_MODE`、公開resultは
   `code: UNSUPPORTED`と`cause: unsupported-approval-mode`の組で表現し、暗黙の
   `plan-digest`降格を禁止する。
3. `SI-FLW-082`をacceptedとする。各実装PRの先頭taskをrelease integration ownerとし、
   plugin/skill version更新に必要なrelease metadataを当該taskの変更境界へ追加する。
   release metadataを共有する実装PRは直列化し、各PRでpatch bumpを1回だけ行う。

## 実装着手条件

- 上記3件を`accepted`へ遷移し、この裁定記録を`decision_ref`として残す。
- `FLW-NFR-014`、`FLW-DSN-017`、`FLW-TSK-106`〜`114`の該当箇所へ裁定を反映する。
- 反映後に仕様一括検査を通し、契約・タスク境界の矛盾が解消されたことを確認する。
