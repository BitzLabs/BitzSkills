---
id: FLW-DSN-011
title: "v1からv2への規範移行設計"
status: active
version: 1.4
updated: 2026-07-29
owner: hide
implements: FLW-FR-011, FLW-FR-012, FLW-CON-001, FLW-CON-006
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
| v2-discovery-evidence | Discovery Gate Go後も保持 | FLW-DSC-000〜006とGate裁定 | 探索根拠。実行契約ではない |
| v2-proposed | Design Gate裁定まで | FLW-DSN-000/002〜014 | 設計候補。実行契約ではない |
| v2-approved | Design Gate通過後〜実装完了 | active化した設計、後続のv2 draft/approved要件 | 実装対象契約 |
| v2-current | v2 Promotion Gate完了後 | promoted v2要件、active v2設計、v2 skills/scripts | 新しい実行契約 |

Discovery GateはDiscoveryからDesignへのフェーズ遷移を許可する人間裁定であり、
FLW-DSC-000〜006を`active`へ遷移させるゲートではない。Discovery成果物は`draft`を維持し、
Goの正は`assumptions.md`と`worksheet.md`の裁定記録とする。したがって、DSCの`draft`は
Gate未裁定や設計未着手を意味しない。

v2 draftの`implements`はDesign Gate後に要件を派生するまで空欄とする。Design Gate前の
トレースは`origin`でDiscovery・reviewへ結ぶ。FAIL設計から要件を派生しない。

## 継承するv1不変条件

v2は実装名を継承しないが、次を破棄しない。

1. squash merge済みbranchはterminalであり再利用しない。
2. cleanup前にPR state、head branch、head SHA、default到達性を再照会する。
3. 証跡が不足する削除は安全側停止する。
4. remote branch削除をmergeやlocal cleanupへ自動連結しない。
5. doctorは対象projectへ書き込まない。

これらは次の複合的な後継候補へ分割して継承する。

| v1要件 | v2後継候補 | 継承する責務 |
|---|---|---|
| FLW-FR-001 | FLW-FR-004 | Git read、診断、fetchの副作用分離 |
| FLW-FR-001 | FLW-FR-006 | worktree-first lifecycleとfinish |
| FLW-FR-001 | FLW-FR-007 | branch audit |
| FLW-FR-001 | FLW-FR-009 | PR preflightと段階的PRライフサイクル |
| FLW-FR-001 | FLW-CON-006 | 破壊操作とcleanupの安全境界 |
| FLW-FR-002 | FLW-FR-011 | read-onlyなv2環境診断 |

この表はDesign Gate後の追跡候補であり、置換関係そのものではない。候補要件がdraftまたは
approvedの間は、候補側の`supersedes`と旧要件側の`superseded_by`を空欄に保つ。
Promotion Gate承認後、人間が旧要件をdeprecatedへ遷移させる同じ変更セットで、完全性を再確認した対応だけを両方向のrelation fieldへ記録する。

## spec-issue継承

| issue | v2で参照する設計 | v2要件 | accepted内容 |
|---|---|---|---|
| SI-FLW-001 | FLW-DSN-006/008/011 | 複合後継候補 | v1実施済みの安全不変条件 |
| SI-FLW-002 | FLW-DSN-005/012/013 | FLW-FR-004 | fetchとinspectの分離、鮮度証跡、工程別診断 |
| SI-FLW-003 | FLW-DSN-006/012 | FLW-FR-007 | 状態変更を行わないbranch audit |
| SI-FLW-004 | FLW-DSN-006/012 | FLW-FR-006 / FLW-CON-006 | branch-only WorkUnitと安全なcleanup |
| SI-FLW-005 | FLW-DSN-008/013 | FLW-FR-009 | prepareからpost-mergeまでの段階的PRライフサイクル |

SI-FLW-002〜005は2026-07-29の人間裁定を代理記録したaccepted issueであり、裁定参照は
`.spec/reports/decision-2026-07-29-bitz-flow-v2-design-gate.md`とする。Design Gate自体が
spec-issueのacceptを暗黙に兼ねたのではなく、同じユーザー指示に含まれた二つの明示裁定を別イベントとして記録している。

## 切替シーケンス

1. v2設計が再レビューでCONDITIONAL_PASS以上となる。
2. 人間がDesign Gateを裁定し、設計をactive化する。
3. v2 FR/NFR/CONをdraft起票し、人間がapprovedを裁定する。
4. M0 Contract Kernelをprerelease実装し、3platform evalを通す。
5. M1〜M5を出口条件ごとに実装・検証する。
6. bitz-sddの委譲先、README、migration noteを同じrelease系列で更新する。
7. v2 Promotion Gateで人間が後継要件をpromotedへ進める。
8. 人間専用遷移で旧要件をdeprecatedへ進め、同じ変更セットで候補側`supersedes`と
   旧要件側`superseded_by`を記録する。
9. v1 design/skills/scriptsを撤去し、doctorで旧参照ゼロを確認する。

手順8より前はv1が正であり、relation fieldは空欄に保ち、v2 scriptを安定版入口として
案内しない。候補の一部がPromotion Gateを満たさない場合は、旧要件をdeprecatedへ進めず、
候補表を更新して再審査する。

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
| M3 | 専用GitHub canary repo、10 Issue/SDD flow | capability、Issue marker、link reconcile、復旧時間 | 重複Issue・marker重複・link誤判定・raw fallback各1件 |
| M4 | 専用GitHub canary repo、10 PR flow | PR marker、CI/head判定、partialからの復旧時間 | 重複PR・誤merge・CI/head誤判定・raw fallback各1件 |
| M5 | canary repoのdraft 10件 + prerelease publish 1件 | tag/notes/target一致 | 誤tag・誤publish・notes不一致各1件 |

- canary owner/rollback ownerはbitz-flow maintainer（初期owner: hide）。
- write canaryは各milestone最低7日または10 flowの長い方を観測する。
- 縮退出荷境界は、その境界自身の独立canaryがgreenの場合だけ公開できる。M3のgreenを
  M4の一部実行で代用せず、M4未完了でもM3の10 Issue/SDD flowだけで判定できるようにする。
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
