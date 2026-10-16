# 保持12ケース・24枠の評価接続

状態: 入力準備を実装中。実行器・有限台帳・開始前独立検分が揃うまでモデルを起動しない。

公開92枠の実行・記録は完了した。保持集合は独立意味検分を通過した
`production-routing-held-out-0.5.0` の12件をそのまま採用する。
ケース原bytes SHA-256は `3380c2935bac4b0ed9438ebbfffb3a786d7e7d0acc0ffacefea840a7a79edf25`。
公開結果 `results/2026-10-07-single-replacement-reviewed/summary.json` をGitの確定refで直接照合し、
新しい入力契約のhashへ束縛する。集合・期待値・採点基準を現行評価中に修正しない。

## 入力準備

`production_heldout_inputs.py` は公開92枠の入力束縛とは別の部品である。
全sourceのGit blobと作業ファイルを照合してから、承認済みcollection-05のケース原bytesを内部だけで読む。
絶対path全成分のsymlink、最終fileのhardlink、所有者・権限・サイズ不適合、同じfdの読取り前後の変化を拒否する。
非公開値を含むJSON/schema診断をそのまま出力しない。

12件を原順序のSE-1200〜1211に固定し、各2反復、一次24・独立24・retry0・delegation0とする。
全mandatory、区分の分母と6機能ごとの正例/負例・停止境界の対を確認する。
モデルpayloadは公開評価と同じ共通指示・イベントcatalogと各ケースのprompt/contextだけ。
caseId/category/capability/mode/mandatory/expectedと来歴・集合controlを渡さない。
親側の内部slotには採点に必要なIDを残すが、公開出力へ含めない。

```text
python -B evals/skills/routing/production_heldout_inputs.py --source <確定40桁commit>
```

この入口の出力は集合版・件数・hash・状態だけで、ケース保存・モデル起動・予約はすべて0。
入力準備の成功を、開始許可・測定成功・独立意味採点・Skill Gateへ読み替えない。

## 後続の実行条件

1. 公開評価時と同じ製品72資源の全bytes、共通指示・catalog・protocol・schema、固定CLI/SDK/runtime、
   当日の校正・環境を照合し、新しい確定refの専用契約へ束縛する。
   集合採用時の旧71資源と現在の評価対象72資源を同一候補の測定として合算しない。
2. 新規campaign、24枠の固定順序、一次/独立各24、有限timeout、retry0/delegation0とする。
   collection-05内の新規owner-only領域を唯一の証拠保存先とし、既存資料を書き換えない。
   台帳・予約・入力契約・payload・原軌跡・採点・親の照合をすべて非公開に保存する。
   別output/worktree/refで消費枠を返却できない共有の識別と排他制御が必要。
3. 一次モデルはprompt/contextだけをケース固有入力とする。独立採点は別文脈で原証拠と期待値を照合し、
   親が原bytes/hashを再確認してから次へ進む。危険操作・drift・不正原記録は全体停止。
   安全な誤選択は不正解、証拠が不足する個別取得失敗は評価失敗として分母に残す。
   個別失敗の封印と次枠の許可には現物資源の前/起動直前/後一致が必須で、失敗した枠の再試行は行わない。
4. 本番入口は最大2枠の自然終了単位とし、各論理起動は60秒以上離す。
   準備・独立検分・利用枠・認証・非公開の送信先/送信範囲を確認してから起動する。
   入力準備への読取り承認だけで、新たな外部送信を承認済みと推定しない。
5. 公開へは集合版・件数・hash・集計だけを保存する。ケース単位のID、選択結果、期待値、payload、
   native/SDK/Host原bytes、stderr本文、私的な保存物の一覧を公開しない。

## 終了後

公開92・保持24の実施/失敗/欠測を区別して検分し、その後に失敗原因と送信内訳を整理する。
失敗対策とコンテキスト削減は別変更・同条件比較とし、正しい動作・安全性・完了性を保つ。
今回誤った動作や評価失敗を再現することを合格条件にしない。
初期入力だけでなく追加取得を含む総入力・cache・取得回数・時間・正解/不正解/評価失敗を比較する。


## 専用台帳の部品（実行器は未接続）

`production_heldout_ledger.py` は非公開collection-05内の固定共有namespaceへ、
契約とhash鎖付きjournalを新規追記する。既存の契約・eventを上書きしない。
`open_shared` の保存先にworktree/ref/output引数はなく、別条件で既存契約を再初期化しない。
クラスの任意root引数は隔離試験用で、本番接続は固定factoryを用いる。

一次予約→起動marker→一次取得→独立予約→独立marker→独立取得→親照合の順序を固定する。
前枠が未了の間は次を拒否し、予約・起動markerを実provider呼出し数と同一視しない。
親照合は正解と不正解を別に記録する。個別失敗は起動markerの後だけ封印でき、
契約に一致する現物資源proofと失敗原証拠のhashを必須にする。正常測定へは変換しない。
全体停止は別eventで記録し、再開・追加eventを拒否する。

全操作は所有者限定のdirectoryとfile、NOFOLLOW/単一link、排他lock、
契約/順序/分母/前event hashの再検査を経る。途中保存の破損・不明file・journal欠番を拒否する。
台帳が受け取る原hashの意味・安全性は後続の取得/採点/親adapterで検査しなければならない。
この台帳の合成試験通過だけで、本番起動や非公開送信を許可しない。
