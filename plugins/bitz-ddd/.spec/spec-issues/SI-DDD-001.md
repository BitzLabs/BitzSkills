---
id: SI-DDD-001
raised_by: SDD-REV-006 GP-003 で bitz-ddd を適用した際に発見（2026-07-29）
target: 旧英語8章 docs パスへの参照が残存する
proposed_change_type: modify
status: open
---
- **目的**: bitz-sdd は SI-SDD-012 で docs レイアウトを旧英語8章から日本語6章へ移行し、
  同期マッピングも SDD-FR-126〜128・SDD-FR-149 で日本語パスへ更新した。しかし
  **bitz-ddd の各スキルは旧パスを参照したまま**であり、利用者に存在しない同期先を案内する。
  bitz-ddd は bitz-sdd への依存を宣言しており（`metadata.dependencies: ["bitz-sdd>=2.0"]`）、
  依存先の公開契約（同期マッピング）の変更に追随していない状態である。
  実際に本 issue は、bitz-sdd の設計層を後付けするために bitz-ddd を適用した作業中に
  発見された（成果物の書き込み先自体は `.spec/design/` であり実害は出なかったが、
  スキル本文の案内は誤っている）。
- **該当箇所**（6件）:
  1. `skills/ddd-model/SKILL.md` — `docs/02-design/domain-model.md` に同期される旨
  2. `skills/ddd-model/references/domain-modeling.md` 3行目 — 同上
  3. `skills/ddd-model/references/domain-modeling.md` 25行目 — `docs/01-context/glossary.md`
  4. `skills/ddd-model/references/domain-modeling.md` 43行目 — `docs/02-design/domain-model.md`
  5. `skills/ddd-story/references/domain-story.md` 7行目 — `docs/01-context/personas-journeys.md`
  6. `skills/ddd-story/SKILL.md` — `docs/02-design/domain-story.md` に自動集約される旨
- **提案する修正**:
  1. 日本語6章の対応先へ置き換える
     （`docs/03_設計仕様/ドメインモデル.md` / `ドメインストーリー.md`、
     `docs/00_はじめに/用語集.md` / `ペルソナ・ジャーニー.md`）
  2. 依存先の公開契約変更に追随できていなかった経路を検討する。bitz-sdd の同期マッピングは
     SDD-FR-150 で機械検証されるようになったが、**依存プラグイン側の記述は対象外**である
  3. `ddd-doctor` の診断項目に、依存先の公開契約との整合を含めるか検討する
- **対象ファイル**: 上記6箇所、関連する DDD-FR 要件、bitz-ddd マニフェスト。
- **確認観点**: 置換後のパスが bitz-sdd の `DEFAULT_MAPPING` の同期先と一致すること。
  bitz-sdd 側のマッピングが再び変わったときに検出できること。
- **影響推定・ロールバック**: 文書のみの修正であり軽量レーン可。2・3 は依存プラグイン間の
  契約追随の仕組みであり、範囲が大きいため別途裁定する。
- **依存**: SI-SDD-012（日本語6章移行）、SDD-FR-149 / SDD-FR-150（同期マッピングと機械検証）。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。bitz-sdd 側の現行マッピングへ合わせるだけ |
| ガードレール抵触 | なし |
| 影響範囲 | bitz-ddd の2スキル・6箇所。実害は案内の誤りに留まる |
| 軽量レーン適否 | 1 は可（文書修正）。2・3 は不適（プラグイン間の契約追随） |

**推薦: accept**。ただし **1（パス置換）と 2・3（追随の仕組み）を分けて扱う**こと。
1 は即座に直せる。2・3 は「依存先の公開契約が変わったとき、依存側がどう気づくか」という
より大きな問題であり、bitz-env / bitz-flow にも同型の問題がありうる。
