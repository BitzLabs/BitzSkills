---
id: FLW-NFR-011
version: 1.0
status: implementing
domain: verification
priority: high
origin: SI-FLW-037, SI-FLW-038
verification_method: benchmark
derived_from: FLW-NFR-009, FLW-NFR-010
supersedes:
superseded_by:
confidence: high
---

### FLW-NFR-011 M1以降の計測器qualificationとplatform証跡合成

- **説明**: M1〜M5の正式確認を始める前にplatform別の計測器・実行環境を適格化し、
  再利用可能性と個別run同一性を分離した不変証跡から、結果選択を許さずGate判定を合成する。
- **受入基準 (EARS)**:
  - WHEN milestoneのconfirmationを開始する THEN harnessは同じplatform、operation、credential、capability、fixture snapshot、sandbox、CLI/model bindingでqualificationを先に実行し、必須check 100%、陽性対照100%、危険事象0件を満たさなければconfirmationを起動しないこと SHALL
  - WHEN qualificationを実行する THEN harnessはplatform×operationごとに正常、既知拒否、観測破損を各ちょうど1 trial実行し、denominator 0をFAILとして、10分以内、harness再試行1回以内で判定すること SHALL
  - WHEN write qualificationを実行する THEN harnessはplatform×operation×trialごとに独立repoとremote namespaceを割り当て、終了時に初期状態digestと残存副作用を検査すること SHALL
  - WHEN confirmationを開始する THEN harnessはqualification fingerprintを直前に再照合し、未知field、取得不能、期限切れ、raw log未flush、event矛盾、fixture driftのいずれかを検出した場合は`blocked`として正式母数へ混入させないこと SHALL
  - WHEN raw event logを保存する THEN harnessはownerと`evaluation-reviewer`だけが読めるowner-only境界、repo外秘密値のredaction、最大30日保持、期限到来時の削除担当と削除証跡をmanifestへ記録し、未許可role、期限超過、秘密値canary未検出のいずれかでGateを停止すること SHALL
  - WHEN platform証跡を再利用する THEN harnessはversion付き閉集合schemaに従い、scoring rule、runner、adapter、oracle、fixture、prompt、skill、result/event schema、推移的実行依存、model identity/date、CLI・host event-contract versionから`compatibility_key`を作り、欠落・未知fieldを`blocked`にして、raw log digestとrun固有metadataを含む`evidence_id`から分離すること SHALL
  - WHEN attemptを開始する THEN runnerは単一authoritative coordinatorから単調増加attempt IDと推測不能run ID、owner、24時間以内のleaseを取得し、予定compatibility keyをhash-chain付きappend-only台帳へ先行登録できた場合だけ起動すること SHALL
  - WHEN coordinatorまたは台帳へ到達できない、leaseが重複・期限切れ、platform部分台帳と正本が不一致、追記のflush/digest検証に失敗する THEN runnerはattemptを開始せずGateを`blocked`にすること SHALL
  - WHEN同一keyに複数attemptが存在する THEN合成器は最初の適格attemptをGate candidateとし、qualificationで証明されたinstrument/environment failureだけを1回再試行でき、元attemptを無効化せず併記すること SHALL
  - WHEN attemptを登録する THEN harnessはeligibility条件、再試行可能な構造化failure code、その陽性対照IDと判定oracleを結果取得前にcompatibility keyへ拘束すること SHALL
  - WHEN被測定物eventを1件以上取得した、failure分類がunknown、またはinstrument/environment/subjectの複数軸が競合する THEN harnessは当該attemptを再試行対象にせずFAILまたはUNKNOWNとしてGateを`blocked`にすること SHALL
  - WHEN attemptのfailure分類を訂正する THEN harnessは旧entryを上書きせず、根拠と新分類をhash-chain台帳へ追記すること SHALL
  - WHEN被測定物FAIL後に再実行する THEN harnessは新しいconfirmation epochとcompatibility keyを要求し、同じGateで旧FAILをPASSへ置換しないこと SHALL
  - WHEN evidenceをGateへ採用する THEN qualification fingerprintは24時間以内、confirmation evidenceは7日以内であることを再照合し、期限超過を`blocked`にすること SHALL
  - WHEN scoring rule、fixture、prompt、schema、runner共通部が変わる THEN合成器は全platform証跡を失効し、platform adapterだけが変わる場合は当該platformだけを失効すること SHALL
- **検証手段**: qualification失敗時のconfirmation未起動、隔離、TOCTOU、秘密値、全体/部分失効、FAIL後PASSの選別拒否、append-only台帳欠損をfault benchmarkで検証する。
- **Revision History**:
  - 1.0 (2026-08-11) FLW-REV-008のP0/P1を受け、M1〜M5横断のqualification・証跡合成契約をdraft起票
