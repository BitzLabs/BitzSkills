---
id: FLW-DSN-011
title: "v1からv2への規範移行設計"
status: draft
version: 1.0
updated: 2026-07-29
owner: hide
implements: 
origin: FLW-REV-002
---

# FLW-DSN-011 v1からv2への規範移行設計

## 背景

FLW-REV-002は、現行v1のactive/verified契約とv2 draftが相互排他的であるにもかかわらず、
適用時点とsupersede手順が無いことをP0とした。本設計は、旧成果物を先に書き換えず、
「現在の正」と「次版候補」を時間軸で分離する。

## 規範セット

| set | 適用期間 | 正となる成果物 | 状態 |
|---|---|---|---|
| v1-current | v2 Promotion Gate完了まで | FLW-FR-001/002、FLW-DSN-001、現行4skills/scripts | 現在の実行契約 |
| v2-proposed | Design Gate裁定まで | FLW-DSC-000〜006、FLW-DSN-002〜014 | 設計候補。実行契約ではない |
| v2-approved | Design Gate通過後〜実装完了 | active化した設計、後続のv2 draft/approved要件 | 実装対象契約 |
| v2-current | v2 Promotion Gate完了後 | promoted v2要件、active v2設計、v2 skills/scripts | 新しい実行契約 |

v2 draftの`implements`はDesign Gate後に要件を派生するまで空欄とする。Design Gate前の
トレースは`origin`でDiscovery・reviewへ結ぶ。FAIL設計から要件を派生しない。

## 継承するv1不変条件

v2は実装名を継承しないが、次を破棄しない。

1. squash merge済みbranchはterminalであり再利用しない。
2. cleanup前にPR state、head branch、head SHA、default到達性を再照会する。
3. 証跡が不足する削除は安全側停止する。
4. remote branch削除をmergeやlocal cleanupへ自動連結しない。
5. doctorは対象projectへ書き込まない。

これらはDesign Gate後に新しいFR/CONへ派生し、旧FLW-FR-001/002の後継候補とする。
後継IDは正式採番時まで本文へ予約しない。

## spec-issue継承

| issue | v2で参照する設計 | 現時点の扱い |
|---|---|---|
| SI-FLW-001 | FLW-DSN-006/008/011 | accepted・v1実施済み。安全不変条件を継承 |
| SI-FLW-002 | FLW-DSN-012/013 | reference-only。openのため採用裁定は未了 |
| SI-FLW-003 | FLW-DSN-006/012 | reference-only。openのため採用裁定は未了 |
| SI-FLW-004 | FLW-DSN-006/012 | reference-only。openのため採用裁定は未了 |
| SI-FLW-005 | FLW-DSN-008/013 | reference-only。openのため採用裁定は未了 |

Design Gateの承認はopen spec-issueのacceptを兼ねない。SI-FLW-002〜005は別途、
人間がaccept/rejectを裁定し、acceptしたissueだけを後継要件の`origin`または実施記録へ接続する。
reject時は次のいずれかを裁定記録へ明記する。

- 提案固有の設計要素をv2 designから除去する。
- 同じ設計判断をDiscovery/reviewから独立導出したと確認し、`origin`または本文の由来を
  spec-issueではない根拠へ付け替える。

rejectされたissueを根拠のまま残してDesign Gateを通さない。

## 切替シーケンス

1. v2設計が再レビューでCONDITIONAL_PASS以上となる。
2. 人間がDesign Gateを裁定し、設計をactive化する。
3. v2 FR/NFR/CONをdraft起票し、人間がapprovedを裁定する。
4. M0 Contract Kernelをprerelease実装し、3platform evalを通す。
5. M1〜M5を出口条件ごとに実装・検証する。
6. bitz-sddの委譲先、README、migration noteを同じrelease系列で更新する。
7. v2 Promotion Gateで人間が後継要件をpromotedへ進める。
8. 人間専用遷移で旧要件をdeprecatedへ進め、`superseded_by`を記録する。
9. v1 design/skills/scriptsを撤去し、doctorで旧参照ゼロを確認する。

手順8より前はv1が正であり、v2 scriptを安定版入口として案内しない。

## 移行検査

- repository内の`flow-pr`、`flow-worktree`、旧script名の参照を分類する。
- 旧→新action対応表をmigration noteへ生成する。
- bitz-sddの依存versionと委譲先を検査する。
- installed v1へ戻すversion固定手順を記載する。
- v2設定はv1に影響しない新規`.bitz-flow.json`だけを読み、v1用fileを変換しない。
- 起動時resultへplugin version、result schema major、実体path digestを表示し、v1/v2誤起動を検出する。

## canaryとrollback runbook

| 段階 | cohort | 観測 | 即時停止 |
|---|---|---|---|
| M0 | 3platformの保存fixture + 本repo read-only | 10trial/operation | raw fallback、状態変更、秘密値出力が1件 |
| M1/M2 | 本repoの専用worktree、10 WorkUnit | 各operationのDONE/PARTIAL/INDETERMINATE | 誤変更1件、未収束INDETERMINATE1件 |
| M3/M4 | 専用GitHub canary repo、10 Issue/PR flow | marker重複、CI/head判定、復旧時間 | 重複・誤merge・raw fallback各1件 |
| M5 | canary repoのdraft 10件 + prerelease publish 1件 | tag/notes/target一致 | 誤tag・誤publish・notes不一致各1件 |

- canary owner/rollback ownerはbitz-flow maintainer（初期owner: hide）。
- write canaryは各milestone最低7日または10 flowの長い方を観測する。
- SFCR/InvocationはFLW-DSN-014閾値を下回った時点でpromotionを停止する。
- canaryで作成したIssue/PR/release/worktreeは自動削除せず`bitz-flow-canary`として保全・一覧化する。
- rollbackは3platformそれぞれでmarketplace/repository revisionとplugin versionを直前v1へpinし、
  doctorがversion/schema/pathを確認後、read-only smoke testを行う。
- 正確なpin/install commandはM0で各platform公式CLIへfixture化し、migration noteのversion付き
  runbookへ固定する。command fixtureが無いplatformではv2 promotionを行わない。
- v1→v2→v1の往復canaryを1回通し、旧参照ゼロ検査とv1 smoke testがgreenであることを要求する。

## 代替案

- v1を先にdeprecated化: v2未完成期間に正規フローが消えるため不採用。
- pointer skillを残す: dispatcher迂回経路を恒久化するため不採用。
- v1とv2を同じmajorで段階混在: 実行契約を判別できないため不採用。

## 影響とロールバック

v2公開前はv2成果物をrevertしてv1-currentを維持する。v2公開後はmanifest/versionを
直前のv1安定版へ固定し、v2で作成したGit/GitHub成果物は自動削除せず保全する。
