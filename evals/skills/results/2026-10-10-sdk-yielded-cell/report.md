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

## 独立検分のP2と局所是正

ユーザーの具体的な許可回答後、source7d7552e/v0.4の同8パスを1回送信した。
CLI exit0/timeoutなし/review_findings/P2が1件。input37636/cached0/output1097/reasoning625。
原receipt SHA256 `3d918bcba7017626c3d705fc3af9ced1babbece845f1ad02702355fc2f01f520`、
原response SHA256 `673ba24733a27a78be65c16a45545c0febcbc24999da93eaf623fed4da483d3b`。
親が原stdio/hash/schema/最終JSON/usage、確定Git、前・起動・後guardと有限予約を再照合した。

P2は元の第2要求のlistedを確認せず、第3要求の再掲からstageだけを集める点。
歴史Gitのisolated内の当該終端分岐を合成入力で実行し、元listed欠落・kind改変・本文欠落でもwaitCompleted=trueとなることを再現した。
これは原ログの改変やSDK全体の実行を再現した主張ではなく、固定終端分岐の合成入力での検査不足を示す。

listedを第2要求、readを第3要求から取り、再掲履歴を型も含めて照合するyielded_observationを終端へ接続した。
各段階を1件に制限し、kind/stage/本文ラッパー、成功状態、原ホスト結果との本文一致を要求する。
JSONの重複キー・非有限数も拒否する。欠落・再掲改変・偽kind/段階・重複・本文欠落・エラー・型違い・未完了の回帰を追加した。
局所28件/0.099s/OK/exit0、合成P2入力の拒否と旧原捕捉への修正判定の適合を確認した。
新模擬・HTTP・一次・追加モデル0。原v0.4と旧捕捉を保持し、是正後の独立通過はまだ判定していない。
同8パスの継続許可により、別有限契約v0.5/出力05で修正版を1回再検分する準備をした。
