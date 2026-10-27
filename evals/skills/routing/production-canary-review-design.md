# 公開カナリアの原結果照合と独立採点の接続設計

- 状態: Draft（R02の接続設計とコンポーネント実装中、非規範）
- 日付: 2026-10-11
- 開発計画: [提案31](../../../docs/04.提案資料/31_スキル統合残件の開発計画と進捗.md)
- 取得契約: `production-canary-v0.1.json`。一次最大4件・各独立1回。自動retry 0。
- この設計のみでは一次/独立モデルを起動しない。

## 1. 接続する順序

一次の予約→原取得→親の構造・原bytes照合→独立入力の固定→独立予約→別文脈SOLの採点→原応答と使用量の再照合→親の最終レシート→共有台帳の確定、とする。
未検分・停止・欠測・改変がある間は次の一次を予約しない。捕捉CLIのexit 0だけではacceptedにしない。

## 2. 既存実装の適用範囲

| 既存部品 | 利用する契約 | R02で追加する検査 |
|---|---|---|
| production_canary_capture.py | 入力固定・予約・隔離・原取得 | 原receiptと契約・予約・全原artifactの束縛 |
| production_ledger.py | 共有排他・独立起動前予約・verified review入口 | 原独立応答/receiptと親再照合からだけ確定を呼ぶ |
| production_rpc_capture.py | 呼出し/応答/開始/完了の相関 | 一次のSDK thread/turn引数・schema/effortの正確な照合 |
| production_trace.py | host本文/manifest/native finalの一致 | 一次profileの閉じた通知集合・禁止tool・順序・停止の検査 |
| production_sdk_trace.py / production_canary_trace.py | 診断profileの原相関・親子ID | 一次profileを別入口で検証し、診断の成功へ別名置換しない |
| production_connection_evidence.py | 実接続の固定入力・usageの照合 | 複数inferenceと実list/readを持つカナリアの原rollout対応 |

既存の診断SDKはturn/startの `threadId/input` 2キーを要求し、thread/startの `experimentalRawEvents` を許容しない。
一次実行器はthread/startへ `experimentalRawEvents: true`、turn/startへ `outputSchema/effort` を明示する。
2026-10-11に合成入力を既存 `requests` へ与え、`unknown SDK thread params` で拒否することを実確認した。
この違いは専用の一次profileとして実装する。既存診断の許可を広げて実結果とみなさない。

## 3. 原結果の構造検査

- 基準source・候補manifest・共通catalog・入力・環境・契約・attemptをGit原bytesと共有台帳へ照合する。
- 読める成果物は固定名と許容rollout構造のみ。認証・cache・stateのファイルは一覧に含めず、receiptに任意パスがあっても読み始める前に拒否する。
- 必須artifactの欠落、unknown artifact、絶対/親パス、symlink、hash不一致、停止marker、timeout、captureIntegrity=falseは停止する。
- 原SDKのinitialize/initialized/thread/start/turn/startの回数・順序・UUIDと、原応答thread/turn/開始/完了を照合する。
- providerはbitz_openai_http、modelはgpt-6.1-sol、read-only/never/ephemeral/fallback禁止、共通指示、cwd、raw events、JSON Schemaとeffortを一致させる。
- 原stderrから対象行を漏れなく投影し、保存projectionと照合する。本文は公開せずhashと集計のみを残す。
- direct制御はexec/waitの既知有限profile、子はproduction-routingのlist/readだけ。未知source/操作/通知/不適合順序は停止する。
- 正例は一覧1/選択SKILL本文1、負例は無読取りまたは一覧のみ。本文・host/native結果・選択パス・finalを相関させる。
- 原client requestの初期入力と後続tool結果、rollout context、usageを相関する。HTTP/SSE wire全文、server内部入力、送信前hard capを認定しない。

## 4. 独立採点と台帳の確定

独立採点用の版付きSchema/有限契約/実行器を新規に定義する。静的検分のSchemaを一次の意味採点へ流用しない。
独立入力には、原入力、固定期待、候補本文の証拠、原軌跡、親の構造検査結果とhashを束縛する。作業者の会話履歴を引き継がず、tool/追加agent/別モデル/自動retryを起動できない文脈を用いる。
各独立呼出しは共通台帳のreserve_independent_reviewで入力hashを起動前に固定する。
戻り値はcase/反復/source/入力hash/軌跡hash/意味判定/安全判定/所見/制限を持つ。判定理由の根拠は原入力と原操作に限定する。
CLI正常終端、保存応答と原最終応答の一致、使用量、独立入力・予約・出力hashを親が自分で照合する。
機械的な構造検査または独立採点の必須条件が失敗した場合はstoppedを記録する。acceptedはP1/P2=0、正常終端、原結果一致、意味・安全適合が揃った場合だけとする。
確定レシートは既存のrecord_verified_reviewへ渡し、合成用record_reviewを製品の記録に使わない。
少数4件の結果でSkill Gate/行動/実地/Phase/リリースを認定しない。

## 5. 実装順と無課金回帰

1. 一次SDK profileと原artifactの許可集合を固定する。
2. 既存親子相関・host/final照合へ専用profileを接続する。
3. 実client rolloutとusageの束縛を接続する。
4. 独立採点のSchemaと有限実行器を実装する。
5. 親レシート生成とrecord_verified_reviewを接続する。
6. 確定ref・clean treeの無課金検査、独立検分後にR03を開始する。

回帰は入力/期待/Schema改変、原artifact欠落/追加/escape/symlink、原hash改変、旧ref、SDK policy上書き、未知source/tool、未読本文、親子ID矛盾、重複final、usage改変、独立入力/予約欠落、receipt差替え、未検分の次予約、停止後の起動拒否を含める。
正常合成例と負例を通して、実providerの結果を模擬成功へ読み替えないことを確認する。

## 6. 実装状況（2026-10-11）

一次SDK profile、原artifact/固定入力/予約、原RPC/host/native final、完全初期context、rollout/raw/lastと累積usageの相関、固定CLI50資源、校正原12artifactを実装した。独立意味採点には専用SchemaとSOL 1 CLI・1論理turn・300秒・retry0の有限実行器を接続し、原入力/hash/予約/応答/正常終端/usageを親で照合してrecord_verified_reviewへ渡す。

失敗は一次と独立のtyped stopへ保存する。欠測usageを0へ置き換えず、不正artifactは再読取りしない。原拒否receiptは不変コピーとして保持する。production_canary_campaign.oneは1attemptだけを取得→構造→独立→親確定の順で進め、未検分/停止後の次予約を禁止する。

原artifactの最終是正はb64772aa、native可変辞書は4eb6a871、本文/追加context/校正RPCは後続refで独立確認した。c9614b52の全627試験は通過したが、失敗時の再受理とreceipt消失のP2=2が追加された。原指摘を保持し、是正したclean検証ref912c63faで全件試験・独立検分を実行中。R02全体は完了判定前。

校正04はclean c9614b52の固定runtime・network隔離・認証mountなし・局所1要求・課金0で成功し、manifest版0.1.1へ原記録を固定した。一次/独立評価モデル0。912c63faの入口事前検査は実runtime/校正04/snapshotの照合を通過した。局所校正で実provider/wireを認定しない。少数カナリアの成功も行動・Skill Gate・実地・リリースを認定しない。


5bdfdb23の全641試験と既存契約audit通過、別文脈の90canary/34ledger/対象4試験と原race是正確認、実runtime/校正04再照合を完了した。独立文脈が設計§5の全接続と次枠拒否を確認し、「R02実装・無課金検分範囲でR03開始可」と判断した。R02接続実装の検分を完了し、実provider/SOLの成功はR03の原証拠で検証する。
