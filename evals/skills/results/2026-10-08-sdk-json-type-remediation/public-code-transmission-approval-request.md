# Phase 4：JSON型是正後の公開コードを送る条件

直前の承認を受けたreview-05は1回実行し、P2=1/P3=1を返した。旧枠は消費1/残0。
その後の修正版は、新sourceと追加回帰テストの具体的payloadへの明示承認不足として自動審査で拒否された。
今回は以下の6ファイルを外部サービスへ送る別有限1回を確認する。

- 宛先：OpenAI Codex CLI（codex-cli 0.160.1）/ `gpt-6.1-sol`。
- source：`dad596b2034bbcd0abb4cd25c19aea78143aa5a3` の確定Git bytes。
- 目的：JSON型置換の修正後の独立静的検分。実モデル一次測定をしない。
- 契約：`evals/skills/routing/sdk-trace-review-v0.6.json`。
- 上限：独立1回、timeout300秒、一次0、委譲0、自動retry0。
- 原保存先：リポジトリ内 `.venv/sdk-trace-independent-review-06`。

| 送信対象 | 原bytes | SHA256 |
|---|---:|---|
| `evals/skills/routing/production_sdk_trace.py` | 35645 | `2ba2313cf875c021efaef5db445f586f212d73ae318dc75637b92c0f7dec2564` |
| `evals/skills/routing/production_trace.py` | 13733 | `4e24f801e049362167abb448a3607826c739bb8b43586e5ea1f24c68d0324535` |
| `tests/skills/test_production_sdk_trace.py` | 33407 | `d16d918f71ac2476b6c45a11d4bdee6ccfd5ab02704d0d011f8a540b089f50d2` |
| `evals/skills/results/2026-10-08-sdk-trace-connection/verify-parent-links.py` | 4868 | `9e4ebd5d0de79b759babfc60c3e3092afe3b45ffb2e81811dc47ea42ba8def6b` |
| `evals/skills/routing/sdk-trace-review-remediation.md` | 5083 | `512dd7853b1d84e42ff429cd53bc3c5abe6226497c22f3dc1cb62050ffb407bb` |
| `tests/skills/test_production_trace.py`（追加） | 16171 | `15ed0c37f0a567c0ba647ed55b2013dedebbb9d7922b3742b0221d166b87f08d` |

合計108907原bytesに、固定検分指示・source ID・行番号/hash・公開JSON応答schema（922 bytes）を追加する。
確認事項は、上記のコード・テスト・修正履歴の内容がOpenAIの外部モデルサービスへ渡ることである。
保持評価ケース・期待値の実データ・過去評価の原stdio・認証情報はモデルpayloadへ含めない。
CLI自身の既存認証だけをread-onlyで接続し、親は内容を読み取り・コピー・出力しない。
モデルのtool/委譲とrepo/homeの読取りを遮断し、列挙した確定内容だけをstdinで渡す。

今回の承認対象は、上記6ファイルの独立静的検分1回への送信である。
結果をPhase完了・実provider・一次測定の承認へ拡張しない。
