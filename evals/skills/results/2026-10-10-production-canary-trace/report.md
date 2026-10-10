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
