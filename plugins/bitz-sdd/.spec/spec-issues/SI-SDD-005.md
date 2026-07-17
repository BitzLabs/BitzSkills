---
id: SI-SDD-005
raised_by: CORE-FR-012（accepted未着手検知）の実地運用で発覚した記録漏れ・表記ゆれ・重複放置の再発防止（2026-07-18 セッション）
target: plugins/bitz-sdd/skills/sdd-core/references/lifecycle.md + skills/sdd-issue/SKILL.md（完了記録ステップの不在）
proposed_change_type: modify
status: open
---
- **目的**: 2026-07-18 セッションで CORE-FR-012（accepted 未着手検知）を実地運用した結果、
  ルート15件・bitz-env6件が「未着手」として検出されたが、実体照合すると大半（12件）は
  実装済みで、記録漏れが原因と判明した（SI-CORE-026 / SI-ENV-022 で個別修復。加えて
  SI-CORE-019/023 の重複放置を SI-CORE-027 で発見・統合）。この個別修復は対症療法であり、
  根本原因（完了記録の運用が制度化されていない）を放置すると同じノイズが再発する。
  4つの根本原因を解消する:
  1. **完了記録が制度化されていない**: 「実施」マーカーは bitz-env が2026-07-12に自然発生的に
     始めた慣習で、`sdd-issue`/`sdd-core` のどこにも明文化されていない。同日裁定の13件中6件
     （SI-ENV-002/005/007/008/011/014）に付け忘れが発生し、ルート workspace は当時0件
     （運用自体が存在しなかった）。
  2. **表記ゆれ**: SI-CORE-012/020 は「実施」ではなく「実装完了」という別語彙を使用しており、
     CORE-FR-012 の検知（`**実施**:` 固定パターン）はこれを拾えない。
  3. **origin: は作成時点のみで改訂を追跡しない**: 要件の `origin:` は最初に起票された
     spec-issue しか記録できない構造的制約があり、後続の改訂issueの記録先が無い。
  4. **spec-issue に重複解消の正規手段が無い**: `spec_update.py` の権限マトリクスに
     spec-issue 用の `deprecated`（または `superseded`）遷移が定義されておらず、SI-CORE-019の
     ような重複が機械的にクローズできない（SI-CORE-027 で実行しようとして機械的に拒否された
     実例あり）。
  - **追加の実例**: 本ISSUE起票時点の重複チェックで、bitz-sdd workspace 自身にも
    `SI-SDD-003`（accepted）が単体実行では未着手表示になる事例を確認した
    （`--workspace . plugins/*` 一括実行では解消 — 原因1・3と同型のパターン）。
- **提案する修正（テスト不要 — ドキュメントのみの規律追加）**:
  1. **完了記録ステップの明文化**（原因1）: `sdd-issue/SKILL.md` の「後続工程」節に、
     spec-issue が実際に実装された時点（軽量レーンでの直接反映、または要件化パスで対応
     requirement が `verified` に達した時点）で、当該 spec-issue 本文に完了記録を追記する
     ことを必須ステップとして追加する。既に「予備判定の提示」等の既存ステップと並ぶ形で
     フロー図（1〜6の番号付き手順）に組み込む。
  2. **語彙の統一**（原因2）: 完了記録の語彙を `- **実施**: <日付> <根拠>` に一本化することを
     `sdd-core/references/lifecycle.md` に明記する（「実装完了」等の類義語は使わない）。
     既存の SI-CORE-012/020 の「実装完了」表記は、混乱を避けるため書き換えず併記のまま残す
     （事後変更は最小限にする — 実際 SI-CORE-020 には本セッションで `**実施**:` 行を並記済み）。
  3. **origin: の限界を明文化**（原因3。ツール変更は行わない）: `lifecycle.md` に
     「`origin:` は要件の初回起票元のみを記録し、後続の改訂 spec-issue は追跡しない。
     改訂の記録は改訂元 spec-issue 側の `**実施**:` マーカーで行う」という設計上の割り切りを
     明記する（CORE-FR-012 が `origin:` と実施マーカーの両方を見る設計になっている理由の説明）。
  4. **spec-issue の重複解消手段の追加**（原因4。`spec_update.py` の変更を伴う）:
     `TRANSITIONS["spec-issue"]` に `("accepted", "superseded")` を人間専用遷移として追加し、
     `superseded_by:` frontmatter と組み合わせて重複の正式クローズを可能にする（テスト先行。
     `tests/test_spec_update.py` に回帰テストを追加）。lifecycle.md の spec-issue 状態遷移図に
     `accepted → superseded`（人間専用）を追記する。
- **対象ファイル**: `tests/test_spec_update.py`（4のみ、先行）、
  `plugins/bitz-sdd/skills/sdd-core/scripts/spec_update.py`（4のみ）、
  `plugins/bitz-sdd/skills/sdd-core/references/lifecycle.md`（2, 3, 4）、
  `plugins/bitz-sdd/skills/sdd-issue/SKILL.md`（1）、bitz-sdd マニフェスト bump。
- **確認観点**:
  - 1〜3 はドキュメント追記のみで既存フローの挙動を変えないこと（規定の追加であって変更でない）
  - 4 は `.venv/bin/pytest` 全件 green（共有スクリプト変更のため部分実行不可）、
    `accepted → superseded` 遷移が `--by-human` 無しでは拒否されること、
    既存の `("open","accepted")` `("open","rejected")` 遷移に影響しないこと
  - `spec_inspect.py --workspace . plugins/*` PASS
- **影響推定・ロールバック**: 1〜3 はドキュメント追記のみで単独 revert 可能。4 は
  `spec_update.py` への遷移追加のみで既存遷移を変更しないため後方互換（追加した遷移の
  削除で revert 可能）。
- **依存**: CORE-FR-012（本ISSUEの発見契機）。SI-CORE-026 / SI-CORE-027 / SI-ENV-022
  （個別修復の実例。本ISSUEはその一般化・恒久化）。

## 予備判定（推薦） — 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。1〜3はドキュメント追記のみ。4は spec_update.py に新しい遷移を追加するのみで既存の権限マトリクスは変更しない |
| ガードレール抵触 | なし |
| 影響範囲 | 限定的。lifecycle.md / sdd-issue SKILL.md / spec_update.py（1関数のテーブル追加）+ テスト1件 |
| 軽量レーン適否 | 1〜3は軽量レーン可（ドキュメントのみ）。4は spec_update.py という共有スクリプトの契約（遷移権限マトリクス）拡張のため通常フロー推奨（Design Gate 不要な軽微な拡張だが、テスト先行と全件pytestは必須 = SDD-FR-112） |

**推薦: accept**（根拠: 今回発覚した4つの根本原因はいずれも低リスクな恒久対策があり、放置すると同種のノイズ・重複放置が再発し続けるため）。
最終裁定はユーザー自身の明示指示による `spec_update.py --to accepted --by-human` で行うこと。
