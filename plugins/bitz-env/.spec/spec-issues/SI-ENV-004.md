---
id: SI-ENV-004
raised_by: sdd-review REV-001（business BIZ-201）
target: plugins/bitz-env/.spec/requirements/（NFR 新規）
proposed_change_type: new
status: accepted
---
- **矛盾/曖昧の内容**: 非機能要件(NFR)が1件も無い。env_guard は全 Bash 実行に PreToolUse で
  割り込むため、応答が遅ければ開発体験を直接損なう。SessionStart の注入サイズにも上限が無い。
  定量目標が無いと「遅い/過大」の判定基準を持てず、公開ツールとして品質保証が弱い。
- **提案する修正**: 最小限の NFR を起票（重い指標 p99 等は不要）。例:
  (a) ENV-NFR-001: env_guard は1呼び出し当たり通常環境で 200ms 以内に応答する（体感を損なわない）。
  (b) ENV-NFR-002: SessionStart の rules 注入は rules/*.md の合計を対象とし、過大注入を避ける
      （肥大時の上限や要約方針）。
  検証手段は benchmark または manual-check。
- **影響推定**: 要件ファイル 1〜2件の新規追加（ENV-NFR-*）。domains.md の統制語彙は据え置きで足りる。
  既存 FR/CON への影響なし。実装は現状が満たしている見込みで、計測で確認する。
