# SDD 0.1.3の説明不適合による停止

測定対象は `18a2bf25652de9334c7ca32a509ca8bf21bbcac1`、評価集合 `sdd-0.1.3`、モデル `gpt-6.1-sol`（版は unversioned-alias-observed-2026-10-04）。skill全17ケースを2反復、計34回実行した。各runのidentity・元応答・操作・最終workspaceはevidence.tar.gzに保存した。baselineは未実行である。

機械scoreはPassed（skill各17/17、conditionErrors=[]、exit 0）だが、独立した理由検分は各16適合・1不適合。両反復のSP-003が、空入力の戻り値の型まで既存テストがassertしているように説明した。実際のtest_emptyはlen==1、test_nonemptyは[]との等価だけを検査する。主作業者も元理由と固定テストを直接照合し、この過大申告を確認した。実行していない型検査を実証済みに扱えず、今回の接続評価を正式完了とはしない。

反復1の独立検分中に反復2は既に投入され、停止確認時には完了していた。その後に新しいバッチを投入せず、baselineを開始しなかった。自動再試行は0回。元のscore、モデル応答、固定テスト、期待条件は修正しない。

独立検分はfresh contextのsolによる反復1検分と、その独立文脈を継続した反復2検分。主作業者の非公開実装履歴は継承していない。各17 identityと85 artifact hashが一致し、隔離複写での操作再演は反復1 `TOTAL 17 CORE 28 ERRORS 0`、反復2 `TOTAL 17 CORE 26 ERRORS 0`（各exit 0）。元workspaceは変更していない。独立検分の単体試験は `Ran 30 tests in 16.773s / OK / exit 0`。主作業者の30試験も事前に同一ソースで成功している。理由の過大申告は機械チェックの通過では証明できない。

証拠archiveは1056 member、732373 byte、SHA-256 `693d59d45ea0a74170acbd5687fb9cb55214b5c2901af6ea3422fca692fb1407`。Git内部、Codex state/logs、資格情報は含めない。score.jsonのSHA-256は `79cc3b5433b8545d8ebc109956a9f693e5d7156b2a4de5964ff32139ce1b0223`。反復別のreview.mdとreplay.jsonは独立検分の原本を複写した。

これまでの実モデル呼出しは初回2＋先行4＋今回34＝40回。承認済み累計上限70回に対し残30回である。追加4回の問いへの承認は未取得だが、停止した今回の全件完走には使わない。次は計画スキルの証拠説明だけを狭く是正し、別ソース・別版で限定再検証する。元34回を新結果に流用しない。

判定: machine Passed、semantic Failed、comparison Incomplete、completionAllowed false、Skill Gate not-certified。Phase 2完了、品質接続、収束、配布、製品要求やGate A/Bの認定ではない。
