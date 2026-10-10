# Phase 4：固定2セル監査の承認済み公開6パス

[直前の具体的な6パスと継続送信の許可回答](../2026-10-10-sdk-yielded-parent/public-code-transmission-approval-evidence.md)に基づく。
ユーザーは監査側公開6ファイルをOpenAI/gpt-6.1-solへ各修正版1回の静的検分として継続送信する具体的質問に「許可します」と回答した。
同6パスのsource `1d72e209691a06c81c3e53cc82468165f7fe2f81` の本文202879 bytesを有限v0.22で初回1回送信し、自動承認審査を通過した。
独立1回/最大300秒、一次・追加委譲・自動retry0。旧原結果と消費枠を保持する。

| パス | bytes | SHA256 |
|---|---:|---|
| evals/skills/routing/production_sdk_trace.py | 49995 | `58e175f78c231df7aa2dac51d7756b899d5e0197cfcd703a5ede6580ef0304b1` |
| evals/skills/routing/production_trace.py | 20872 | `18e5e58331f5420cee0b4047474ee8569775603b7cabd57c24084668fa354aca` |
| tests/skills/test_production_sdk_trace.py | 66142 | `ab1b62dc502a62031d973bb0c5a8c9a0e97b91371e7f30763b06e783e8dffbd3` |
| evals/skills/results/2026-10-08-sdk-trace-connection/verify-parent-links.py | 15306 | `4f7f3d888e00a5512d2a274fbb7ce051dd68228d8be6199c049da9f31c459e09` |
| evals/skills/routing/sdk-trace-review-remediation.md | 19963 | `2cd2da85d35902ebf5e56394fd279f1414a5051573386412510a083b707ff43f` |
| tests/skills/test_production_trace.py | 30601 | `80f1037386cd22ebe02c4c78f27141583cd5ed56e199a60113fbd2f44d2dbd4b` |

追加は固定指示・限定条件・source/行番号/hash・公開schema。原RPC/SSE/SDK/telemetry/provider本文・snapshot・保持資料・認証内容・別パス本文を送らない。
新2exec捕捉側の照合器はguardへ固定するだけで、本文を送信しない。tool/試験/追加モデル/委譲/別ファイル読取りを禁止する。
実provider・任意複数セル・一次測定・Phase/Step/Gateをこの静的検分で認定しない。
