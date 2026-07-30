---
id: SI-SDD-038
raised_by: ROADMAP 順序10（V4設計Ready canary）の実測（2026-07-30）
target: spec_inspect の幽霊参照走査が .spec/design/ と .spec/reviews/ を参照元として含まない
proposed_change_type: modify
status: open
---
- **目的**: `spec_inspect.py` の幽霊参照走査は、`references/verification.md` の走査対象表のとおり
  `.spec/specs`・`.spec/tasks`・`tests`・`test`・`src` を参照元とし、**`.spec/design/` と
  `.spec/reviews/` を含まない**。`SDD-FR-162` により `design/` は再帰的に走査されるようになったが、
  それは成果物を**レジストリへ登録する**ための走査であり、そこに書かれた**発信参照の検査**では
  ない。結果として、設計成果物とレビュー成果物が存在しない ID を参照しても検出されない。

  順序10 の canary で次を実測した（対照群として `.spec/specs/` を併置）。

  | 参照元 | 幽霊 ID を記載 | 終了コード | 検出 |
  |---|---|---|---|
  | `.spec/specs/<f>/test-spec.md` | 本文 | 1 | される（対照群） |
  | `.spec/reviews/<REV>.md` | 本文 | 0 | **されない** |
  | `.spec/design/<DSN>.md` | 本文 | 0 | **されない** |
  | `.spec/design/<DSN>.md` | frontmatter `implements:` | 0 | **されない** |

  あわせて、実在要件を設計・レビューだけが参照している場合、その要件の「参照元数」は 0 のままで
  未参照として扱われる。設計から要件への追跡が集計に反映されない。

  V4 のターゲット設計（P5）は `domain-model` / `architecture` / `api-design` / 移行計画など
  十数点の設計成果物を追加し、P6 の Design Gate では多観点レビューと System Engineering Review が
  それらを相互参照する。V4 は同時に要件の後継化・deprecated 化・ID 再編（P4 逆起票要件の分類）を
  行うため、**参照先が消える変更と参照する文書が増える工程が重なる**。現状のままでは、
  設計・レビューが古い ID を指したまま Design Gate を通過しうる。

- **提案する修正**:
  1. `.spec/design/` と `.spec/reviews/` を幽霊参照の走査対象へ加える。`design/` は
     `RECURSIVE_ARTIFACT_DIRS` に従いサブディレクトリまで再帰する。
     自己言及 ID（`SI-CORE-002` で除外した自身の ID）と、既存の走査対象と同じ除外規則を適用する。
  2. 設計成果物の frontmatter `implements:` を、タスクの `implements:` と同じく参照として解決し、
     未解決なら FAIL とする。あわせて解決できた参照を要件の「参照元数」へ算入するかを裁定する
     （算入すると、設計だけが参照する要件が未参照リストから外れる。
     算入しないなら、設計参照は幽霊検出のみに使う）。
  3. 加法的導入とし、既存ワークスペースで新たな FAIL が出ないことを先に実測する。
     出る場合は WARN での先行導入（`SDD-FR-153` の証跡検査と同じ段階導入）を選択肢とする。
  4. `references/verification.md` の走査対象表と `sdd-core` の該当記述を同時に更新する
     （表と実装の二重定義を残さない）。

- **対象ファイル**: `skills/sdd-core/scripts/spec_inspect.py`（走査対象の定義と参照解決）、
  `skills/sdd-core/references/verification.md`（走査対象表）、`skills/sdd-core/SKILL.md`、
  `tests/test_spec_inspect.py`、`tests/test_design_canary.py`（canary へ回帰を追加）。

- **確認観点**:
  - 重複: `SI-SDD-036`（accepted・実装済み）は `design/` を**レジストリとして**再帰走査し
    ID 一意性と採番根拠を直す issue であり、本 issue の**発信参照の検査**とは対象が異なる。
    `SI-SDD-014` は workspace 外テスト参照の集計であり、参照元ディレクトリの追加ではない。
  - 既存要件との関係: 走査対象と判定仕様は `PROJECT.md` の公開契約に列挙されているため
    **軽量レーン不適**。`SDD-FR-153` の段階導入（WARN 先行）の前例に倣えるか評価する。
  - ガードレール: 設計・レビューは検討段階の候補 ID を書くことがある。
    未確定 ID の記法（バッククォート囲み・明示的な除外マーカー等）を用意せずに FAIL 化すると、
    設計中の記述が書けなくなる。除外手段とセットで裁定する。
  - 検証: 対照群（`specs/`）との一致、`design/` サブディレクトリ、frontmatter `implements:`、
    自己言及の非検出、複数ワークスペースでの解決、既存ワークスペースの無影響を回帰テストする。
  - 軽量レーン適否: **不適**（`spec_inspect.py` の判定仕様は公開契約）。

- **影響推定・ロールバック**: 走査対象の追加は `spec_inspect.py` に閉じ、判定仕様の変更として
  単独 revert できる。導入時に既存ワークスペースが FAIL する場合は、WARN 先行 → FAIL 昇格の
  2段階に分割する。

- **依存**: なし（`SI-SDD-036` は実装済み `SDD-FR-162` として前提が満たされている）。
  V4 の P4（逆起票要件の分類）と P5（ターゲット設計）より**前**に解消すると効果が最大になる。

- **予備判定（推薦）**: **accept 推奨、ただし提案1 を先行**。提案1（走査対象の追加）は
  V4 設計中の参照切れを防ぐ効果が大きく、加法的に導入できる。提案2 のうち
  「参照元数への算入」は未参照要件の集計を変えるため、V4 の Workspace 責任分解
  （ROADMAP テーマ2）とあわせて裁定するほうが安全である。
  除外手段（確認観点3）を用意しないまま FAIL 化することには反対する。
