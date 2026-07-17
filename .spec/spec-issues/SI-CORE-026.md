---
id: SI-CORE-026
raised_by: CORE-FR-012 実地確認（2026-07-18 セッション）— accepted_unaddressed 検知の偽陽性として発覚
target: SI-CORE-004/005/006/020/023/024 対応 requirement の origin: フィールド（記録漏れ）
proposed_change_type: modify
status: accepted
---
- **目的**: CORE-FR-012（spec_status.py の accepted 未着手検知）を `--workspace . plugins/*`
  で実地実行したところ、ルート workspace で15件が「未着手の accepted」として検出されたが、
  うち6件（SI-CORE-004 / 005 / 006 / 020 / 023 / 024）は実体照合の結果**実装済み**と確認できた。
  対応する requirement の `origin:` フィールドにこれら spec-issue ID への言及が無いために
  CORE-FR-012 の突合から漏れていた（＝実装漏れではなく記録漏れ）。この記録漏れを解消し、
  検知ノイズを減らす。
  - SI-CORE-004: `plugins/bitz-ddd` / `plugin-creator` / `skill-creator` に `.spec/` が
    新設済み（実体確認済み）。対応 origin 未記載の requirement は無し（reverse-derived 起票が
    無いため、backlink 先の requirement 自体が存在しない可能性がある — 下記「確認観点」で洗い出す）。
  - SI-CORE-005: 5プラグイン全てに discovery 成果物6件ずつ実在確認済み。
  - SI-CORE-006: CORE-CON-001〜007（規約要件7件）は存在確認済みだが、同issue内の
    「裁定（2026-07-13, 人間）」で決定された `env-destroy → env-uninstall` への改名が
    **未実施**（`plugins/bitz-env/skills/` に `env-destroy` のまま存在、`env-uninstall` は
    無し）と実装時に判明。SI-CORE-006 は**部分実装**であり実施マーカーの対象から除外する
    （下記「実施マーカー対象外」参照。口先だけの完了宣言を避けるための訂正）。
  - SI-CORE-020: `plugins/bitz-sdd/skills/sdd-git/references/issue-driven-flow.md` に
    「## 未マージ依存の原則 — 前提を先に land する（SI-CORE-020）」の節が実在確認済み
    （文中に ID 直書きだが、対応する requirement 側 origin には無い）。
  - SI-CORE-023: AGENTS.md の「仕様（.spec）検証の正規コマンド」節に
    「`--workspace . plugins/*` を使う（SI-CORE-023）」の記述が実在確認済み。
  - SI-CORE-024: 全5プラグインに `.codex-plugin/plugin.json` が存在し
    marketplace.json のエントリ数と一致（5件）することを実地確認済み。
- **提案する修正**:
  1. 各 spec-issue（SI-CORE-004/005/006/020/023/024）本文に、bitz-env の軽量レーン運用に
     倣って `- **実施**: <日付> <実装済みの根拠>` 行を追記する（既存の bitz-env 実績パターンを
     ルートへ横展開。CORE-FR-012 は `**実施**:` マーカーを既に「対応済み」判定に使うため、
     これだけで検知ノイズが解消する — 新しいフィールドやスキーマ変更は不要）。
  2. 上記のうち、対応する requirement が既に存在するもの（SI-CORE-020 → 該当する
     sdd-git 関連の requirement があれば、SI-CORE-006 → CORE-CON-001〜007 等）は、
     可能なら requirement 側の `origin:` にも spec-issue ID を追記する（frontmatter の
     メタデータ追記のみ・EARS 節は一切変更しない。`verified`/`promoted` の requirement でも
     安全に実施可能 — 不変条件が禁じるのは EARS 節の書き換えであり frontmatter メタデータでは
     ない）。ただし1の実施マーカーだけで検知目的は達成するため、これは可能な範囲での追加対応
     （必須ではない）と位置付ける。
  3. SI-CORE-004 のように対応する requirement が特定できない（reverse-derived 起票が
     行われていない）ものは、実施マーカーのみで足りるとし、無理に requirement を新規に
     でっち上げない（過剰な後付け文書化を避ける）。
- **対象ファイル**: `.spec/spec-issues/SI-CORE-004.md`, `SI-CORE-005.md`,
  `SI-CORE-020.md`, `SI-CORE-023.md`, `SI-CORE-024.md`（実施マーカー追記。**5件**。
  当初対象だった SI-CORE-006 は部分実装のため実施マーカー対象外に訂正 — 上記「目的」参照）。
  対応 requirement が特定できたものに限り `.spec/requirements/*.md` の `origin:` 行
  （frontmatter のみ）。
- **実施マーカー対象外（訂正）**: SI-CORE-006 は `env-destroy → env-uninstall` 改名が
  未実施のため引き続き `accepted_unaddressed` の対象のまま残す（正確な状態を保つ）。
  改名自体を進めるかどうかは別途人間裁定が必要（本ISSUEのスコープ外）。
- **確認観点**:
  - `spec_status.py --workspace . plugins/*` を再実行し、ルート workspace の
    `accepted_unaddressed` からこの6件が消えていること
  - `spec_inspect.py --workspace . plugins/*` が引き続き PASS すること（EARS 節・スキーマへの
    影響が無いことの機械確認）
  - 実施マーカーに記載する根拠が、実際に本セッションで確認した実体（上記「目的」に列挙）と
    一致していること（口先だけの完了宣言にしない）
- **影響推定・ロールバック**: `.spec/spec-issues/` の本文追記と、任意で `.spec/requirements/`
  の frontmatter 1行追記のみ。コード・スキーマへの影響なし。追記の削除のみで完全に revert 可能。
- **依存**: CORE-FR-012（accepted_unaddressed 検知機能。本ISSUEはその実地運用で発覚した
  記録漏れの後始末）。

## 予備判定（推薦） — 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。frontmatter メタデータ（origin: / 本文の実施マーカー）の追記のみで、対象6件いずれの EARS 節・受入基準も変更しない |
| ガードレール抵触 | なし。既存ファイルへの追記のみ、リポジトリ外書き込みなし |
| 影響範囲 | 限定的。spec-issue 本文6件 + 該当すれば requirement frontmatter 数件のみ |
| 軽量レーン適否 | 適（可）。公開契約・.spec スキーマ・frontmatter 書式のいずれにも触れない、事実の後付け記録に過ぎないため軽量レーンで実施可能 |

**推薦: accept**（根拠: 事実確認済みの実装済み6件について記録を追いつかせるだけの低リスク修正。CORE-FR-012 の実用上のノイズを15件→9件に削減できる）。
最終裁定はユーザー自身の明示指示による `spec_update.py --to accepted --by-human` で行うこと。
- **実施**: 2026-07-18 SI-CORE-004/005/020/023/024 の5件に実施マーカーを追記済み。
  SI-CORE-006 は部分実装（env-destroy→env-uninstall改名が未実施）と判明したため対象外に
  訂正し、`accepted_unaddressed` に正しく残るようにした（上記「実施マーカー対象外」参照）。
