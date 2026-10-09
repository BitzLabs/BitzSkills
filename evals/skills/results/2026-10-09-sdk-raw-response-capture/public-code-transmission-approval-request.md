# Phase 4：raw通知捕捉の独立SOL検分の送信対象

対象source: `4be29c094adb27fe897e72b3d841dcd73b5d0995`。
全465件/61.858s/OK/exit0と原証拠照合が済んだ新規raw通知捕捉の公開コードだけを、
OpenAI Codex CLIのgpt-6.1-solへ静的検分のため送る有限1回を準備した。
前の具体的な継続承認はSDK診断の6パスだった。今回は下の8パスを使う。
原ログ・実際の通知本文・snapshot・認証情報・私的入力は送らない。

| パス | bytes | SHA256 |
|---|---:|---|
| evals/skills/routing/production_operation_probe.py | 18409 | `2efeed657e25562761ed738fec639410066325cfb85eab6a631b97f659c0f4b4` |
| tests/skills/test_production_operation_probe.py | 11523 | `be89916c342e02e7ea8516ed21c6e3534a4904971243ebb03eed603bf4be1029` |
| evals/skills/routing/production-operation-probe-v0.7.json | 3415 | `a4591b0315ca2474fa3ca92f17ffd0bb951280bf649fd68b4520a3484e52722f` |
| evals/skills/routing/production-operation-probe-v0.8.json | 4004 | `5cb8d0848cc001bfa3c0297dd24feba33584b0aa44c2a754ff55f8c69b073f1f` |
| evals/skills/routing/production_sdk_probe.py | 16846 | `29b0d201bdca9796c9fcbcc6c2b5de282dd9bfc2a579ea7d430d0efa15fb11ae` |
| evals/skills/routing/production_cli_probe.py | 14738 | `cc64e4fdff0612e0e72072b88b78993e6128a63d0df7aa890b55e939e6757fe7` |
| evals/skills/routing/source_guard.py | 3044 | `553bfe5c3c2a1aa33b44551da910a4f80c1ba86ea69b13dcedcedf22d1444489` |
| evals/skills/results/2026-10-09-sdk-raw-response-capture/verify-artifacts.py | 12568 | `618c30974a7605c5f2192076f953ef7f57c9af71437e3e66d8f63ae69547db06` |

合計84547 bytes。ほかに固定検分指示・限定条件・source ID・行番号/hashと公開schema（922 bytes）を付ける。
契約は `evals/skills/routing/sdk-raw-response-review-v0.1.json`。
source/hashを親が入力読取り前と呼出し前後に照合し、原stdio・schema・最終JSON・実exit・usageを保存する。
独立SOL1回上限、一次0、追加委譲0、自動retry0。検分者のtool・試験実行・repo/home読取りは禁止。
この承認は新規捕捉の公開8パスの当該sourceの静的検分1回だけを対象にする。
SDK監査への接続・任意複数/yield/wait・実provider・一次採点・Phase完了の承認は含めない。

準備したコマンド:

```text
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/routing/run_sdk_trace_review.py --source 4be29c094adb27fe897e72b3d841dcd73b5d0995 --raw-capture
```
