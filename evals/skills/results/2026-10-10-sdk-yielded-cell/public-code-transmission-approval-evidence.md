# Phase 4：承認済み公開8パスのyield/wait捕捉修正版

2026-10-10。ユーザーは[前回の具体的な送信範囲と継続範囲](../2026-10-09-sdk-raw-response-capture/public-verifier-remediation-code-transmission-approval-request.md)にOKと回答済み。同8公開パス・同宛先OpenAI/gpt-6.1-sol・各確定refにつき独立静的検分1回・一次0・委譲0・自動retry0の継続承認を用いる。元承認を今回の別パスや実ログへの送信に広げない。

今回のコード確定refは `5ddc3c3f1ac052e5990df32e3ed2de806ce6af85`。新契約 `sdk-raw-response-review-v0.4.json`、専用出力 `.venv/sdk-raw-response-independent-review-04`。原SDK試行は別の無課金局所模擬で1回・HTTP3件を捕捉済み。レビューに原通信を送らない。

| パス | bytes | SHA256 |
|---|---:|---|
| evals/skills/routing/production_operation_probe.py | 23038 | `1ccc86b7c7816470a2273b5c1509ac9dcaf4061ab43fafe32c341c6310e05e33` |
| tests/skills/test_production_operation_probe.py | 22425 | `b76e0361e436ec82ccb4fceab280f496a85800bfb3510a438515f95f699ab147` |
| evals/skills/routing/production-operation-probe-v0.7.json | 3415 | `a4591b0315ca2474fa3ca92f17ffd0bb951280bf649fd68b4520a3484e52722f` |
| evals/skills/routing/production-operation-probe-v0.8.json | 4004 | `5cb8d0848cc001bfa3c0297dd24feba33584b0aa44c2a754ff55f8c69b073f1f` |
| evals/skills/routing/production_sdk_probe.py | 16846 | `29b0d201bdca9796c9fcbcc6c2b5de282dd9bfc2a579ea7d430d0efa15fb11ae` |
| evals/skills/routing/production_cli_probe.py | 14738 | `cc64e4fdff0612e0e72072b88b78993e6128a63d0df7aa890b55e939e6757fe7` |
| evals/skills/routing/source_guard.py | 3044 | `553bfe5c3c2a1aa33b44551da910a4f80c1ba86ea69b13dcedcedf22d1444489` |
| evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-artifacts.py | 15384 | `50a223766d2aa1168d98b6973c2abd11cae106c567bf43fb1a7eae5fe11826fd` |

合計102894 bytes。固定指示・限定条件・行番号/hash・公開schemaだけを加える。新v0.9契約本文、原ログ・実結果・snapshot・保持資料・認証情報は送信対象ではない。検分者のtool・追加モデル・repo/home読取りを禁止し、原stdio/schema/最終JSON/exit/usageを保存する。

最初の起動要求は自動承認審査が「具体的な送信対象と宛先への明示承認を確認できない」として拒否した。元承認と今回の対象パスの一致を示して、確定ref `d5918b345f427590a3fcdc3ac31d22463c558496` の同じ正規コマンドを再審査へ提出したが、「承認記録ファイルは信頼できるユーザー発言ではない」として再び拒否された。2回とも起動・送信・予約0、出力04は未作成。回避実行をせず、ユーザー本人の具体的な送信許可の回答を待つ。独立検分は未実施である。
