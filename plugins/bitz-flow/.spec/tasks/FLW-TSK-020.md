---
implements: FLW-NFR-001
depends_on: FLW-TSK-012
boundary: evals/flow-core/fixtures/v2-skill/SKILL.md
status: done
---

### SI-FLW-016 の裁定に基づき v2 SKILL.md へパス解決手順を追加する

- **作業内容**: `SI-FLW-016` の裁定（accept・案1＋案2 併用）に基づき、Mandatory entry protocol
  の項1へ4行を追加する（裁定記録
  `.spec/reports/decision-2026-08-07-si-flw-016-path-resolution.md`）。

  | 追加要素 | 役割 |
  |---|---|
  | `<このスキル>` は本 SKILL.md が置かれたディレクトリである | プレースホルダの定義を明示 |
  | 「推測で書かず、実行前に一度だけ場所を確かめる」 | 推測を禁じ**代替を与える** |
  | `find . -maxdepth 6 -path '*/flow-core/scripts/flow.py' 2>/dev/null \| head -1` | 具体手順 |
  | 「**`find /` を実行してはならない**」＋見つからなければ停止・報告 | 最悪の手段を塞ぎ着地点を定義 |

  `-maxdepth 6` は必須である（`.claude/skills/flow-core/scripts/flow.py` は深さ 5）。
  当初 4 で検討したが実測で届かず 6 へ確定した。cwd 配下を深さ限定で探す形にしたため、
  `.claude/` / `.agents/` を列挙せずに済み `CORE-CON-012` の前提と衝突しない。

- **完了条件**: 3 platform の再実測で次を満たすこと。
  1. `find /` の実行が **0 件**になること
  2. **raw fallback が 0 件へ戻ること**（M0 出口条件）
  3. **claude が探索的な操作を経てからパスを組み立てること**（数値ではなく挙動での確認）
  4. codex-cli / antigravity の既達水準を落とさないこと

- **検証結果**: 探索コマンドの所要時間を実測した。

  | 条件 | 所要時間 | 結果 |
  |---|---|---|
  | corpus repo | 0.00s | `./.claude/skills/flow-core/scripts/flow.py` |
  | リポジトリ本体（大きなツリー） | 0.00s | 同上 |

  第10ラウンド（2026-08-07。3 platform 同一 fixture）で完了条件を確認した。

  | 完了条件 | 第8R | 第10R | 判定 |
  |---|---|---|---|
  | 1. `find /` の実行 0 件 | claude 2 件 | claude 0 / codex 0 / agy 0 | ✅ |
  | 2. パス解決に由来する raw fallback 0 件 | 1 件 | 0 件 | ✅ |
  | 3. claude が探索を経てからパスを組む | 0/30 | **29/30** | ✅ |
  | 4. codex / agy の非退行 | bypass 0 / raw fb 0 | bypass 0 / raw fb 0 | ✅ |

  条件3が最も直接的な証拠である。第8ラウンドでは claude の v2 30 trial すべてが
  推測でパスを書いていたのに対し、第10ラウンドでは 29 trial が最初の bash 実行として
  `find . -maxdepth 6 -path '*/flow-core/scripts/flow.py'` を発行し、
  その出力から実パスを組み立てている。残り1 trial は**そもそもスキルを読み込んでいない**
  ため本タスクの対象外である（別途 `SI-FLW-018` として起票）。
  agy も同じ探索コマンドを採用しており、turn の浪費や退行は観測されなかった。

  なお `find /` の grep は SKILL.md 本文の禁止文（「**`find /` を実行してはならない**」）に
  一致するため、**実行されたコマンドだけを数える**必要がある。文字列一致では
  claude 29 件・codex 48 件が出るが、いずれも本文の引用であり実行は 0 件である。

- **備考**: 追加は4行で `FLW-DSN-010`（文章を長くしない）の制約内。`SI-FLW-013` では逆に
  文章を減らしたが、本件は**代替手段を与えないと禁止が機能しない**ため最小限の追加とした。
  配布側 `plugins/bitz-flow/skills/flow-core/SKILL.md` は変更しない（Promotion Gate で反映）。
  ただし本欠陥は claude のネイティブなスキル読み込みでは実運用でも起きる。
  本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
