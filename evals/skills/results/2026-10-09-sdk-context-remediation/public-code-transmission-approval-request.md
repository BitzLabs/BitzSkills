# Phase 4：公開監査コードの今回と以後の送信条件

前回承認されたsource dad596bのreview-06は1回実施し、P2=2を返した。旧枠は消費1/残0。
修正後の新sourceは、同じ6ファイルでも具体的な変更後payloadへの明示承認不足として自動審査で拒否された。
今回は、下記sourceの送信と、Phase 4の同じ6ファイルを修正した際の同じ送信・再検分について確認する。

- 宛先：OpenAI Codex CLI（codex-cli 0.160.1）/ `gpt-6.1-sol`。コードを外部モデルサービスへ送信する。
- 今回source：`220df0dde378cae10ffc7dc917d84cf1bc5f8f1b` の確定Git bytes。
- 目的：同じ公開SDK証拠監査コンポーネントの修正後の独立静的検分。
- 今回契約：`evals/skills/routing/sdk-trace-review-v0.7.json`。
- 各検分の上限：独立CLI起動1回、timeout300秒、一次0、追加委譲0、自動retry0。
- 今回の原保存先：リポジトリ内 `.venv/sdk-trace-independent-review-07`。

| 送信対象（今回と継続対象の固定6パス） | 今回原bytes | 今回SHA256 |
|---|---:|---|
| `evals/skills/routing/production_sdk_trace.py` | 36017 | `4dfb5dd61df755448f9f7143a638c2edf6bc8c12765348dbbc97cdf8cfd2a3c2` |
| `evals/skills/routing/production_trace.py` | 14150 | `b19c0f1808bc4c3d1116eb08b6f39de3e7c3a47d3a196960aede071e4c1cc5f2` |
| `tests/skills/test_production_sdk_trace.py` | 34746 | `b0ea1c31483fcea4901bd1aca59300b609a051bb8e46bbb3c1b95c2b3f432d8e` |
| `evals/skills/results/2026-10-08-sdk-trace-connection/verify-parent-links.py` | 4868 | `d95ed39dea52687f98d248f7aeb10e42e128f46242ab30e4c9737b656acb3eab` |
| `evals/skills/routing/sdk-trace-review-remediation.md` | 5988 | `f8b0212d5c08c8460a72f7da309375ce10b504c5c31272b895a48ea3843fac05` |
| `tests/skills/test_production_trace.py` | 17097 | `381f8b6a1b87fbe32e7fbed71ea7909253fcf94580465b0bc14882fa5654eee3` |

今回の合計112866原bytesに、固定静的検分指示・source ID・行番号/hash・公開JSON応答schema（922 bytes）を追加する。
確認事項は、これらのコード・公開合成テスト・修正履歴の内容と、それらを修正した後の内容がOpenAIへ渡ることである。

継続許可は上表の同じ6パス・同じPhase 4の監査修正・同じ宛先に限定する。
修正後も各回、送信前にコミットを確定し、sourceと各hashを記録・照合する。
別の有限契約と新しい保存先を使い、旧指摘・停止・原証拠・消費枠は保持する。
結果が出た後に指摘を修正した場合だけ次の検分を用意し、失敗を自動retryしない。
対象ファイル追加、宛先変更、一次評価や保持評価資料の送信は、この継続範囲に含めない。

保持評価ケース・期待値の実データ・過去評価の原stdio・認証情報はモデルpayloadへ含めない。
CLI自身の認証だけをread-onlyで接続し、親はその内容を読み取り・コピー・出力しない。
モデルのtool/委譲とrepo/homeの読取りを遮断し、列挙した確定内容だけをstdinで送る。
結果をPhase完了・実provider・一次測定の承認へ拡張しない。

この文書は送信確認用であり、作成しただけでは継続許可を得たことにしない。
