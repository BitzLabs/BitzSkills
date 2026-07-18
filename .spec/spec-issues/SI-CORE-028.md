---
id: SI-CORE-028
raised_by: ユーザー要望（CORE-CON-008 起票中に追加提起、2026-07-18）
target: plugin-creator の update 標準契約（CORE-CON-008）へのバージョン移行機構
proposed_change_type: modify
status: accepted
---
- **目的**: CORE-CON-008 で定義中の標準スキル `<plugin名>:update` の最小契約は現状
  「バージョン更新と依存再確認」のみで、プラグイン自身が保持する状態（`.spec` 系
  frontmatter・配置先の `metadata` スキーマ・`.claude/<plugin>.local.md` 等の設定ファイル）が
  旧バージョンの形式のまま残るケースを救済しない。バージョンが上がるたびに必要な変換を
  「積み重ね（累積）」構成のマイグレーションステップとして定義し、`update` がインストール先の
  現在バージョンから最新バージョンまで**中間バージョンを順次経由**して適用できるようにし、
  古いバージョンで導入されたプラグインもできるだけ最新バージョンで使い続けられるようにする。
- **提案する修正**:
  1. plugin-creator の `update` reference に、バージョン単位のマイグレーションステップを
     蓄積する規約を追加する（例: `references/migrations/<from>-to-<to>.md` または
     `migrations.yaml` にステップを列挙し、`update` 実行時に配置先 `metadata.version` から
     ライブラリ側 `metadata.version` までの経路を解決して**順番に**適用する）。
  2. 各マイグレーションステップの最小契約を定める: 対象バージョン範囲（from/to）・
     やること（変換内容）・冪等性（同じステップを二重適用しても壊れないこと）・
     失敗時のロールバック手順。
  3. skill-packager の「バージョンアップ時の安全判定」
     （`plugins/skill-creator/skills/skill-packager/references/lifecycle.md`）との関係を整理する
     — skill-packager はスキルファイル自体の**置き換え可否判定**を担い、本 ISSUE は
     置き換え後 or 置き換えに伴って必要になる**状態・設定側の変換**を担う。責務境界を
     明文化し、二重規定を避ける。
  4. 中間バージョンが欠落している（マイグレーションステップが定義されていない版がある）場合の
     挙動を定める（安全側: 変換不能として停止しユーザーに提示。無視して先に進めない）。
- **対象ファイル**: `plugins/plugin-creator/skills/plugin-structure/references/`（update 標準
  reference の新規または追記）、`.spec/requirements/CORE-CON-008.md`（受入基準への追記 or
  別要件として分離するかは要件化時に判断）、`plugins/skill-creator/skills/skill-packager/references/lifecycle.md`
  （責務境界の追記）。
- **確認観点**:
  - release_check / spec_inspect PASS
  - マイグレーション未定義の中間バージョンがある場合に `update` が安全側（停止+提示）で
    止まることを確認できること
  - 累積ステップの冪等性（同一ステップの二重適用でファイルが壊れないこと）を確認できること
- **影響推定・ロールバック**: plugin-creator の reference 追加と CORE-CON-008 の受入基準拡張が
  中心で、既存プラグインの動作は変更しない（機構の追加のみ）。単独 revert 可能。ただし
  マイグレーション機構は**契約（`.spec` スキーマ・frontmatter 書式）に触れる**ため軽量レーン
  ではなく通常フロー + Design Gate が必要（sdd-core の軽量レーン除外条件に該当）。
- **依存**: SI-CORE-006（CORE-CON-008。update 標準の土台）。CORE-CON-008 が承認される前提での
  拡張のため、CORE-CON-008 の受入基準に含めるか、承認後の別要件として追うかは人間裁定が必要。
- **実施**: 2026-07-18 CORE-CON-009 として要件化し verified 到達（DSN-002 approved・CORE-TSK-015 done。plugin-creator の migration-steps.md 新設と skill-packager lifecycle.md の責務境界追記）
- **予備判定（sdd-issue 推薦）**: **accept 推薦（条件付き）**。
  - 既存要件との矛盾: なし。CORE-CON-008 はまだ draft で `update` の最小契約を「バージョン更新と
    依存再確認」とのみ定めており、本提案はその具体化・拡張であり矛盾しない。
    `spec_inspect --impact CORE-CON-008` は依存成果物0件（未実装のため衝突リスクなし）。
  - ガードレール抵触: なし。ただしマイグレーション適用先が「配置先」（リポジトリ外の
    `~/.claude/skills/` 等）になる場合は AGENTS.md の「リポジトリ外への書き込みは事前確認」に
    該当するため、実装時に確認フローを組み込む必要がある。
  - 影響範囲: plugin-creator（標準定義）と、将来的に `update` を実装する各プラグイン
    （bitz-env 等）。現時点で `update` の実装がまだ無いため影響は限定的。
  - 軽量レーン適否: **不可**（`.spec` スキーマ／frontmatter 書式という契約に触れるため通常フロー
    + Design Gate が必要）。
  - 条件: CORE-CON-008 の承認前に本 ISSUE も合わせて裁定し、範囲を「CORE-CON-008 に統合するか
    別要件 CORE-CON-009 として独立させるか」を人間が決めることを推奨する
    （本 ISSUE 単体では設計の骨子提案までで、詳細設計は sdd-design のスコープ）。
