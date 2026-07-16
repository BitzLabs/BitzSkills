---
name: sdd-plan
description: BitzSDD — 「いまどこまで進んでいて、次に何をすべきか」を対話で答えるナビゲーションスキル。sdd-core の spec_status.py（機械集計）を実行し、フェーズ判定・ゲート状態・次アクション提案（着手可能タスク、裁定待ち spec-issue、draft 要件、blocked の理由）をセッション内で提示する。ユーザーが「次に何をすべきか」「次何する」「現状把握」「どこまで進んだ」「今どのフェーズ」「着手できるタスクは」と言及したとき、またはセッション冒頭で作業の再開点を特定するときに使用する。人間向けレポート成果物（.spec/reports/）の生成は sdd-report が担当する。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-16"
  updated: "2026-07-16"
---

# sdd-plan

BitzSDD プロジェクトの現在地（フェーズ・ゲート状態・未処理の作業）を機械集計から読み取り、
「次に何をすべきか」をセッション内の対話で答えるナビゲーションスキルです。

## 責務境界

| | sdd-plan（本スキル） | sdd-report |
|---|---|---|
| 目的 | セッション内の対話ナビゲーション | 人間向け成果文書の生成 |
| 出力 | 会話での提示のみ（**原則ファイルを書かない**） | `.spec/reports/status-report.md` |
| 集計 | sdd-core の `spec_status.py` に全委譲 | sdd-report 同梱の `sdd_report.py` |

- 集計・カウント等の**決定的処理はすべて sdd-core の `spec_status.py` 側**にある。
  本スキルはその出力の解釈と提案だけを行い、スキル本文にも実行時にも集計ロジックを持たない。
- 本スキルはファイルを生成・変更しない。例外として STATE.md の更新が必要になった場合も、
  直接編集せず sdd-core の `spec_update.py` 経由の遷移記録のみとする。
- 「レポート成果物が欲しい」と言われたら本スキルではなく sdd-report に切り替える。

## 実行手順

1. **機械集計**: sdd-core 同梱の `spec_status.py` を実行する（読み取り専用・ファイル生成なし）。

   ```bash
   python3 <sdd-core スキル>/scripts/spec_status.py <repo-root> --json   # 単一ワークスペース
   python3 <sdd-core スキル>/scripts/spec_status.py --workspace . plugins/* --json  # モノリポ一括
   ```

   プロジェクトにラッパー（例: `scripts/spec status`）が用意されていればそちらを優先する。

2. **フェーズ判定とゲート状態**: JSON の `phase` / `by_status` を読み、いまどのフェーズかを判定する。
   人間裁定点（Discovery Gate / Design Gate / Promotion Gate）の位置づけと通過条件は
   sdd-core の references/gates.md が正 — ゲート待ちが疑われる場合はそちらを参照して裁定に必要な
   証跡（assumptions.md の判定、sdd-review の統合判定、spec_inspect レポート）が揃っているかを確認する。

3. **次アクション提案**: 集計結果から以下を分類して対話で提示する。

   | 分類 | 読み取り元 | 提示内容 |
   |---|---|---|
   | 着手可能タスク | tasks の `pending` | depends_on が解決済みのものを列挙（実装は sdd-implement へ） |
   | 裁定待ち | spec-issues の `open`、requirements の `draft` | 人間の accept / approve 待ちであることと裁定材料の所在 |
   | 検証待ち | requirements の `implementing` | sdd-test での検証・verified 昇格を提案 |
   | blocked | tasks の `blocked` | ブロック理由（依存タスク・裁定待ち・契約変更起票中）を特定して提示 |
   | クリーン | 未処理ゼロ | Promotion Gate の準備、または新しい要望のインテーク（sdd-issue）を案内 |

4. **ルーティング**: 提案した次アクションの実行は、それぞれの担当スキル
   （起票 = sdd-issue、要件・ライフサイクル = sdd-core、実装 = sdd-implement、検証 = sdd-test、
   レポート = sdd-report）へ引き継ぐ。本スキル内で作業を始めない。

## してはいけないこと

- スキル本文・実行時に独自の集計・カウントロジックを持つこと（`spec_status.py` と二重実装になる）
- `.spec/` 配下を含むファイルの生成・編集（STATE.md も直接編集しない）
- ゲートの通過判定を自分で下すこと（ゲートは人間裁定。本スキルは状態の提示まで）
