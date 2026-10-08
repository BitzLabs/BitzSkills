# Phase 4：公開コードの独立SOL再検分で送信する内容

自動承認審査がコード送信の明示承認不足として拒否したため、以下の具体的な1回の送信を確認する。
SOL評価全般の継続承認はあるが、拒否された送信は未実行である。

- 宛先：OpenAI Codex CLI（codex-cli 0.160.1）の `gpt-6.1-sol`。外部のモデルサービスへ送信する。
- 目的：SDK証拠監査器の修正後の独立静的検分。主にreview-04のP2が再現しないか確認する。
- source：`f62a87a6181831f87cd24de72c843588869dd736`。下表の確定Git bytesを使用する。
- 上限：独立SOL最大1回、timeout300秒、一次モデル測定0、追加委譲0、自動retry0。
- 契約：`evals/skills/routing/sdk-trace-review-v0.5.json`。
- 保存先：リポジトリ内 `.venv/sdk-trace-independent-review-05`。prompt/schema/stdio/原応答/予約/receiptを保存する。

| 送信ファイル | 原bytes | SHA256 |
|---|---:|---|
| `evals/skills/routing/production_sdk_trace.py` | 35036 | `f8e0e0834b41e5406021aeea746ebf7cb1dc8907012f9b24e9d1ff08ed321dc9` |
| `evals/skills/routing/production_trace.py` | 13298 | `2227bf73b6ca1e76831afa70a39ff8d380a084169575f82a97bec0e3bbcb4642` |
| `tests/skills/test_production_sdk_trace.py` | 29486 | `328a5fa1ca7d93c87770f244df9e5f6ae7b96f207bcaa27f8db54d3122a17832` |
| `evals/skills/results/2026-10-08-sdk-trace-connection/verify-parent-links.py` | 4868 | `7aa6aae048eeed5a1eaf9754537624cc99b1e7e19f3895fc382cbb95402a6555` |
| `evals/skills/routing/sdk-trace-review-remediation.md` | 3831 | `a85c7c3f7bebf088ffe84d2761596c5059af108d30f83eead249b60aebf1fa81` |

合計86519原bytesに行番号、source ID、hash、固定静的検分指示と公開JSON応答schema（922 bytes）を追加する。
コード・テスト・修正履歴の内容が外部サービスへ渡る点が確認事項である。
保持評価ケース・期待値の実データ・過去の評価原stdio・認証情報はモデルpayloadへ含めない。
CLI自身の既存認証をread-onlyで接続するが、親はその内容を読み取り・コピー・出力しない。
モデルにはtoolや委譲を許可せず、repo/homeの読取りを遮断し、stdinの列挙した確定内容だけを渡す。

この承認は上記5ファイルの独立静的検分1回への送信を対象とする。
結果をPhase完了・実provider・一次測定の承認へ拡張しない。
