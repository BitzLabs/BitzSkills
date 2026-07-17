---
id: SI-CORE-027
raised_by: CORE-FR-012 実地確認（2026-07-18 セッション）— accepted_unaddressed 検知で発覚
target: .spec/spec-issues/SI-CORE-019.md（status: accepted のまま SI-CORE-023 と重複放置）
proposed_change_type: deprecate
status: accepted
---
- **目的**: SI-CORE-019 と SI-CORE-023 は、対象・目的が完全に一致する重複 issue である
  （どちらも「`spec_inspect.py` をリポジトリルート単体で実行すると `tests/test_env_guard.py`
  由来の `ENV-*` 参照が幽霊参照として偽陽性検出される」問題）。SI-CORE-023 の提案2
  （正規コマンドを `--workspace . plugins/*` と定め AGENTS.md に明記）が実際に採用され、
  AGENTS.md「仕様（.spec）検証の正規コマンド」節に反映・実装済みであることを確認した。
  一方 SI-CORE-019 は `status: accepted` のまま重複が未整理で残っており、CORE-FR-012 の
  「未着手の accepted」検知に毎回ノイズとして現れ続けている。この重複を解消する。
- **提案する修正（訂正版 — 実装時に判明した制約を反映）**:
  1. ~~SI-CORE-019 の status を `deprecated` へ遷移~~ → **実施不可と判明**。
     `spec_update.py` の権限マトリクスに `spec-issue` の `accepted → deprecated` 遷移は
     定義されていない（`deprecated` は `requirement` 専用の語彙であり、spec-issue の遷移は
     `open → accepted / rejected` のみ）。実行時に機械的に不正遷移として拒否されたため、
     `status: accepted` のまま留め置く方針に変更する。
  2. 代わりに、SI-CORE-019 frontmatter に `superseded_by: SI-CORE-023` を自由記述的に追記し、
     本文に `**実施**:` マーカー（CORE-FR-012 が検知する完了マーカー）で
     「SI-CORE-023 での実装をもって解決済みとみなす」旨を記録する
     （`status` を変えずとも CORE-FR-012 の検知からは正しく除外される）。
  3. SI-CORE-023 側にも `**実施**:` マーカーを追記し、AGENTS.md への正規コマンド明記が
     完了していることと、SI-CORE-019 との重複統合を記録する（SI-CORE-026 と同様の
     記録漏れ解消を兼ねる）。
- **対象ファイル**: `.spec/spec-issues/SI-CORE-019.md`（frontmatter への `superseded_by:` 追記
  + 実施マーカー追記。status は変更しない）、`.spec/spec-issues/SI-CORE-023.md`（実施マーカー追記）。
- **確認観点**:
  - `spec_status.py --workspace . plugins/*` の集計で、ルート workspace の
    `accepted_unaddressed` から SI-CORE-019 / SI-CORE-023 の両方が消えること
    （spec-issue の総数・status 内訳自体は変わらない — 019 は `accepted` のまま）
  - `spec_inspect.py --workspace . plugins/*` が引き続き PASS すること
  - 存在しない遷移をエージェントが独断で強行しないこと（機械的拒否を尊重し、
    代替手段に訂正した経緯を本文に残すこと）
- **影響推定・ロールバック**: spec-issue 2件の frontmatter/本文編集のみ。status 変更を伴わない
  ため revert は追記の削除のみで完了する。
- **依存**: SI-CORE-023（実装済みで置き換え先となる issue）。CORE-FR-012（本重複を
  実地運用で検出した検知機能）。

## 予備判定（推薦） — 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。status 遷移とテキスト追記のみ |
| ガードレール抵触 | なし |
| 影響範囲 | 限定的。spec-issue 2件のみ |
| 軽量レーン適否 | 適（可）。ただし `accepted → deprecated` 遷移自体が元々人間専用権限（spec_update.py の権限マトリクス） |

**推薦: accept**（根拠: 内容が完全一致する重複の整理であり、実害はノイズ発生のみ。実装は既に SI-CORE-023 側で完了済みのため、019 を残す理由がない）。
最終裁定はユーザー自身の明示指示による `spec_update.py --to accepted --by-human` で行うこと。
- **実施**: 2026-07-18 SI-CORE-019 に `superseded_by: SI-CORE-023` と実施マーカーを追記、
  SI-CORE-023 側にも統合の実施マーカーを追記済み。当初案の `deprecated` 遷移は spec-issue の
  権限マトリクスに存在せず機械的に拒否されたため、status は `accepted` のまま維持する方式に
  訂正して実施した。
