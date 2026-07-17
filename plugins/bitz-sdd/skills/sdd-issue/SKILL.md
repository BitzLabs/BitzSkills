---
name: sdd-issue
description: BitzSDD — ばらばらに届く要望・不具合報告・改善アイデアを整理し、可否の予備判定（推薦）を付けて .spec/spec-issues/ に起票するインテークスキル。1要望 = 1 spec-issue への分割、既存 spec-issue・要件との重複チェック、影響範囲分析、委託先ワークスペース判定、spec_scaffold.py による採番・起票、裁定材料の提示までを定型化する。ユーザーが「この要望を整理して」「spec-issue にして」「起票して」「インテーク」「要望がいくつかある」と言及したとき、または作業中に仕様変更が必要だと気づいて起票が必要になったときに使用する。裁定（accepted / rejected 化）は人間専用で本スキルは行わない。要件のライフサイクル・規律の正は sdd-core が担当する。
metadata:
  version: "0.1.1"
  author: br7.hide
  created: "2026-07-16"
  updated: "2026-07-18"
---

# sdd-issue

ばらばらに届く要望を定型フローで整理し、**可否の予備判定（＝推薦）を添えて** spec-issue に
登録するインテークスキルです。

## 権限分離（最重要）

- 本スキルが行うのは**予備判定と推薦まで**。spec-issue は**常に `status: open` で起票**する。
- `open → accepted / rejected` の**裁定は人間のみ**（sdd-core 憲法4「仕様の変更権は常に人間が持つ」）。
  エージェントが sdd-core の `spec_update.py` で裁定を試みても `--by-human` 強制で拒否される。
- 本文に書く「可否の判定」は**推薦**であり、裁定ではない。提示の際もそのように表現する。
- 規律・ライフサイクル・番号管理の**正は sdd-core** のまま。本スキルはその上のインテーク運用
  フローだけを担い、ライフサイクル規則を再定義しない。

## インテークフロー

1. **要望の整理**: 持ち込まれた要望を **1要望 = 1 spec-issue** に分割する。分割原則:
   小さな変更量 / 動作変更と構造変更を混ぜない / テスト追加が先 /
   後の issue ほど前の issue に依存させる（＝逆順 revert で安全にロールバック可能）。

2. **重複チェック**: sdd-core の `spec_status.py --json` で既存 spec-issue・要件の一覧を取得し、
   同じ対象・同じ目的の起票が無いか突合する。重複していたら新規起票せず既存 ID を提示する。
   （集計ロジックを自前実装しない — 機械集計は常に `spec_status.py` 側）

3. **可否の予備判定**: 以下の判定軸で accept / reject の推薦を組み立てる。

   | 判定軸 | 確認方法 |
   |---|---|
   | 既存要件との矛盾 | 対象領域の requirements/ を確認（矛盾があれば supersedes 候補として明示） |
   | ガードレール抵触 | AGENTS.md 等の禁止事項・事前確認事項に触れないか |
   | 影響範囲 | sdd-core の `spec_inspect.py --impact <関連要件ID>` で影響成果物を列挙 |
   | 軽量レーン適否 | 契約（公開 API・`.spec` スキーマ・frontmatter 書式)に触れるなら通常フロー + Design Gate、触れないなら軽量レーン可 |

4. **委託先ワークスペース判定**（モノリポの場合）: 変更が単一パッケージに閉じるならそのサブ
   ワークスペース、共通規約・複数パッケージに跨るならルートの `.spec/` に起票する。
   委託関係が生じる場合は frontmatter の `origin:` / `delegated_to:` に双方向の対応を記録する
   （委託フローの正は sdd-core の lifecycle.md。未規定の項目は本文の自由記述で補う）。

5. **採番・起票**: sdd-core の `spec_scaffold.py` で起票する（手書きしない — 書式・採番衝突を構造的に防ぐ）。

   ```bash
   python3 <sdd-core スキル>/scripts/spec_scaffold.py <workspace> spec-issue \
     --prefix <SI-プレフィックス> --target "<変更対象>" --raised-by "<発見元>" --change-type <new|modify|bump|deprecate>
   ```

   雛形生成後、本文に目的・提案する修正・対象ファイル・確認観点・影響推定とロールバック・依存を記入する。

6. **裁定材料の提示**: 起票した spec-issue の本文に **accept / reject の推薦と根拠**（判定軸ごとの
   結果）を記載し、人間へ「裁定待ち」として一覧提示する。裁定の実行はユーザー自身または
   ユーザーの明示指示による `spec_update.py --to accepted --by-human` で行う。

7. **完了記録**: spec-issue が実際に実装された時点（軽量レーンでの直接反映、または要件化パス
   で対応する requirement が `verified` に達した時点）で、当該 spec-issue 本文に
   `- **実施**: <日付> <根拠>` を追記する。語彙は `**実施**:` に統一し、「実装完了」等の
   類義語は使わない（表記ゆれは CORE-FR-012 の完了検知を取りこぼす原因になる。語彙統一・
   `origin:` との関係は sdd-core の `lifecycle.md` を参照）。

## 後続工程

- accepted になった spec-issue は、軽量レーン（sdd-core）または要件化（draft 起票 → 人間 approve）
  を経て sdd-implement のタスク分解へ進む。実装完了後は手順7の完了記録を必ず行う。
- 「いま裁定待ちの spec-issue は何か」の照会は sdd-plan が担当する。

## してはいけないこと

- `status: open` 以外での起票、および本スキルからの accepted / rejected 化（裁定は人間専用）
- spec_scaffold.py を使わない手書き起票（採番衝突・書式ブレの原因）
- 複数の関心事を1つの spec-issue に束ねること（1要望 = 1 spec-issue）
