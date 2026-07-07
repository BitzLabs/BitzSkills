# ブラウンフィールド導入とメトリクス

## 既存コードベースへの導入（Stage B）

1. **観測仕様の逆導出**: 既存コード・既存テストから現状の振る舞いを EARS 化し、`origin: reverse-derived` + `confidence: high|medium|low` 付き draft を生成する。confidence は「既存テストの裏付けがあるか」で判定
2. **人間のトリアージ**: 「意図通り（→approved）/ 意図と違うが現状維持（→approved+注記）/ 直すべき（→新featureとして扱う）」に振り分け。**これから触る領域だけ on-demand** で行い、全件網羅を目標にしない
3. **段階目標**: 逆導出はコード変更の前提条件としてのみ要求（触る場所に approved 要件がなければならない）

reverse-derived 要件は「仕様が意図を表す」保証がないため、traceability matrix 上で区別表示する。

## メトリクス（.planning/metrics.md に feature ごと1行、planエージェントが自動記録）

| 指標 | 定義 | 悪化時に疑う場所 |
|------|------|------------------|
| 一発合格率 | リトライなしで verified に達したタスク割合 | 仕様の曖昧さ・タスク分解の粒度 |
| spec-bug 率 | 全失敗中の spec-bug 割合 | 派生プロセス・approved 承認の甘さ |
| 手戻り率 | supersede が発生した要件割合 | docs/ の意図記述の薄さ・要件の切り方 |
| エスカレーション率 | 人間介入が必要だったタスク割合 | リトライ上限・boundary 設計 |

補助監視: verification_method の `manual-check` 比率（20%超で見直し）。

## 改善ループ

3〜5 feature ごと（または月次）に metrics.md をレビューし、効いていない規律を削り、効いている規律を本スキルに固める。**本ワークフロー自体を semver 管理し、変更は docs/ の ADR として記録する** — ワークフロー自体がSDDの適用対象。
