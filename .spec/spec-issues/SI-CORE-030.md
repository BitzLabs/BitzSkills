---
id: SI-CORE-030
raised_by: 標準環境ビジョン反映時の docs_inspect 実行
target: docs/ 構造と sdd-docs docs_inspect の適用境界
proposed_change_type: modify
status: open
---
- **目的**: ルート `docs/` は使い方ガイド・過去計画・3プラットフォーム調査・外部資料保全を含む
  大規模資料庫として運用されている一方、`sdd-docs` の `docs_inspect.py` は `docs/` 全体を
  SDDテンプレート管理下（全Markdownにfrontmatter、MASTER.mdへの登録必須）とみなす。
  標準環境ビジョンの同期後に正規検査を試すと exit 1、合計1,557件
  （FM_ABSENT 211、FM_MISSING 1,001、その他ERROR 6、REG_ORPHAN 338、
  PT_MASTER_MISSING 1）となり、文書層の健全性を判定できない。この適用境界を明文化・機械化する。
- **提案する修正**:
  1. `docs/` のうちSDDナラティブとして管理する範囲と、調査資料・保全資料・過去計画として
     docs_inspect対象外にする範囲を設計する。
  2. `docs/MASTER.md` の導入、検査除外設定、資料の別ルート移動のいずれか、または組合せを
     Design Gateで選ぶ。除外を採る場合は黙示的なハードコードではなく、リポジトリ側で監査可能な
     設定として宣言する。
  3. 管理対象の `docs/01-context/` と入口文書について、必要frontmatter・レジストリ・同期契約を整える。
  4. `docs_inspect.py . --strict` の期待結果と、調査報告を破壊・大量改変しない回帰テストを追加する。
- **対象ファイル**: ルート `docs/` の管理構造、`docs/MASTER.md`（候補）、
  `plugins/bitz-sdd/skills/sdd-docs/scripts/docs_inspect.py` とテスト（ツール改修を採る場合）、
  `.spec/discovery/` から同期される `docs/01-context/`。
- **確認観点**:
  - 既存要件との矛盾: なし。sdd-docsの双方向同期を実用化し、標準環境の文書層を検証可能にする補完。
  - ガードレール: 調査報告や既存成果物を一括削除・上書きしない。大量frontmatter付与を機械的に
    実施する場合も、人間がdiffを確認できる粒度に分割する。
  - 検証: `docs_inspect.py` の対象範囲が明示され、管理対象のERROR 0。`release_check.py`、
    `spec inspect --workspace . plugins/*`、pytestもgreenを維持する。
  - 軽量レーン適否: **不適**。docs管理契約と、場合によってはsdd-docsツールの公開挙動を変更するため、
    通常フロー + Design Gateを推奨する。
- **影響推定・ロールバック**: 現時点はopen issueの追加のみ。実装時は文書パス・同期・検査対象へ
  広く影響する。ロールバックは設定／MASTER／ツール変更をPR単位で戻し、既存資料の配置を維持する。
- **依存**: CORE-DSC-001〜006（標準環境ビジョンと文書層の位置づけ）、sdd-docsの同期契約。
- **予備判定（推薦）**: **accept 推薦**。標準環境のSSOTを `.spec` としながら、対応する人間向け
  docsを正規検査できない状態は継続的なドリフト検出を妨げる。ただし既存資料が大規模なため、
  直ちに一括修正せず、適用境界の設計を先行する。裁定は人間専用で、本issueは `open` のままとする。
