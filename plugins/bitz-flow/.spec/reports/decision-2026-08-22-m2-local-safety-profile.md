# 裁定記録 — M2 Local Safety Profileへの縮退

- **日付**: 2026-08-22
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `FLW-REV-024` の是正方針、`FLW-DSN-017`、`FLW-NFR-014`、M2承認・運用境界
- **裁定原文**: 「OKです。提案の内容を反映し、設計を進めましょう」
- **提示済み提案**: archive・署名鍵管理・RBAC・通知/RTOをM2から外し、plan-digest、ローカル
  process間lease、原子的promotion、追記証跡、doctor/audit/reconcileへ縮退する。
- **記録者**: codex（裁定者の明示指示に基づく代行記録・実行者未検証）

## 裁定

1. M2の信頼境界を、同一OSユーザーが管理するローカルrepository、Git common-dir、ローカル
   filesystemへ限定する。同一OSユーザーによる悪意ある改ざん、network filesystem、remote writeは扱わない。
2. M2の承認方式は`plan-digest`、`operation_id`、期限、単回nonce、明示的人間確認に限定する。
   `signed-capability`、reviewer key registry、root of trust、key rotation/revocationはV2初期版から外す。
   `signed-capability`宣言を検出した場合は無言で降格せず`UNSUPPORTED_APPROVAL_MODE`で停止する。
3. process間lease、単調fencing token、mutation直前再照合、追記型journalは維持する。ただしdaemonや
   外部serviceを設けず、Git起動権限を持たない単一ローカルmoduleを更新authorityとする。
4. operation journalとreceiptのarchive、prune、restore、自動削除をM2から外す。M2は原本を削除せず、
   使用量をdoctorで表示するだけとする。
5. mutation前に同一filesystemへdurableな緊急receiptを先行公開し、Git副作用後の容量不足でも
   `INDETERMINATE`証跡を失わない。最悪容量の動的計算やarchive容量管理は要求しない。
6. contract v2 schemaはschema別activationではなく、単一bundle manifestをall-or-nothingで有効化する。
7. promotionはexclusive local lock、owner-only staging、bundle再照合、atomic current pointer更新へ限定する。
   署名baseline、reviewer policy、未知artifactのchild probeは要求しない。
8. 運用面は`doctor`、`audit`、明示確認付き`reconcile`へ限定する。OS owner権限を認可境界とし、
   RBAC、通知adapter、運用RTO/SLOはPromotion Gate後の実需要で再検討する。

## 過去裁定との関係

- `decision-2026-08-15-capability-b2.md` の「registry存在時だけ署名を有効化する」は、M2について本裁定で
  置き換える。将来の署名profileを禁止するものではないが、V2初期版の要件・設計・Gate条件には含めない。
- `decision-2026-08-17-v2-operational-integrity-scope.md` の「強い改ざん耐性を持たない」を具体化し、
  同一OSユーザーの外側にtrust anchorを新設しない。
- M2の公開scopeは従来どおり`worktree.create`、`worktree.resume`、`worktree.audit`であり、破壊系と
  remote writeはM3まで`UNSUPPORTED`を維持する。

## 再判定条件

- `FLW-DSN-017`、`FLW-NFR-014`、`FLW-FR-006`、関連task boundaryが本裁定と一致する。
- `FLW-REV-024`のP1を、実装追加またはscope削除のどちらで解消したか追跡できる。
- 同じ5観点で独立再レビューし、Design Gateを再判定する。
