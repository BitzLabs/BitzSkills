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
今回のモデル起動/予約/送信0、出力20は未作成。独立検分通過や当Step完了とは判定しない。
直前の捕捉側8パスは別系列で3回の検分と是正を済ませ、当該静的検分を通過している。
次は[この監査側6パスの送信範囲](public-code-transmission-approval-evidence.md)を具体的に示して本人の許可回答を確認する。

記録照合コマンドは以下。新モデル・試行・HTTP・書込みを行わない。

```text
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/results/2026-10-10-sdk-yielded-parent/verify-recorded-results.py
```
