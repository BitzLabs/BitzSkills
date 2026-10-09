# Phase 4：原証拠照合器の是正後コードと継続送信の確認範囲

確定source: `f8e27f2ddf7d003df7f27236b1059557368534d2`。前回v0.2のP2に対応し、照合器自身へ成功フラグと開始RPC・終端の相関検査を接続した。
同じ8公開パスをOpenAI Codex CLI/gpt-6.1-solへ静的再検分のため追加1回送信する案である。
v0.1/v0.2は各1回を消費済み。原結果・指摘・消費枠を保持し、追加送信へ流用しない。

| パス | bytes | SHA256 |
|---|---:|---|
| evals/skills/routing/production_operation_probe.py | 19532 | `38611ea7dfc01c13005bacab73294b669e562b1d03ca21c514beda59b6fea1c1` |
| tests/skills/test_production_operation_probe.py | 18972 | `216fdf87fed61af6fc47ca407e2f8bab9bbcd70c721a4814b13c242252543cd5` |
| evals/skills/routing/production-operation-probe-v0.7.json | 3415 | `a4591b0315ca2474fa3ca92f17ffd0bb951280bf649fd68b4520a3484e52722f` |
| evals/skills/routing/production-operation-probe-v0.8.json | 4004 | `5cb8d0848cc001bfa3c0297dd24feba33584b0aa44c2a754ff55f8c69b073f1f` |
| evals/skills/routing/production_sdk_probe.py | 16846 | `29b0d201bdca9796c9fcbcc6c2b5de282dd9bfc2a579ea7d430d0efa15fb11ae` |
| evals/skills/routing/production_cli_probe.py | 14738 | `cc64e4fdff0612e0e72072b88b78993e6128a63d0df7aa890b55e939e6757fe7` |
| evals/skills/routing/source_guard.py | 3044 | `553bfe5c3c2a1aa33b44551da910a4f80c1ba86ea69b13dcedcedf22d1444489` |
| evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-artifacts.py | 15384 | `50a223766d2aa1168d98b6973c2abd11cae106c567bf43fb1a7eae5fe11826fd` |

合計95935 bytes。固定検分指示・限定条件・source ID・行番号/hash・公開schema（922 bytes）を追加する。
原ログ・実際の通知本文・snapshot・認証情報・私的入力は送信しない。
独立SOL1回上限、一次0・追加委譲0・自動retry0・timeout300秒。
検分者のtool・試験実行・repo/home読取りは禁止。原stdio/schema/最終JSON/exit/usageとsource guardを保持する。

今回の契約は `evals/skills/routing/sdk-raw-response-review-v0.3.json`、
保存先は `.venv/sdk-raw-response-independent-review-03`。未送信・未起動・未予約。

## 継続送信も承認する場合の固定範囲

今回の1回に加えて、今後も上記と同じ8公開パスの修正版だけを、同じ宛先・モデル・目的・非送信範囲で送信する。
各修正版は確定ref/hashで固定し、新しい有限契約と専用保存先を用いて、そのrefにつき独立静的検分を1回だけ実施する。
不適合や停止の原結果を保持し、修正とローカル検証を済ませてから新契約へ進む。自動retry・一次評価・追加委譲は行わない。
送信前に対象パス・bytes/hash・有限条件を記録し、別パスや原ログを追加する場合はこの継続範囲に含めない。
同じ8パスの修正版への継続承認があれば、同条件の送信ごとに再確認を求めない。
SDK監査接続・任意複数cell/yield/wait・実provider・一次採点・Phase完了の認定は、この静的検分の通過へ代用しない。

今回のコマンド:

```text
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/routing/run_sdk_trace_review.py --source f8e27f2ddf7d003df7f27236b1059557368534d2 --raw-verifier-remediation
```

