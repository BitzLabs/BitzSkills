# 計画スキルの証拠説明是正と利用上限による停止

対象は `1e3a4726dddfabfcedf42a7f8130317d5d8ce450`、sdd-plan 0.1.1／bitz-sdd 0.2.1、評価集合 sdd-0.1.4、モデルgpt-6.1-sol（unversioned-alias-observed-2026-10-04）。既存assertの検査範囲、コードからの推論、追加予定、未実行結果を区別する狭い指示を加えた。元0.1.3の不適合、固定テスト、ケース、評価器、Core、製品規範は変更しない。

是正の独立検分は妥当。実モデルではSP-003の両反復が、空入力の型・要素型・内容を未検査、テストを未実行と正しく説明した。独立意味検分はskill反復1全7＋SP-003反復2の8件で8適合／0不適合／0不明。元0.1.3の両反復不適合を成功に変えない。

予定した限定検証は計画7ケース×skill/baseline×2反復＝28回以内。実際はskill11呼出し、10完成、1中断で止まった。完成分は全4機械検査通過、反復1は7/7、反復2はSP-001／SP-002／SP-003の3/7。SP-004反復2は9回の読取り操作後にCodex利用上限でturn.failed、codex exec exit 1。保存・Core・テスト実行・最終decisionはない。stderr.logは空で、上限の実エラーはtrace.jsonlに記録されている。

評価器が失敗を観測して新規投入を停止した。反復2のSP-005／SP-006／SP-007、baseline全14、実装ケースはこの版で未投入。自動再試行は0。独立レビューも同じ利用上限で停止したため、後に完成したSP-001／SP-002反復2は独立意味認定を行っていない。主作業者の機械照合を独立レビューへ読み替えない。

固定68枠の原scoreはFailed／not-certified、conditionErrors=[]、exit 1。skill反復1は7/17、反復2は3/17、baseline各0/17。58 missing runには中断1件も含まれる。scoreの未完了と、完成した限定ケースの適合は分けて報告する。Phase 2全体、Skill Gate、比較効果、品質接続、収束、配布は未認定。

主作業者の実出力: 公開CLI例 `Ran 2 tests in 0.924s / OK / exit 0`、評価器 `Ran 30 tests in 16.642s / OK / exit 0`、audit `Passed / cases17 / errors[] / exit 0`、quick_validate `Skill is valid! / exit 0`。独立実行は2 tests in 0.941s、30 tests in 16.660s、各OK／exit 0。主作業者も元理由と固定assertを直接照合し、完成10runの登録artifact SHA-256計50件が全て一致した。

evidence.tar.gzは372 member／246520 byte、SHA-256 `b6b62deae62177ef6ce6946debeeea7023e09826808c29a47b12760919f38894`。元trace／host／workspaceと10完成runを保存し、Git内部・Codex state/logs・資格情報は除外した。score SHA-256 `585cd930ef352aae969f4b6cb1bb879c5581e4898c04cddb9628eb9d3a48c0ea`。独立報告と機械照合は利用上限前に完成した8件分の原本を複写した。

実モデル呼出し累計は初回2＋先行4＋0.1.3測定34＋今回11＝51回。承認済み上限70回に対し残19回。ただし残枠があってもCodex利用上限中は起動しない。usageの完成turn集計はinput_tokens884280（cached_input_tokens733952はその内数）、output_tokens10192、reasoning_output_tokens241。中断turnには使用量の確定値がなく、請求額を推定しない。

再開時は利用上限の解消を先に確認する。中断SP-004を自動再試行せず原本を保持し、別の再試行記録・費用判断を伴う実行方針を人間に確認する。まず未独立認定2件の理由検分を再開し、残りの限定検証を承認枠内で進める。全件評価や完了認定には不足する枠とゲートを別途明示する。
