# Phase 4：公開canary統合設計の送信許可範囲

状態：2026-10-10に本人がPhase 4の検証期間中の送信を明示許可済み。以下は提示時の範囲と停止の歴史記録。
現在の許可・初回実結果は `phase-4-transmission-approval-evidence.md` を参照する。
確定source：`747c4988536fa61af1e91f9e30853e4ad4de58e6`。
宛先：OpenAI、モデル：`gpt-6.1-sol`。目的：実provider公開canaryと一次台帳の静的設計検分。
この6パスは前回の監査側6パス・捕捉側8パスと異なる。前回の具体的承認を転用しない。

## 送信する公開本文

全て `evals/skills/routing/` 配下。現refの本文合計89,977 bytes。

| ファイル | bytes | SHA-256 |
|---|---:|---|
| production-canary-integration-design.md | 8339 | c11c7bb28787f1e0551e0adff2b3c1e3a6de660e676f15418142c21c561d2fc6 |
| production_ledger.py | 11431 | f3b5306284babf5d6adf3ee34b44a7250f33f3818a82733d706b6c63c940e929 |
| production_sdk_probe.py | 16846 | 29b0d201bdca9796c9fcbcc6c2b5de282dd9bfc2a579ea7d430d0efa15fb11ae |
| production_cli_probe.py | 14738 | cc64e4fdff0612e0e72072b88b78993e6128a63d0df7aa890b55e939e6757fe7 |
| production_trace.py | 20872 | 18e5e58331f5420cee0b4047474ee8569775603b7cabd57c24084668fa354aca |
| run_sdk_trace_review.py | 17751 | 278a26dfa1a704504b998718e7f664ce65828de29ae59a3fbc358d52adccd3f1 |

固定scope/source/行番号/hash/schemaと検分条件を添付する。原捕捉・原ログ・保持入力・期待値・認証内容・別パス本文は送らない。
公開本文も外部のモデル提供者へ移転するため、この具体的範囲の本人許可を確認する。

## 求める承認

上記6公開パスをOpenAI/gpt-6.1-solへ静的設計検分として送信すること。
現在のv0.24は1回・300秒。指摘への修正後も同6パス・同宛先だけ、各確定refに新しい有限契約を用意し1回ずつ継続する。
各回のbytes/hash・消費回数と停止を記録し、前回結果を保持する。追加パスや一次評価への承認として扱わない。
自動retry・委譲・追加モデル起動0、一次モデル軌跡0。ここで将来案の一次4/独立一次検分4を起動しない。

## 自動承認の停止記録

2026-10-10、`--canary-design-review` の昇格要求がprocess作成前に拒否された。
理由：内部コード89,977 bytesのOpenAIへの外部移転であり、SOL評価全般の許可では具体的6ファイルと宛先の承認を満たさない。
別経路・別モデル・間接起動を行わず、`.venv/sdk-trace-independent-review-24` が未作成と確認した。
この文書自体は承認ではない。本人の回答を受けてから送信する。
