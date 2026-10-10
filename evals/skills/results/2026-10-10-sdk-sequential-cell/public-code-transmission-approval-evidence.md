# Phase 4：固定2exec捕捉の承認済み公開8パス

[前回の具体的な8公開パスの継続承認](../2026-10-10-sdk-yielded-cell/public-code-transmission-approval-evidence.md)に基づく。
ユーザーは公開8本文をOpenAIのgpt-6.1-solへ各修正版1回の静的検分として継続送信する具体的質問に「許可します」と回答した。
同8パスの修正版source af35d0b7c9c9c1c6e1e69c76799e72efbecbbd81 の127003 bytesを、有限v0.7で初回1回送信し、自動承認審査を通過した。
原07のP2=2/原応答/消費枠を保持し、新有限v0.8では同8パスの是正版を各確定ref1回送る。
新契約v0.9/v0.10・新照合器の本文はguardに固定するだけで送信しない。

送信パスはproduction_operation_probe.py、test_production_operation_probe.py、production-operation-probe-v0.7/v0.8.json、
production_sdk_probe.py、production_cli_probe.py、source_guard.pyと2026-10-09-sdk-raw-response-capture/verify-artifacts.pyのみ。
追加は固定指示・限定条件・source/行番号/hash・公開schema。原RPC/SSE/SDK/telemetry/保持入力/snapshot/認証内容を送らない。
宛先はOpenAI/gpt-6.1-sol、最大300秒、独立1回、一次0・追加委譲0・自動retry0。tool/試験/別ファイル読取りも禁止する。
複数セル相関全般・実provider・一次測定・Phase/Gateの認定をこの静的検分へ代用しない。
