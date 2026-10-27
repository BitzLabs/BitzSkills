# Phase 4：入力・証拠監査器のP2是正検証

修正版source `7fa403a1ade5e1dc6d57f1749bda78fdd397da2c` の9ファイルを固定し、公開コードの独立SOL検分1回でP1=0/P2=0となった。
親も対象26件を再実行し、原報告・レシート・予約・試験ログ・ソースを照合した。
結果はコンポーネントの修正確認として記録する。独立検分の手順には下記の制限が残る。

旧指摘3件に対し、明示的なfinal_answerと開始/完了phase一致、最終応答開始前の全tool完了と以後のtool拒否、
実hostと同じmanifest scope/schemaVersionの必須照合を追加した。
独立検分の敵対ケース8件もすべて拒否した。旧sourceのP2=3、原報告/receipt/予約、消費済み1回は保持する。

実結果は次のとおり。

| 実行者・対象 | 実出力 | 終了コード |
|---|---|---|
| 親・確定sourceのclean全skills | Ran 320 tests in 60.302s / OK | 0 |
| 独立SOL・対象 | Ran 26 tests in 0.227s / OK | 0 |
| 独立SOL・全skills | Ran 320 tests in 60.389s / OK | 0 |
| 独立SOL・敵対入力 | 8件すべて拒否 | 0 |
| 親・対象再実行 | Ran 26 tests in 0.219s / OK | 0 |

検分者自身の最初のsource guardは、初期ソース読取り後・敵対検分/試験前だった。
読取り開始前guardを実施済みとは扱わず、原receiptのexecutionPointと欠如記録を保持する。
親の呼出し前予約guard、検分者の読取り後/test前guard、保存前guard、親の再照合は対象9件で一致したが、
これで検分者の読取り前要件を代替したり、完全な手順通過やPhase/Gate完了を認定したりしない。

原provider bytesは取得できないcollaboration経路である。証拠はtool transcriptとローカル試験出力に限定する。
独立SOL消費1/残0、一次0/追加委譲0/自動retry0。私的評価入力は使用していない。
Core/fixtureの変更はなく、Gate A/Bの再認定対象ではない。

原ローカル証拠は `.venv/production-trace-review-02/` に保存し、公開summaryにSHA-256を固定した。
`verify-parent-artifacts.py` は新旧原証拠、schema、source9、実試験ログ/件数/終了コード、手順制限を再照合する。
ローカル原証拠がない環境では検証を停止し、公開summaryだけを原証拠の代わりにしない。

次は同じPhase 4の実CLI接続、tool構成の実効検証、入力/catalog/manifestの実行契約束縛、一次永続台帳。
それらと別有限canary契約が整うまで有料一次を起動しない。
実native接続、行動、Skill Gate、製品完了・リリースは未認定。
