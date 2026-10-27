# Phase 4：固定yield/wait親セル継続相関の専用監査（2026-10-10）

固定probe-call/exec→probe-wait/wait、cell=1、native list/readの2子IDに限定する専用入口を追加した。
旧audit_parent_linksの1exec範囲と未知wait停止は維持する。原入力は変更しない。
2つの親timingと2子のcell/runtime ID、受理/dispatch/result/ready、一覧をexec側・読取りをwait側の順に照合する。
exec結果後のwait開始、3つの局所provider要求と各親開始/結果の順、native子のthread/turnも検査する。
新API自身がwire本文を認定したとは扱わず、callerが旧原保存物へ照合する検査と区別する。
任意複数cell・全native lifecycle・実provider・一次測定・Phase/Gate全体は未認定。

局所82件/0.756s/OK/exit0。確定ref `4ec01ad8e1783dd9596406ac1f11bebaa5b9f7bb` のclean全488件/61.897s/OK/exit0。
原捕捉の全target24行とnative子2件・同じcell=1にも適合した。前後のguardを照合した。
新模擬/HTTP/有料モデル/一次/委譲/自動retry0。原捕捉と旧P2・原モデル応答を変更していない。
原試験stderr SHA256 `62e8cad8be6fb48a3e4d22fff2f5f3a0c86e73f4566b0f070938eaf4a1290635`。
原telemetry値SHA256 `a1071dce17c7ec967dcbb13641db81886d53a2737df173fa60ca574c00767793`。
原検証summary SHA256 `b8fa026e7464d72df3b4994680b57268149e15c8f9d1636ce42b68194060ce3c`。
記録照合の実出力はrecorded_yielded_parent_results_match_original_bytes/tests488/nativeChildren2/traceRows24/exit0。

同6公開パスの有限v0.20によるSOL検分を起動要求したが、自動承認審査が
「6パスとOpenAI/gpt-6.1-solへの具体的な許可を提示ユーザー発言から確認できない」として拒否した。
原の6パス継続承認記録だけでは本人の具体的許可を確認できないという理由であり、回避実行はしない。
拒否された要求ではモデル起動/予約/送信0だった。その後、下記の具体的な許可回答を得て初回起動した。
直前の捕捉側8パスは別系列で3回の検分と是正を済ませ、当該静的検分を通過している。
この監査側6パス・同宛先・各修正版1回の継続送信を具体的に示し、ユーザーは「許可します」と回答した。

独立SOL20は確定ref `5f874622d77fa10978a2ab56055539af9d28abec` で1回起動し、review_findings/P2=1/CLIexit0/timeout=false。
入力59635/cached0/出力1271/推論837 tokens。原receipt SHA256 `c9d873d6fa9213966690a0631e6a746b833bb5425b22de4b12d92d4db02f9cc8`、
原response SHA256 `d766c9b71dd06461f5e778bd5fd8c6dd078d21e52fc9dfb0f18fa30604f92b45`。
親が原stdio/schema/最終JSON/usage/hashと確定Git/前後guard/有限予約を照合した。
同threadの中央API要求に別turn_idを明示しても局所相関が通る指摘を、未修正コードと原捕捉のコピーで再現した。
neutralイベントの明示turn_idを確定turnへ照合する是正と回帰を追加した。省略turnは補完しない。
局所83件/0.798s/OK/exit0。原応答・指摘・消費枠を保持し、新有限v0.21で同6パスの修正版を1回静的検分する。
本段階の是正は独立未検分。Phase/Step/Gate全体は未認定。

是正source `1c6aa5f0c937ba418dfa3278f7f0723b05bd9c5d` のclean全489件/64.437s/OK/exit0。
原試験stderr SHA256 `956969c609dbea30a57a303ccf0cd41825658fca1de45ee2a83f41a955e7b32e`。
原捕捉への再適用も24行/2 native子/cell1で適合し、前後のsource guardが一致した。
v0.21の最初の要求は実行器の前回保存先20の許可一覧欠落によりunknown previous reviewでモデル起動前に停止した。
この停止で出力21・予約・送信・モデル起動は0。保存先を明示追加し、原停止を保持する。

保存先登録後のsource `150066085466344fd3026b675486fa26a729f4a3` はv0.21の初回1回でstatic_review_passed/指摘0/CLIexit0。
入力60463/cached0/出力1476/推論1420 tokens。原receipt SHA256 `59409d8c4802df380c6df1b358bc90bc57bfae0ba7f4dca78917938e2c1da0c2`、
原response SHA256 `f5ca7b969a8a5d8c0c74a386696b955aea117bfd70e7319ffcfea5715df44071`。
親が原stdio/schema/最終JSON/usage/hash、確定Git、前後guard、有限予約を再照合した。
全489試験sourceと独立検分sourceの同6公開パス本文は完全一致する。後者の追加差分は実行器の保存先登録と原記録。
公開記録照合器は旧P2の歴史Gitへの原捕捉コピーによる再現と、是正版の拒否・原捕捉正常系も再適用する。
当区切りのSOL実起動2/SDK静的系列累計21、一次・委譲・自動retry0。模擬・HTTP追加0。
固定親セル継続の局所是正と当該静的検分のみ通過。任意複数exec/cell、全raw/provider文脈、実provider、一次測定、Phase/Step/Gateは未認定。

記録照合コマンドは以下。新モデル・試行・HTTP・書込みを行わない。

```text
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/results/2026-10-10-sdk-yielded-parent/verify-recorded-results.py
```
