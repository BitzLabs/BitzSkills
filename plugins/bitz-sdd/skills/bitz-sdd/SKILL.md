---
name: bitz-sdd
description: BitzSDD — 仕様駆動開発（SDD）ワークフローを運用するスキル。要件定義・仕様作成・実装・検証・完了処理のすべてをこの規律に従って実行する。ユーザーが「仕様駆動」「SDD」「要件」「EARS」「spec」「タスク分解」「feature実装」に言及したとき、リポジトリに .planning/ や AGENTS.md が存在するとき、または新機能の設計・実装・検証・リリース処理を依頼されたときは、明示的な指示がなくても必ずこのスキルを使うこと。要件の変更・廃止・番号管理・テスト失敗時の対応・ドキュメント更新もすべて本スキルの管轄。
metadata:
  version: "1.0.0"
  author: br7.hide
  created: "2026-07-07"
  updated: "2026-07-07"
---

# BitzSDD Workflow

個人用の仕様駆動開発フレームワーク。docs/（人間の意図・永続）と .planning/（AI実行契約・短命）を分離し、EARS記法の要件を機械検証で充足させる。対象スタック: Antigravity 2.0 / cc-sdd / GSD / Claude Code。

## 憲法（5原則）

規則同士が衝突したら番号の小さい原則が勝つ。

1. **spec-anchored** — 仕様とコードは共存。仕様が実行を駆動するが、動くコードが最終的な真実
2. **一方向派生** — docs/ → .planning/ → code の順にのみ派生。逆流は Promotion Gate のみ
3. **検証中心** — 人間は行をレビューしない。合否は機械が出し、人間はゲートと例外だけを見る
4. **権限分離** — エージェントは契約を実装できるが、書き換えられない。仕様の変更権は常に人間
5. **短命と永続の分離** — .planning/ は feature 単位で使い捨て。docs/ と LESSONS_LEARNED は永続

## 絶対規則（すべてのフェーズで適用）

これらは references を読まなくても常に守ること:

- **requirements/ 配下のファイルを編集しない**（人間専権）。仕様の矛盾・曖昧を発見したら `spec-issues/` に提案を起票する
- **実装中にID採番しない**。新要件が必要なら spec-issue（仮番号 `SI-<branch>-<n>`）を起票
- **docs/ に書き込まない**（Promotion Gate のドラフト生成を除く）
- **status が implementing 以降の要件のEARS節は不変**。変更は人間の bump/supersede 裁定を経る
- 検証 red のとき、通したいがために仕様・テスト・閾値を緩めることは絶対にしない
- コスト予算（tasks/ メタデータ宣言）を超過したら停止して報告する

## ディレクトリ構成

```
docs/                        永続・人間ナラティブ（WHY と人間向けWHAT）
  MASTER.md / 01-context/ / 02-design/(ARCHITECTURE, DECISIONS) / 06-reference/ / 08-knowledge/LESSONS_LEARNED.md
.planning/                   短命・AI実行仕様（検証可能なWHAT と HOW）
  PROJECT.md / ROADMAP.md
  requirements/              1要件1ファイル。_index.md と _counter.md は自動生成（手編集禁止）
    FR-*.md NFR-*.md CON-*.md / domains.md / _lint-rules.md
  spec-issues/SI-*.md        エージェント発の仕様変更提案
  specs/<feature>/           EARS→検証マッピング、boundary×checks×depends_on
  tasks/                     タスク分解+依存グラフ
  STATE.md                   ブランチローカルの生きたメモリ
  metrics.md                 ワークフロー計測
AGENTS.md                    読み込みプロトコル+権限マトリクス
```

同一事実が両ツリーにある場合: 意図は docs/ が勝ち、契約と状態は .planning/ が勝つ。

## 読み込みプロトコル

起動時は最小ロード: `PROJECT.md` → 担当タスク → タスクの `implements:` が指す要件ファイルのみ。docs/ の全読みは禁止（必要な節だけ参照）。

## フェーズ・ルーティング

GSDの5フェーズ + Gate。**今どのフェーズかを判定し、対応する reference を読んでから作業する**:

| いまやること | フェーズ | 読むファイル |
|---|---|---|
| プロジェクト把握・docs/整備 | Map / Discuss | references/lifecycle.md |
| docs/ が未整備（MASTER.md がない等） | Map | （`sdd-docs` スキルで docs/ を初期化・検証する） |
| 要件起票・採番・変更・廃止 | Plan | references/lifecycle.md |
| 仕様→タスク分解・並列投入 | Plan / Execute | references/parallel-git.md |
| 実装・テスト作成 | Execute | references/verification.md |
| 検証 red・エラー・矛盾発見 | Execute / Verify | references/failure-protocol.md |
| 検証・カバレッジ確認 | Verify | references/verification.md（+ scripts/spec_inspect.py 実行） |
| feature完了・docs/更新 | Promotion Gate | references/gates.md |
| 既存コードへの導入 | 導入 | references/adoption-metrics.md |
| ワークフロー自体の見直し | 定期 | references/adoption-metrics.md |

## 要件ステータス（状態機械の要約）

`draft → approved → implementing → verified → promoted`、廃止は `deprecated`（`superseded_by:` 必須）。

- draft→approved と verified→promoted と deprecated 裁定は**人間のみ**
- approved には spec-lint 合格と `verification_method:` 記入が前提条件
- implementing→verified は機械判定（全検証 green + stale マークゼロ）

詳細な遷移規則・改訂vs継承の判定（「緑を赤にし得るか」基準）・変更伝播は references/lifecycle.md。

## 検証ツール

構造検証・孤児/幽霊検出・カバレッジ・変更影響分析は同梱スクリプトで実行する:

```bash
python scripts/spec_inspect.py <repo-root>              # 全検証 → inspection-report.md
python scripts/spec_inspect.py <repo-root> --impact FR-012   # FR-012変更の影響成果物を列挙
```

Verify フェーズと Promotion Gate では必ず実行し、レポートを人間に提示する。
docs/ 側の構造検証（docs_inspect.py）は `sdd-docs` スキルが担うので、Promotion Gate では両方を実行する。

## テンプレート

新規作成時は assets/ のテンプレートをコピーして使う（書式ドリフト防止のため、記憶から書き起こさない）:

- assets/requirement.md — 要件ファイル（frontmatter必須項目つき）
- assets/spec-issue.md — 仕様変更提案
- assets/domains.md — ドメインコード統制語彙
- assets/lint-rules.md — EARS lint と禁止語辞書
- assets/AGENTS.md — 新規リポジトリ初期化用
- assets/metrics.md — 計測台帳

## ユーザーへの応答姿勢

- 裁定が必要な遷移（承認・supersede・Gate）では、機械チェック結果と推奨を添えて人間に判断を求める。勝手に進めない
- spec-issue を起票したら、要点（何が矛盾し、bump/supersede どちらを提案するか）を会話でも報告する
- フェーズをまたぐ長い作業では、STATE.md に進捗と判断根拠を追記しながら進める
