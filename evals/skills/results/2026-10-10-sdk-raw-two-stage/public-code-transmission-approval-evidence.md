# Phase 4：固定3交換SDK監査の承認済み公開6パス

[具体的な同6パスと継続送信の許可回答](../2026-10-10-sdk-yielded-parent/public-code-transmission-approval-evidence.md)に基づく。
ユーザーは監査側公開6ファイルをOpenAI/gpt-6.1-solへ各修正版1回の静的検分として継続送信する具体的質問に「許可します」と回答した。
同6パスのsource `d76f002fa8e12d7bcd717c5ccf3945c07cc88500` の本文227124 bytesを有限v0.23で初回1回送信し、自動承認審査を通過した。
独立1回/最大300秒、一次・追加委譲・自動retry0。旧応答/指摘/消費枠を保持する。

| パス | bytes | SHA256 |
|---|---:|---|
| evals/skills/routing/production_sdk_trace.py | 59298 | `4ff5fa54eab1f4a63ffea3ddd0fa5eec696865c996bc84fcb77357088f06da1c` |
| evals/skills/routing/production_trace.py | 20872 | `18e5e58331f5420cee0b4047474ee8569775603b7cabd57c24084668fa354aca` |
| tests/skills/test_production_sdk_trace.py | 76929 | `1b32f7af85734b3ebc7a75788da4b204bad7e3f9efd96214a85681bcd13763be` |
| evals/skills/results/2026-10-08-sdk-trace-connection/verify-parent-links.py | 17716 | `9b50f8eb0aba9d76177b2a1eddbd87fc1b527f55415fa0d3565afbf71f45a911` |
| evals/skills/routing/sdk-trace-review-remediation.md | 21708 | `533b71b4c938df6621b7ebf7d5c30e672de5bf1846db5ac968016e0f8c5175b0` |
| tests/skills/test_production_trace.py | 30601 | `80f1037386cd22ebe02c4c78f27141583cd5ed56e199a60113fbd2f44d2dbd4b` |

追加は固定指示・限定条件・source/行番号/hash・公開schema。原RPC/SSE/SDK/telemetry/provider本文・snapshot・保持資料・認証内容・別パス本文を送らない。
共通2段階の依存8パスや新照合器はguardへ固定するだけで、今回の本文に追加しない。
tool/試験/追加モデル/委譲/別ファイル読取りを禁止し、実provider・一次測定・Phase/Step/Gateをこの静的検分で認定しない。
