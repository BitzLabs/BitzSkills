# Phase 4：固定セルのyield/wait原証拠捕捉（2026-10-10）

固定1execの一覧表示→yield_control→200msの待機→読取りと、同じcell_id=1へのfunctions.waitを1回、
Python SDK 0.160.1と局所模擬Responsesで捕捉した。実provider、一次評価、追加モデルは起動していない。
確定sourceは `5ddc3c3f1ac052e5990df32e3ed2de806ce6af85`。専用契約v0.9と出力09を使い、旧試行を変更していない。

局所試験24件/0.093s/OK/exit0。確定refの全476件/61.854s/OK/exit0を確認した。
SDK模擬試行は1回/局所HTTP3件/有料モデル呼出し0、namespace/runtime exit0、強制終了なし。
開始RPCのthread/turnとfinal→completed、エラーなしを原通知から再計算した。
原receipt SHA256は `eba92afac912898ffc7fa7e159fd47fd86f67196212ec3d0adfa11128b8f3904`。
試験stderr SHA256は `d7b434352cabca1ffcb174fb3f0e21071a25a3d6301a41807a2efb2d43911cee`。

原RPC raw通知はResponseItem8件、response完了3件。SDKへ配送されたmethod/paramsと完全一致した。
原SSE、provider inputの前置履歴、exec/waitのcall/output、固定final投影を照合した。
一覧と読取りの出力はそれぞれ中断したexecと完了したwaitへ分かれ、ホスト2件の本文と一致した。
固定snapshot71資源も歴史Gitへ照合した。原runtime stderrの全対象telemetry24行と選択ログはbytesで一致した。

既存の固定1exec監査は、新しいwaitのcall_idを `unexpected telemetry call` として停止する。
waitを無視して旧監査の通過へ代用しない。新しい継続相関の専用監査は未実装で、
任意複数セル・全native lifecycle・実provider・一次台帳・canary/本測定とPhase/Gate全体の認定は残る。
eligibleForMeasurement=false、phaseComplete=falseを維持する。

独立SOL検分v0.4は承認済み同8公開パスの修正版だけを対象として準備した。
最初の起動要求は自動承認審査で具体的な送信対象/宛先の明示承認を確認できないとして拒否された。
元の具体的継続承認と今回パス/hashの一致を記録して再審査したが、承認記録ファイルはユーザー本人の発言ではないとして再び拒否された。
回避実行はせず、レビュー04の起動・予約・送信0、独立SOL追加0。原捕捉を成功として再分類することなく、独立検分は未実施と記録する。
[対象8パス・本文bytes/hash・宛先・有限条件](public-code-transmission-approval-evidence.md)についてユーザー本人の具体的な承認回答が必要になった。

原証拠の再照合コマンドは以下。書込み・新模擬試行・局所HTTP・モデル呼出しを増やさない。

実出力は `recorded_yielded_capture_matches_original_bytes` /tests476/rawItems8/rawCompleted3/traceRows24/exit0。
旧raw捕捉とSDK raw交換の記録照合器もそれぞれexit0で、以前の原結果と独立検分の記録を保持している。

```text
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/results/2026-10-10-sdk-yielded-cell/verify-recorded-results.py
```

新契約作成時、元v0.8に存在しないconstraintsキーを参照して生成処理が停止した。
元のlimitationsキーを確認して修正した。SDK試行・課金枠は消費していない。
