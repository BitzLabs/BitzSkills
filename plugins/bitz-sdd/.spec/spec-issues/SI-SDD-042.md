---
id: SI-SDD-042
raised_by: bitz-flow M2 設計での実事故（blocking GP の取り違えが機械検査を素通り）
target: sdd-review の review schema・sdd-core の spec_inspect.py・ROADMAP のV4テーマ
proposed_change_type: new
status: open
origin: bitz-flow
---
- **目的**: **レビュー指摘が設計へ正しく受領されたか**を機械検証できるようにする。
  bitz-sdd はレビュー**結果**（findings・スコア・verdict・`gate_preconditions`）を成果物化し
  `spec_inspect.py` が schema・ID 形式・`tracked_by` の幽霊参照まで検査するが、
  **検査しているのはリンクの存在であって応答の妥当性ではない**。
  テーマ13（検証活動の成果物化）と同型の欠落 — 結果は持つが過程を持たない。

- **根拠となった実測**（2026-08-12、bitz-flow M2。委託元 workspace の実事故）:

  1. `FLW-REV-011` が blocking な `gate_preconditions` を **18件**提示した
  2. `FLW-DSN-016` が「GP → 節番号」の対応表で応答した
  3. `spec_inspect.py` は **問題 0 / 幽霊参照 0** で通した
  4. ところが `GP-004`「instance identity を **precondition に入れ**、apply 直前に CAS 照合する」に対し、
     設計は「canonical **guard key** に instance identity を含める」と応答していた

  これは不十分な対応ではなく**安全性の反転**だった。key に instance を混ぜると
  「旧 instance の discard」と「新 instance の create」が別 key になり互いに排他しない。
  GP が防ごうとした事故（承認待ち中に作り直された worktree を消す）を防ぐどころか、
  同一 path に対する直列化そのものを失う。
  起案者の再読で `FLW-REV-012:SYN-001`（P0）として検出し是正したが、
  **機械検査はすべて green のままだった**。

  テーマ13 の根拠（「総合 4.74 の高得点レビューが達成不能な出口条件を通した」）と同じく、
  **閾値でも観点でも捕捉できない**種類の欠落である。

- **提案する修正**:

  1. **blocking GP のうち振る舞いを要求するものを EARS で書く。**
     上の例を EARS 化すると
     「WHEN worktree の destructive operation を apply する THEN bitz-flow は plan 時の
     instance identity と現在の instance identity を照合し、一致しない場合は mutation しないこと SHALL」
     となり、「guard key に含める」応答は **WHEN 節を満たさない**
     （key は guard 取得時に計算される値であり apply 時点の検査ではない）。
     **対応表に並べた時点で不成立が見える。**
     `spec_inspect.py` は既に EARS を lint しており（`- WHEN` で始まる節に `SHALL` があるか）、
     同じ場所に禁止語（測定不能）lint もある。**新規実装はほぼ不要で既存機構を流用できる。**

  2. **GP を型で分ける（EARS-washing の回避。本提案の核心の半分）。**
     `behavioral` / `artifact` / `process` を区別し、**`behavioral` にだけ EARS を必須**とする。
     `FLW-REV-011` の 18件を実際に仕分けるとおおよそ半々に割れた。

     | 型 | 例 |
     |---|---|
     | `behavioral` | GP-004（CAS 照合）、GP-003（包含規約）、GP-009（case 感度の祖先遡り） |
     | `artifact` / `process` | GP-012（三者照合テストを追加）、GP-013（fixture を採番）、GP-018（version を上げる） |

     後者を EARS 化すると「WHEN リリースする THEN テストが存在すること SHALL」のような
     **架空の system を主語にした空文**になり、形式を満たすだけで検証可能性を上げない。
     **全件 EARS 化は明確に避ける。**

  3. **応答の逐語照合。** 設計側の GP 対応表へ GP 原文（`behavioral` なら EARS 文）を
     **逐語転記**し、乖離を機械検出する。前例は `release_check.py` のマーカー方式
     （`spec_labels.py` の対訳辞書、`DEFAULT_MAPPING`、`PHASE_CODES` の三者照合）。
     現行の「GP → 節番号」は、節を指しただけで対応済みになる。

  4. **`sdd-test` への接続。** `sdd-test` は「EARS 記法の要件からテスト仕様を導出」を持つ。
     blocking GP が EARS なら **GP がそのまま fault fixture の設計入力になる**。
     テーマ6（EARS ⇄ テストID ⇄ テストモジュール）の対象を要件から GP へ広げるかを評価する。

  5. **昇格経路。** blocking GP が後に要件化されるとき、現状は自然文のため書き直しが発生し
     そこで意味がずれる余地がある。最初から EARS なら受入基準へそのまま移せる。

- **schema 案**: `gate_preconditions` は現在 `id` / `kind` / `basis` / `statement` / `evidence`。
  ここへ `gp_kind`（`behavioral` | `artifact` | `process`）と `ears`（`behavioral` のとき必須）を
  加算する。`statement`（人間向け説明）はそのまま残す。
  検査は「`behavioral` なら `ears` があり `WHEN` 節に `SHALL` がある」で、既存 lint の条件式を再利用する。

- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-review/`（review schema と観点定義）、
  `plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py`（`_check_gate_preconditions`）、
  `plugins/bitz-sdd/.spec/ROADMAP.md`（V4 テーマと未裁定論点）。

- **確認観点**:
  - `gp_kind: behavioral` で `ears` を欠く GP が FAIL すること。
  - `artifact` / `process` の GP に EARS を要求しないこと（空文の量産を防ぐ）。
  - 設計側の対応表に GP 原文が逐語で無い場合に検出されること。
  - **設計が GP を正当に却下する経路**が表現できること（下記論点41）。

- **影響推定・ロールバック**: レビュー成果物の schema へ**加算**する変更であり、
  既存 review の必須キーは変えない。`ears` は `behavioral` のときだけ必須のため、
  既存の18件を含む過去のレビューは `gp_kind` 未記入で従来どおり通る（段階移行が可能）。
  ロールバックは追加した2 field と検査を除くだけで足りる。

- **V4 への提案（テーマ14 と新規論点3件）**:

  **テーマ14「レビュー指摘の受領検証」** をテーマ3・6・13 に接続する新テーマとして提案する。
  テーマ3 は**水準と観点**、本テーマは**指摘の形式と受領検証**であり別の判断である。

  - **論点40. blocking GP の EARS 必須化と型分け** — `behavioral` / `artifact` / `process` の
    判別を誰が行うか（レビュアーの宣言か機械推定か）。既存 schema への加算で足りるか。
  - **論点41. GP 応答の逐語照合の強度** — 逐語一致を FAIL とするか WARN とするか。
    あわせて**設計が GP を正当に「却下」する経路**をどう表現するか。
    レビューが誤っている場合に逐語一致を強制すると、
    **誤った指摘への追従を機械が強要する**。却下には理由と再レビューを要求する形が要る。
  - **論点42. GP → 要件の昇格経路** — blocking GP が要件化されるときの ID 継承と、
    「どの GP がどの要件になったか」のトレーサビリティをどこに持つか。

- **限界（提案の弱いところ。隠さず記載する）**:
  1. EARS は「どの時点か」を書かせるが「**どの時点が正しいか**」は強制しない。
  2. **振る舞いに落ちない指摘は EARS にならない。** `FLW-REV-011:SYN-015`
     （「key 集合は加算のみ」を closed enum 値追加の互換性根拠に誤用している）は
     論証の誤りであり EARS で表現できない。価値ある指摘の一部は構造化の外に残る。
  3. **独立レビューの代替にならない。** `FLW-REV-011` が P0 5系統を出せたのは
     独立の目があったからで、形式化は「取り違えない」ための網にすぎない。

- **依存**: テーマ3（レビュー品質目標。`ReviewFinding` への追跡）、
  テーマ6（EARS ⇄ テストID ⇄ テストモジュール）、テーマ13（検証活動の成果物化）、
  論点16（System Engineering Review の実装形態）、`SI-SDD-041`（レビュー成果物の scaffold。
  本件が加える field は同 issue の雛形にも反映が要る）。
  **推薦: accept**。既存の EARS lint とマーカー照合の前例に乗るため実装が薄く、
  委託元（bitz-flow）で**実際に P0 を素通りさせた**再現性のある欠落である。
  ただし全件 EARS 化は明確に不採用とし、型分けを同時に入れることを accept の条件とする。

- **手動先行版**: 委託元の `FLW-DSN-016` §15 は、本 issue の裁定を待たずに
  GP 原文の逐語併記へ変更済み（v1.2）。機械化されれば同表が検査対象になる。
