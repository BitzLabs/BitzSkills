---
id: SI-SDD-029
raised_by: bitz-flow v2再設計で旧verified要件と新draft designが併存（2026-07-29）
target: spec_status.pyの完了済み旧世代と新設計世代の併存時phase判定
proposed_change_type: modify
status: open
---
- **目的**: 完了済みの旧要件・タスクと、新たに開始したDiscovery/Design成果物が同じworkspaceに
  併存するとき、`spec_status.py`が旧世代だけを根拠に`done`を返し、新しいDesign Gate待ちを
  報告できない問題を解消する。bitz-flowではFLW-FR-001/002と全taskがverified/doneのまま
  v2 designとFAIL reviewを追加した結果、statusは`Done（Promotion Gate待ち）`を返した。
- **既存Issueとの関係**: SI-SDD-020 / SDD-FR-136は設計フェーズ語彙の追加を完了済みだが、
  「要件が1件でもあればdesign成果物を無視してplan以降を判定する」ことを明示的に契約している。
  本Issueはその未扱いケースであり重複ではない。既存greenをredにし得るため、既定判定を変える案を
  採る場合はSDD-FR-136のsupersede候補となる。
- **提案する修正**:
  1. `workspace phase = 単一値`だけで複数世代を表せるかをDesign Gateで再評価する
  2. 少なくとも次の3案を比較する:
     - A: `.spec/initiatives/<id>.md`等の明示manifestで成果物ID集合とactive initiativeを指定
     - B: workspace `phase_code`は後方互換で維持し、JSONへ`active_tracks`と
       `phase_conflicts`を加算してsdd-planが解釈
     - C: `--initiative <id>`指定時だけ対象集合を限定してphaseを返す
  3. 古いdraftの残骸や過去reviewを新initiativeと誤認しない、明示的で機械検証可能な識別子を持つ
  4. 新initiativeがDesign Gate待ちまたは最新review FAILの場合、次アクションにDesign是正を示し、
     旧世代のPromotion Gateを唯一の次工程として案内しない
  5. 既存JSON consumersのため現行`phase_code`値を削除・改名せず、破壊変更が必要なら後継schemaを上げる
  6. fixtureとして「旧verified+新design」「旧promoted+放置draft」「2initiative並行」
     「明示initiativeなし」を追加する
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py`、
  `sdd-core/references/gates.md`、`sdd-plan/SKILL.md`、`sdd-report`の必要箇所、
  `tests/test_spec_status.py`、`tests/test_spec_labels.py`、SDD-FR-136の後継候補。
- **確認観点**:
  - 単に「design fileがあればdesign優先」とせず、古いdraftによるfalse positiveを防ぐこと
  - 同じworkspaceの旧契約と新initiativeを別々に追跡できること
  - 既存`phase_code`消費者の後方互換性を明示すること
  - sdd-reviewが同じinitiative対象集合を利用できること
  - `spec_status.py`は読み取り専用を維持すること
- **影響推定・ロールバック**: `spec inspect --impact SDD-FR-136`はルート
  `tests/test_spec_labels.py`、`tests/test_spec_status.py`とbitz-sdd `SDD-TSK-020`の計3件を列挙。
  JSON公開契約とphase解釈に触れるため軽量レーン不可、通常フロー + Design Gateが必要。
  加算案なら新fieldを無視する既存consumerは維持できる。既定phase変更案ならSDD-FR-136を
  supersedeし、旧テストをtombstone化する。ロールバックは新field/選択ロジックとfixtureを一括revertする。
- **依存**: SDD-FR-120（sdd-plan）、SDD-FR-136（phase判定）、SDD-FR-137/140
  （表示・語彙同期）、SI-SDD-028（review対象世代の識別）。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | SDD-FR-136の明示挙動を変更し得る。案によりbumpまたはsupersedeが必要 |
| ガードレール抵触 | なし。読み取り専用集計を維持する |
| 影響範囲 | status/plan/report、phase関連テスト。機械列挙は3件 |
| 軽量レーン適否 | 不可。JSON公開契約とphase判定を変更する |

**推薦: accept**。既存単一世代fixtureでは検出できなかったが、brownfield再設計で再現し、
誤った次工程を案内するため。
