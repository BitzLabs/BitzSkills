# 品質評価器の原出力保存中断を是正する

是正source `07db2a7f9aef68c09456df29fc5922699260ebe5`、
原source `3e181af4`、実行版 `quality-execution-0.1.5`。
品質スキル本文・公開入力・過去の比較結果は変更しない。

完了したnative出力の保存中にKeyboardInterruptが起きると、中断記録はできても
未保存bytesと併発したstderr保存失敗を残せなかった。
TimeoutExpiredのpartial output保存中のKeyboardInterruptでは、元timeoutの中断記録も残せなかった。
新13回帰試験を原refのevaluator bytesへ適用し、
`Ran 13 tests in 0.103s / FAILED (failures=2)`、exit 1を再現した。

各streamでKeyboardInterruptとOSErrorを捕捉し、もう一方の保存を試す。
未保存bytesはbase64で退避し、各保存例外と最初の例外を残す。
完了後は実exit、errnoのない中断はnullを保持する。timeoutでは元TimeoutExpiredと
partial bytes・保存例外を分ける。成功runへの変換、追加backend起動、旧停止枠の再開はしない。

実出力:

- 是正回帰: `Ran 13 tests in 0.108s / OK`、exit 0。
- 品質関連: `Ran 89 tests in 16.105s / OK`、exit 0。
- 全スキル単体: `Ran 198 tests in 52.632s / OK`、exit 0。
- SOL独立検分: `Ran 89 tests in 15.791s / OK`、exit 0、P1/P2指摘0。

独立検分後も作業者が品質89件を再実行し、source4件と独立ログのhashを再照合した。
新規一次軌跡0、事前固定したgpt-6.1-sol独立1枠、自動再試行0。
全一時領域はrepo内。実モデル比較・全Skill Gateの認定へ一般化しない。
中断記録自体の保存不能、記録中に重ねて中断が入る場合まで回復を保証しない。

原回帰・固定ref driver・新試験・独立所見・有限予算・親再検査・old/new sourceは
`evidence.tar.gz`へ保持する。保存監査は`archive-audit.py`で再実行できる。
原品質capacity通知・停止台帳・failed/unknown・SDD原失敗/P2の記録は変更していない。
