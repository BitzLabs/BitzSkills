# Phase 4：固定2execの原証拠捕捉と指摘是正（2026-10-10）

有限v0.10/source `27c399431ab09737927914e1b6942775bd229f43` で一覧取得と元一覧から選んだsdd-plan本文の読取りを別execへ分けた。
初回1試行・局所HTTP3/host2・有料モデル0。原RPC/SSE/SDK通知/stdio/全target telemetryと原snapshotを保持する。
原receipt SHA256 `b390a1791cdf06fdce9759f4d56b90cab66e2ce28022f902fd8dff347befb77b`。
namespace/runtime exit0、forcedShutdown=false、localErrors=[]、mockTurnCompleted/mockFinalMatched=true。
rawItems8/rawCompleted3、全target24行、観測セルは1/2。これを複数セル対応の認定とは扱わない。
既存1exec親監査は追加execをunexpected telemetry callで停止する。
原hash/Git/契約/SDK配送値/ホスト本文/呼出しと出力/再掲履歴/終了と候補71資源を親が再照合した。

初期局所36件/0.112s/OK/exit0。source `af35d0b7c9c9c1c6e1e69c76799e72efbecbbd81` のclean全494件/63.118s/OK/exit0。
原試験stderr SHA256 `b926f78c39d8eb82b028d3fa4c90c66c990389bbbaab8d9b2dca80849db2eee5`、
原検証summary SHA256 `0979cf3cce925bca963adf0917e1cae49ea56324e90b021514d6c9dd9f4f9e67`。

同sourceの承認済み公開8パス本文127003 bytesの独立SOL07はreview_findings/P2=2/CLIexit0/timeout=false。
入力44185/cached0/出力1114/推論425 tokens。
原receipt SHA256 `e97ad1c5a44c4cce5660d036cb78d8d172fb29b0a099c1f9c1210ac25f685cd6`、
原response SHA256 `7eddaa366239f5bcf92e31a5271ac9b4cf7febe2e8434e81182172ec82c11766`。
親が原stdio/schema/最終JSON/usage/hash、確定Git、前後guard、有限予約を照合した。

P2の1件目はhost引数の相関不足。yield側の別read pathと両モードのlist未知argsを歴史Gitと原捕捉コピーで再現した。
共通2段階でlist args={}と、元一覧の一意なsdd-plan pathへのread argsを厳密照合する。
P2の2件目は空白付き追加JSONの見逃し。両モードの最後の原出力へ空白付きstageをコピー追記して受理を再現した。
既知runtimeヘッダだけを分離し、残り全文をstrict JSON1件として解析する。重複・破損・未知本文を拒否する。
省略ヘッダの合成形式と実runtimeのWall time/Outputヘッダ、JSON前後の空白を許す正常系も保持する。
局所38件/0.106s/OK/exit0。旧yield原捕捉の記録照合もexit0。原ファイルの変更や新mock/HTTPはない。
歴史再現器の最初の実行は、旧sequentialが元々拒否していたread引数を追加再現条件へ含めて停止した。
指摘が対象としたyield read引数・両list引数・両空白付き重複に限定して再適用し、旧受理/新拒否を確認した。

同8公開パスの新有限v0.8/専用出力08で是正版を初回1回静的検分する。旧応答/指摘/消費枠は保持する。
任意複数セル・全raw/provider文脈・全native lifecycle・実provider・一次台帳統合・canary・Phase/Step/Gate全体は未認定。
eligibleForMeasurement=false、一次・委譲・自動retry0。
