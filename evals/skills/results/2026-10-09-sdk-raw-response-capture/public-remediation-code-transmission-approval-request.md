# Phase 4：SDK raw捕捉の是正後コードの送信対象

この文書はv0.2の承認・送信履歴。ユーザーがOKと回答し、下記8公開パスを同宛先へ1回送信した。
結果はP2が1件/CLI exit0。v0.2枠は消費済みであり、追加送信には流用しない。
原結果と照合器の是正は[検証記録](report.md)へ記録する。

確定source: `1775038798653da9a6801ea0402c22febae2273a`。前回の公開8パスのうち、局所完了判定と回帰試験の2ファイルを修正した。
前回v0.1はユーザー承認の1回を消費し、P2が1件出た。原結果・消費枠は保持する。
修正後の同じ8公開パスをOpenAI Codex CLI/gpt-6.1-solへ静的再検分のため1回送信する案である。

| パス | bytes | SHA256 |
|---|---:|---|
| evals/skills/routing/production_operation_probe.py | 19532 | `38611ea7dfc01c13005bacab73294b669e562b1d03ca21c514beda59b6fea1c1` |
| tests/skills/test_production_operation_probe.py | 13704 | `06ef63bacd00a0ad16dfe47ba7c89a6fd489ac707314b88240aeaf8e74137001` |
| evals/skills/routing/production-operation-probe-v0.7.json | 3415 | `a4591b0315ca2474fa3ca92f17ffd0bb951280bf649fd68b4520a3484e52722f` |
| evals/skills/routing/production-operation-probe-v0.8.json | 4004 | `5cb8d0848cc001bfa3c0297dd24feba33584b0aa44c2a754ff55f8c69b073f1f` |
| evals/skills/routing/production_sdk_probe.py | 16846 | `29b0d201bdca9796c9fcbcc6c2b5de282dd9bfc2a579ea7d430d0efa15fb11ae` |
| evals/skills/routing/production_cli_probe.py | 14738 | `cc64e4fdff0612e0e72072b88b78993e6128a63d0df7aa890b55e939e6757fe7` |
| evals/skills/routing/source_guard.py | 3044 | `553bfe5c3c2a1aa33b44551da910a4f80c1ba86ea69b13dcedcedf22d1444489` |
| evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-artifacts.py | 12568 | `618c30974a7605c5f2192076f953ef7f57c9af71437e3e66d8f63ae69547db06` |

合計87851 bytes。固定検分指示・限定条件・source ID・行番号/hash・公開schema（922 bytes）を追加する。
原ログ・実際の通知本文・snapshot・認証情報・私的入力は送信しない。
独立SOL1回上限、一次0・追加委譲0・自動retry0・timeout300秒。
検分者のtool・試験実行・repo/home読取りは禁止。原stdio/schema/最終JSON/exit/usageとsource guardを保持する。

別有限契約は `evals/skills/routing/sdk-raw-response-review-v0.2.json`、
保存先は `.venv/sdk-raw-response-independent-review-02`。未送信・未起動・未予約である。
承認対象は上記確定sourceの8公開ファイルを同宛先へ追加1回送信すること。
SDK監査接続・任意複数cell/yield/wait・実provider・一次採点・Phase完了の認定を含めない。

```text
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/routing/run_sdk_trace_review.py --source 1775038798653da9a6801ea0402c22febae2273a --raw-capture-remediation
```
