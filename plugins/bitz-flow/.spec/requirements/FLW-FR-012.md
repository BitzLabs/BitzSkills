---
id: FLW-FR-012
version: 1.4
status: implementing
domain: governance
priority: high
origin: .spec/reports/decision-2026-07-29-bitz-flow-v2-design-gate.md
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-FR-012 v1からv2への段階移行

- **説明**: v1を稼働契約として維持したままv2をM0〜M5で検証し、Promotion Gate後にだけ正を切り替える。
- **受入基準 (EARS)**:
  - WHEN v2 Promotion Gateが未完了である THEN bitz-flowはFLW-FR-001/002とFLW-DSN-001をcurrent契約として扱うこと SHALL
  - WHILE v2後継候補がdraftまたはapprovedである THE SYSTEM SHALL 後継関係を設計本文だけに保持し、候補側`supersedes`と旧要件側`superseded_by`を空欄に保つ
  - WHEN v2 prereleaseを検証する THEN bitz-flowはM0からM5の各出口条件と即時停止条件をmilestone順に適用すること SHALL
  - WHEN M1からM5の各milestoneを開始する THEN bitz-flowはFLW-DSN-014で定めた初期budget、直前までの実績PR数、実績作業session数、レビュー修正回数、出口未達理由、最大予算の人間確認reference、出口、縮退出荷境界をrun manifestへ記録すること SHALL
  - WHEN PR数または作業session数のいずれかが出口未達のまま上限に達する THEN bitz-flowは後続作業を`BLOCKED`にして継続、scope縮小、No-Goの人間裁定を要求すること SHALL
  - WHEN 人間が縮退出荷を裁定する THEN bitz-flowは当該境界自身までの独立canaryがgreenである場合だけ直前の安全な境界を公開し、未完了operationを`UNSUPPORTED`にして生コマンドfallbackを返さないこと SHALL
  - WHEN migration診断を実行する THEN bitz-flowは旧skill名、旧script名、bitz-sdd委譲先、plugin version、result schemaの参照を列挙すること SHALL
  - WHEN v2 canaryが停止条件に達する THEN bitz-flowは後続promotionを停止して直前v1のpin手順を返すこと SHALL
  - WHEN rollbackを実行する THEN bitz-flowはv2が作成したIssue、PR、release、worktreeを自動削除しないこと SHALL
  - WHEN v2 Promotion Gateを提出する THEN bitz-flowは3platformのv1からv2からv1への往復canaryと旧参照ゼロの証跡を要求すること SHALL
  - WHEN v2 Promotion Gateが承認される THEN bitz-flowは旧要件のdeprecated裁定と旧入口撤去を別段階で実行すること SHALL
  - WHEN 人間が旧要件をdeprecatedへ遷移させる THEN bitz-flowは同じ変更セットで完全性を確認した候補側`supersedes`と旧要件側`superseded_by`を記録すること SHALL
- **検証手段**: version/schema誤起動、旧参照検出、milestone停止、v1 pin、往復canary、外部成果物保全をunit testとmigration fixtureで検証する。
- **Revision History**:
  - 1.4 (2026-07-29) M3/M4の独立canaryと縮退出荷ごとのgreen条件を追加
  - 1.3 (2026-07-29) milestone budgetを初期値とし、実績と人間確認referenceによる再校正を追加
  - 1.2 (2026-07-29) M1〜M5のPR/session予算、上限到達時の再裁定、縮退出荷境界を追加
  - 1.1 (2026-07-29) 後継候補とsupersedes/superseded_byの発効時点を分離
  - 1.0 (2026-07-29) Design Gate承認済みFLW-DSN-011からdraft起票
