# Phase 4：固定yield/wait親セル継続監査の公開6パス

[従来の具体的な6パスと継続範囲](../2026-10-09-sdk-context-remediation/public-code-transmission-approval-request.md)へのユーザー承認に基づき、同じ6公開パスのPhase 4監査修正版を同じOpenAI/gpt-6.1-solへ各確定refにつき1回静的検分する範囲で準備する。直前の公開8パス捕捉コードの送信とは別系列で、別パスや原ログへの許可に広げない。

有限契約v0.20/専用出力 `.venv/sdk-trace-independent-review-20`、独立1回・一次0・委譲0・自動retry0・timeout300秒。原stdout/schema/最終JSON/exit/usageとsource guardを保存する。起動前に確定ref/hashを照合する。

| パス | bytes | SHA256 |
|---|---:|---|
| evals/skills/routing/production_sdk_trace.py | 47990 | `9ad00df7b7b005671627be21816511f327a965a8db12f263c9ff6c6d2f118270` |
| evals/skills/routing/production_trace.py | 20872 | `18e5e58331f5420cee0b4047474ee8569775603b7cabd57c24084668fa354aca` |
| tests/skills/test_production_sdk_trace.py | 58662 | `43b9404668bc35b8a30e183fee26b0c1b1c8cc59ff258018621e009a4f3e46d6` |
| evals/skills/results/2026-10-08-sdk-trace-connection/verify-parent-links.py | 13405 | `1bff50bd5d53459ba19be0d0b0add5f08ba3fb49a653edd2660f6ec172e6955e` |
| evals/skills/routing/sdk-trace-review-remediation.md | 17712 | `4affbe7c7a90ffdd052280f75fd13eff04d25b42edb4b4c4604806a81b54300a` |
| tests/skills/test_production_trace.py | 30601 | `80f1037386cd22ebe02c4c78f27141583cd5ed56e199a60113fbd2f44d2dbd4b` |

本文189242 bytes。追加は固定指示・限定条件・source ID・行番号/hash・公開schema。原通知本文・telemetry・provider request/response・snapshot・保持資料・認証情報を送らない。検分者のtool・試験実行・追加モデル・委譲・repo/home読取りを禁止する。source refはコミット後に原invocation/receiptへ記録する。

この送信は固定1exec/1wait/cell1/2読取りの親セル継続相関コードだけの静的検分。原SDK捕捉側の8パスは今回送らない。実provider/任意複数セル/全native lifecycle/一次測定/Phase/Gateは認定しない。元v0.19の原結果と消費枠を保持する。
