---
id: SI-SDD-020
raised_by: SI-CORE-018（表示層日本語化）の対訳表作成時に発見（2026-07-21）
target: plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py の determine_phase() が返すフェーズ語彙
proposed_change_type: modify
status: accepted
---
- **優先度（推薦）**: **高**。SI-CORE-018 のタスク1（lifecycle.md への対訳表制定）が本 issue の
  裁定結果に依存してブロックされるため、SI-CORE-018 より先に裁定する必要がある。
- **目的**: sdd-core の正規フェーズ定義（`sdd-core/SKILL.md` フェーズ・ルーティング表）と
  `spec_status.py` の `determine_phase()` が返すフェーズ語彙が食い違っている。整合させる。
  - **設計フェーズ `Discuss` が実装に存在しない**: SKILL.md は `sdd-design` / `sdd-data` /
    `sdd-ops` / `sdd-review` の4スキルを `Discuss` フェーズに割り当てているが、
    `determine_phase()` が返すのは `map / discovery / plan / execute / verify / done` のみで、
    設計工程を持つこれら4スキルの居場所が機械集計に無い。結果として、ディスカバリー完了後に
    設計を進めている最中のワークスペースは `Discovery` または `Plan` と誤表示され、
    `gates.md` に定義された Design Gate の手前・奥のどちらにいるかを機械集計が報告できない。
  - **`discovery` が正規語彙に無い**: 実装側が独自に追加したコードで SKILL.md の表に登場しない。
  - 意図的な除外とは考えにくい。`has_discovery` は `.spec/discovery/` の成果物有無を見る1行の
    検出であり、`.spec/design/` に同じ検出をするコストはゼロのため、実装漏れと見るのが自然。
- **提案する修正**:
  1. 正規フェーズ語彙を1箇所に確定する。`SKILL.md` のルーティング表と `determine_phase()` の
     どちらを正とするかを Design Gate で裁定し、`discovery` を正規語彙へ昇格させるか
     `Map` に吸収するかを決める。
  2. 設計フェーズを `determine_phase()` に追加する。`.spec/design/*.md` の成果物有無
     （`has_discovery` と同形の検出）を入力に加え、要件承認前・設計成果物ありの状態を
     独立したフェーズコードとして返す。
  3. フェーズ判定の分岐順序（discovery → design → plan の優先順位）と、設計成果物と要件が
     併存する場合の判定を決定的に定義する。
  4. `next_actions()` に設計フェーズの次アクション（Design Gate 通過準備・sdd-review 実施）を追加する。
  5. 回帰テストを先行追加する（設計成果物のみ / 設計＋draft要件 / 設計なしの各 fixture）。
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py`、
  `plugins/bitz-sdd/skills/sdd-core/SKILL.md`（ルーティング表）、
  `plugins/bitz-sdd/skills/sdd-core/references/gates.md`（Design Gate との対応）、
  `plugins/bitz-sdd/skills/sdd-plan/SKILL.md`（フェーズ解釈）、`tests/test_spec_status.py`、
  SDD-FR-120 の改訂または後継要件、bitz-sdd の3マニフェスト。
- **確認観点**:
  - 正規フェーズ語彙の定義箇所が1つに閉じ、SKILL.md と実装が一致すること
  - 既存の `phase_code` 値（`map` / `plan` / `execute` / `verify` / `done`）を消費する
    外部プロジェクトへの後方互換方針が明示されていること（値の削除・改名を伴う場合）
  - `tests/test_spec_status.py` の既存 `phase_code` アサーションが更新され全 PASS すること
  - `spec inspect --workspace . plugins/*` / `release_check.py` / 全 pytest が PASS
- **影響推定・ロールバック**: `spec_status.py` の **機械判定（JSON 出力の `phase_code`）の変更**で
  あり、SI-CORE-018（表示層のみ・データ移行なし）とは影響範囲が異なる。`.spec` の frontmatter
  移行は不要だが、`phase_code` を消費する外部利用プロジェクトに影響し得る。ロールバックは
  `determine_phase()` とテストの revert で戻る。`spec_inspect --impact SDD-FR-120` の依存成果物は0件。
- **依存**: SDD-FR-120（sdd-plan のフェーズ判定・ゲート状態提示）の改訂を伴う。
  **SI-CORE-018 は本 issue の裁定結果に依存する**（対訳表に載せるフェーズ行が確定しないため）。
  分離理由: 本 issue は機械判定の変更であり、SI-CORE-018 の「表示層のみ・revert で戻る」という
  影響推定を壊すため同一 issue に束ねない（1要望 = 1 spec-issue）。
- **可否の予備判定（推薦）**: **accept 推薦**。根拠:
  - 既存要件との矛盾: なし。SDD-FR-120 の受入基準「フェーズ判定とゲート状態（gates.md 参照）」を
    むしろ充足する方向の修正
  - ガードレール抵触: なし
  - 影響範囲: `spec_inspect --impact SDD-FR-120` = 依存成果物0件
  - 軽量レーン適否: **不可**。`phase_code` は JSON 出力の公開契約であり、通常フロー + Design Gate を要する
- **裁定（2026-07-21, 人間）**: **accepted**。要件化パスで対応する（`SDD-FR-136`）。
- **Design Gate 裁定（2026-07-21, 人間）**: 3論点を次のとおり確定した。
  - **論点A（`discovery` の去就）**: **正規語彙へ昇格させ、`design` を新規追加する**（案2）。
    正規モデル側の `Discuss` を成果物ベースで `discovery` / `design` に分割し、SKILL.md の
    ルーティング表と gates.md の文言を実装に整合させる。採用理由: ①既存 `phase_code` を
    削除・改名しないため純粋に加算的で公開契約を壊さない ②`determine_phase()` は成果物の
    有無から機械推定する設計であり、人間の討議活動名である `Discuss` より `.spec/discovery/` と
    `.spec/design/` を分ける粒度の方が判定の実態に忠実。
    不採用: 案1（`discovery` を廃し `discuss` に吸収）は canonical と完全一致する代わりに
    `phase_code` の破壊的変更を伴うため。案3（`discovery` 据え置き + `discuss` 追加）は
    実装語と正規語が混在し一貫性が最も低いため。
  - **論点B（`done` の扱い）**: **`done` を維持し、表示ラベルのみ Promotion Gate 待ちである
    ことを示す**（案B1）。`promotion` への改名は破壊的変更のため不採用。
    ※ `done` が正規語彙に無い点は起票時に挙げた2件に続く**3つ目の不整合**として Design Gate で
    追加検出したもの。修正1「正規フェーズ語彙を1箇所に確定する」の範囲内として同時に解消する。
  - **論点C（判定の分岐順序）**: 要件・タスクがいずれも0件のときだけ `design` > `discovery` >
    `map` の優先順位で判定し、要件が1件でも存在すれば既存の `plan` 以降の判定をそのまま適用する。
    根拠: 「要件の起票をもって Plan フェーズ入りとみなす」現行の暗黙ルールを維持でき、
    既存の全テストケースの挙動が変わらないため。
