# 計画ケースの再開とbaseline理由不適合による停止

測定refは `1e3a4726dddfabfcedf42a7f8130317d5d8ce450`、評価集合sdd-0.1.4、source SHA-256 `560ba39d6ada7b6227c2193f862e8fa58cfbf318083f6660dbb1208bb94875df`、gpt-6.1-sol／unversioned-alias-observed-2026-10-04。前回のed25e898は証拠と進捗だけの変更で、Core・スキル・評価器・ケースの差分は空だった。比較条件を維持するため測定中だけ元refへdetachし、終了後codex/sdd-plan-japaneseへ戻した。

利用者の再開指示後、前回未独立認定のSP-001／SP-002反復2を実証拠で独立検分し、両件の意味適合を確認した。利用上限で中断したSP-004反復2は原本を保持し、別出力先への手動試行として1回実行した。次に未投入のSP-005／006／007反復2を実行した。新規skill4件は全4機械検査と独立意味検分を通過。

前回完成10＋今回skill4＝計画7ケース×2反復の全14完成件で、機械適合・独立意味適合を確認した。独立検分は全70artifact hash、trace/host、最終応答、snapshot、source/case hash、実読・実書内容を照合して一致、Core実操作17回。元SP-004の中断はFailed/Incompleteのまま別に保持し、元0.1.3の説明不適合も成功へ変えない。この14件は発火Gate、実装ケース、baseline比較、Phase 2完了、Skill Gateの認定ではない。

続くbaseline SP-003反復1は機械全4検査を通過したが、独立意味検分はfailed。「文字列のエラーリスト」を回帰条件に含め「これらのテストは既に存在する」と既存テストへ対応付けた。しかし固定test_emptyはlen==1だけで、list/str型や内容のassertはない。主作業者も元reasonと固定assertを直接照合した。Core結果・無変更・未実行の説明は整合するが、検査範囲の過大申告が残った。skillの結果に混ぜず、必須不適合で追加投入を止める従来方針を維持した。baselineは1件実行・1件意味不適合・残13件未投入であり、比較効果を一般化しない。

再開実行は計5回（skill4＋baseline1）。累計は51＋5＝56回、承認済み上限70に対し残14回。自動再試行0、原中断と別の手動試行1を明記する。新しい記録は.venv/sdd-evaluation-04-resume、元.venv/sdd-evaluation-04は変更せず、前回の固定68枠score Failed／not-certifiedも上書きしない。

主作業者の再開前実試験: `Ran 30 tests in 16.698s / OK / exit 0`。元refと現在ブランチの対象source差分は空。前回10件と新5件の登録75artifact SHA-256が全て一致。新5件のarchiveは159 member／93807 byte、SHA-256 `6c7f27a6f2e929ec0e350d90ae1c4c8d061a62194f05a8b6857b1b372778b7c3`。Codex state/logs、Git内部、資格情報を除外した。全14skillとbaseline1の独立報告・照合JSONは原本を保存した。

新5件の完成turn usageはinput_tokens412265（cached_input_tokens328576は内数）、output_tokens4492、reasoning_output_tokens200。請求額は推定しない。これらの実測件数はレビュー用モデル呼出しの件数ではなく、隔離評価trajectoryの件数である。

次の案はcontinuation-proposal.jsonに記す。baselineの「理由説明の意味不適合」だけは失敗を残して他の予定ケースの比較を続けることを、人間の承認条件とする。機械4検査、安全性、実行障害、skill不適合では引き続き停止。ケースや期待を緩和せず、失敗したSP-003反復1を再試行しない。残り13回以内なら累計最大69、承認済み70枠を超えない。この停止方針変更はまだ承認・実行していない。全17ケースの比較や後続工程は別途不足する枠と証拠を提示する。

継続案と事実記録も独立検分し、必須是正の指摘なし。予算56＋13＝69≤70、未投入の予定反復と再試行の区別、原中断のhashとdecision/run不在、元scoreの保持、archiveとusageを直接再計算して一致した。提案pendingを実行許可へ代えない。この文書保存中のツリーには未追跡報告があり、保存前のこの状態をcleanと記録しない。
