# Phase 4：可変ID軌跡と独立一次検分予約

source b83fee8609f28daf4bab967598b8310f9a55ce04 で、可変IDの限定SDK診断と一次台帳の独立予約を実装した。
single-exec/two-exec/exec-waitの正例と、無操作/一覧のみの負例をhost全文・原SDK入力・親セル/子ID・API順序へ結ぶ。
固定probe IDへ別名置換しない。上流wire/raw全payload、測定適格性、実provider実測をこの局所診断では認定しない。
一次独立予約は同枠の入力差替え、再起動、未検分、停止、孤立予約を拒否する。

## 原検証

clean全525件/66.033s/OK/exit0。stdout/stderr/source guard/入力本文hashを原bytesで保存した。
負例fixtureのoutcome enum誤りは初回5件中2 errors/exit1で検出し、not-applicableへ修正後5件/0.055s/OK/exit0。
一次台帳18件/0.298s/OK/exit0、旧SDK92件/0.937s/OK/exit0。
有限v0.27のSOLは起動前に一度自動審査で拒否された。この要求の送信/予約/消費は0。
継続許可済みの通常PUSH後、GitHub PUBLIC属性と6本文の公開ref blob一致を読み取り確認した。
この追加事実を添えた再審査は通過し、初回SOL1回/CLIexit0/timeoutなし/P2=1。
親も原stdio/schema/Git/guard/原応答と共通静的予約を照合した。別経路・別モデルによる迂回は行っていない。

## 指摘と是正

独立予約の欠落・変造が次試行時にreviewへ再照合されないP2を原結果へ保持した。
歴史Gitの元台帳で、試行1の正しいverified review後に独立予約を削除すると試行2へ進むことを、隔離合成台帳で親も再現。
製品open_ledgerで独立予約必須モードをcampaignへ固定し、合成record_reviewを拒否した。
次枠の予約前にも独立予約の原hashと検分入力hashを保存済みreviewへ再照合し、欠落・差替えを拒否する。
局所20件/0.308s/OK/exit0。新有限v0.28へ是正版を固定して独立検分する。
元525試験・P2・消費1を保持。一次0、委譲・自動retry0。実provider/完全入力/要求上限/実地/Phase/Gateは未認定。

source7c532ceのclean全527件/62.901s/OK/exit0、SOL28は初回1回/P2=1/CLIexit0、親の原応答・共通予約照合も通過。
追加P2はevents配列だけでは原stderrの全対象行を証明できない点。元結果と消費を保持する。
原stderr/選択ログbytesを必須入力にし、全対象2targetの原行から得たeventsだけを監査するように是正した。
両原hashを結果へ結び、追加API/未知操作の抽出漏れを拒否する。別targetや上流wire網羅は認定しない。
明示model/version/providerの矛盾とauth retryも拒否し、1子の負例の限定scope表記も合わせた。
局所6件/0.070s/OK、旧SDK92件/0.901s/OK、exit0。新有限v0.29で同6公開パスを検分する。

source4510997のclean全528件/62.803s/OK/exit0。通常PUSH後、有限v0.29の独立SOLは1回/CLIexit0/timeoutなし/P2=1。
指摘は操作結果に明示されたmodel/app.versionの矛盾を見逃すこと。親も合成tool_resultへ別モデルを入れた原ログで、
診断が通ることを再現した。有料一次0。原応答・消費枠を保持する。
実行環境の照合を全対象イベントへ移し、各profileの各イベントで明示矛盾を拒否する回帰試験を追加した。
この是正の独立再検分は未実施。局所修正を解消済み・実provider実測・Phase完了とは扱わない。

修正後の対象7件/0.253s/OK/exit0、作業ツリーの全529件/70.712s/OK/exit0を実行して確認した。
全試験のコマンドは`PYTHONPATH=plugins/bitz-core/src uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B -m unittest discover -s tests/skills -p 'test_*.py'`。
これは変更を含む作業ツリーの回帰結果であり、clean refの独立認定に置き換えない。
verify-recorded-results.pyはexit0で元525/最新528/独立SOL3/各P2=1/一次0を原bytesから再照合した。

2026-10-11時点の残工程：この修正の独立再検分、実providerの要求上限・完全初期入力の証明、
有限公開canary、本測定、5種類の実地比較とSkill Gate 4。送信許可待ちではなく、実装・証拠の未充足である。
5種は局所バグ、新公開動作、仕様/文書、security/未信頼入力、複合workspace。
時間・人手監督・費用・手戻り・欠陥・誤発火・追跡の比較を未実施として保持する。Phase 4未完了。

sourcea22df600のclean全529件/64.124s/OK/exit0。限定v0.30は修正対象の公開2本文16953bytesのみをSOLへ送信した。
独立SOL1回/CLIexit0/timeoutなし/指摘0、input12761/output231/reasoning173。対象是正の独立静的検分のみ通過。
原27/28/29の指摘・原応答・消費は保持する。この区切りのSOL計4、一次/委譲/retry0。
依存全実装、実provider、全初期入力、Phase/Gateを今回の静的検分から認定しない。
