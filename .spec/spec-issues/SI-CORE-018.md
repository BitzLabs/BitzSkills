---
id: SI-CORE-018
raised_by: プロジェクト改修計画 追加要望（2026-07-12 ユーザー提案: フェーズ・ステータス表記の日本語化）
target: bitz-sdd / bitz-ddd のフェーズ・ステータス表記（表示層）
proposed_change_type: bump
status: accepted
origin: root
delegated_to: bitz-sdd:SDD-FR-137, bitz-sdd:SDD-FR-138, bitz-ddd:DDD-FR-002
---
- **目的**: bitz-sdd / bitz-ddd のフェーズとステータスを「採用・未採用・開発中・
  ○○待機中」のような日本語表記にし、人間が状態を直読できるようにする。
- **設計方針（推奨案）**: **frontmatter の機械値は英語のまま維持し、表示層だけを
  日本語化する**。理由: 既存の全ワークスペース約111ファイルと spec_inspect.py が
  英語機械値に依存しており、値そのものの日本語化は全ファイル移行 + 全ツール改修 +
  外部利用プロジェクトの後方互換を要する高リスク変更のため（値の日本語化を望む場合は
  本 ISSUE の裁定時に代替案として人間が選択する。その場合は正規化層 + 移行スクリプトを追加）。
- **提案する修正**:
  1. **対訳表の制定（SSOT）**: sdd-core references/lifecycle.md に対訳表を定義し、
     機械可読辞書（labels_ja）をスクリプト側に1箇所だけ持つ。対訳案:
     - 要件: draft=起草中（承認待機中）/ approved=承認済み（採用）/ implementing=開発中 /
       verified=検証済み / promoted=昇格済み / deprecated=廃止
     - spec-issue: open=裁定待機中 / accepted=採用 / rejected=未採用
     - タスク: pending=着手待機中 / implementing=開発中 / blocked=依存待機中 / done=完了
     - フェーズ: Map=把握 / Discuss=設計討議 / Plan=計画 / Execute=実装 / Verify=検証 /
       Promotion Gate=昇格ゲート（訳語の最終確定は人間裁定）
  2. **表示への適用**: spec_inspect.py のレポート、spec_status.py（SI-CORE-011）、
     sdd_report.py の status-report、各 SKILL.md / references の表を日本語表記
     （必要なら「日本語（機械値）」併記）に統一する
  3. **入力の受理**: spec_update.py（SI-CORE-012）が日本語表記の入力（例: 「採用」）を
     機械値（accepted）へ正規化して書き込めるようにする（テスト先行）
  4. **bitz-ddd**: ddd-evaluate の成熟度レベル・MMI 採点表の表示も同じ対訳方針で日本語化する
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/references/lifecycle.md`（対訳表）、
  `spec_inspect.py` / `spec_status.py` / `sdd_report.py` / `spec_update.py`（表示・正規化）、
  bitz-sdd / bitz-ddd の SKILL.md・references の状態表、`tests/`（正規化と表示の回帰テスト先行）、
  両プラグインのマニフェスト bump。
- **確認観点**:
  - frontmatter の既存機械値に diff が出ないこと（表示層のみの変更であることがレビューの中心）
  - spec_inspect / release_check / `.venv/bin/pytest` が PASS
  - 日本語入力の正規化で未知語がエラーになること（曖昧な状態値の混入防止）
  - 対訳の定義箇所が lifecycle.md + 辞書1箇所に閉じていること（訳語変更が1 PR で済む）
- **影響推定・ロールバック**: 表示層のみなのでデータ移行なし。表示部の revert だけで戻る。
- **依存**: SI-CORE-011 / 012（表示・正規化の実装先スクリプト）。対訳表の制定（修正1）のみ先行可。
- **裁定（2026-07-13, 人間）**: **表示層のみ日本語化** を採用。frontmatter の機械値は英語のまま維持し、レポート・表示のみ対訳辞書で日本語化する（値の日本語化＝機械値移行は不採用）。
- **裁定（2026-07-21, 人間）**: **status の対訳表を確定**（フェーズ行は保留。次項参照）。
  - 要件: `draft`=起草中 / `approved`=承認済み / `implementing`=実装中 / `verified`=検証済み /
    `promoted`=確定 / `deprecated`=廃止
    （`promoted` は当初 `正式版` で確定していたが 2026-07-21 の再検討で `確定` に改めた。
    後述「フェーズ対訳の確定」の脚注を参照）
  - spec-issue: `open`=裁定待ち / `accepted`=採用 / `rejected`=不採用 / `superseded`=統合済み
  - タスク: `pending`=着手待ち / `implementing`=実装中 / `blocked`=介入待ち / `done`=完了
  - **`superseded` は本 issue 起票時の対訳案に欠落していた**。`spec_update.py` の
    `TRANSITIONS["spec-issue"]` に実在する状態のため追加する（実装時に取りこぼさないこと）。
  - **併記の語順**: フェーズは英語主（`Execute（実装中）`）、status は日本語主（`採用（accepted）`）。
    フェーズ名は工程名＝固有名詞として文書横断で通用する一方、status は frontmatter の内部値で
    しかないため、扱いを分ける。
  - **逆引きの一意性を確認済み**: `実装中` は要件・タスクの両方に現れるが機械値はどちらも
    `implementing` で衝突せず、それ以外はすべて種別を跨いでも一意。曖昧な逆引きは発生しない。
- **保留（2026-07-21）**: **フェーズの対訳行は確定しない**。sdd-core の正規フェーズ定義
  （`sdd-core/SKILL.md` のルーティング表。Map / Discuss / …）と `determine_phase()` の実装
  （`map` / `discovery` / `plan` / `execute` / `verify` / `done`）が食い違っており、設計フェーズ
  `Discuss` が実装に無く `discovery` が正規語彙に無い。この不整合を解消しないまま対訳表を SSOT
  として制定すると、誤った語彙を一段格上げしてしまう。不整合は `bitz-sdd:SI-SDD-020` として
  起票・accepted 済み（2026-07-21）。
  - **実施順序**: SI-SDD-020 を main へ land させた後に本 issue へ着手する。両者は
    `determine_phase()` の**同一 return 文**を書き換える（SI-SDD-020 はフェーズの集合、本 issue は
    ラベル文字列）ため、並行させるとコンフリクトする。逆順では対訳表の二度書きと手戻りが生じる。
- **スコープ判断（2026-07-21）**: 提案する修正 1〜4 の**全項を今回の範囲に含める**。
  修正3（`spec_update.py` の日本語入力受理）は当初 PR 分離を検討したが、次の理由で同一 PR とする:
  - 純粋に加算的で、英語の機械値を渡す既存呼び出しは正規化辞書にヒットせず素通りするため挙動が変わらない
  - 未知語は正規化後の `TRANSITIONS[kind].get((cur, new))` が `None` を返し「不正遷移」で exit 2 に
    なるため、確認観点「未知語がエラーになること」は構造的に満たされる
  - 正規化は権限マトリクス照合より前に行うため、`STATE.md` の遷移記録は機械値のまま保たれる
  - 恩恵を受けるのは人間専用遷移（`draft→approved` / `open→accepted` / `verified→promoted` /
    `*→deprecated`）＝必ず人間がタイプするコマンドであり、対象読者と受益者が一致する
  - **実装上の制約**: ①正規化は `spec_update.py` の `cur == new` 判定より**前**に置く（後ろに置くと
    「遷移不要」であるべきケースが「不正遷移」として誤ったエラーになる）②受理する表記は純粋な
    日本語ラベルと機械値の2つに限定し、併記形（`採用（accepted）`）は受理しない
  - PR 内では表示層の実装後の**独立したコミット**とし、単独で revert 可能に保つ。
- **設計上の論点（未裁定・実装着手時に確定）**: 対訳辞書の配置。本 issue の修正1 は「辞書は
  スクリプト側に1箇所」と書くが、AGENTS.md のスキル自己完結原則（他スキルのファイルを相対参照
  しない）と両立しない。`sdd_report.py` は sdd-core を import しない独立構成のため。
  **推奨案**: sdd-core の `scripts/spec_labels.py` を SSOT とし、sdd-report は同内容の複製を持ち、
  両者の一致を `scripts/release_check.py` が機械検証する。確認観点「訳語変更が1 PR で済む」を
  自己完結原則を破らずに満たせる。
- **裁定（2026-07-21, 人間）— フェーズ対訳の確定**: `bitz-sdd:SI-SDD-020` が main へ land し
  （PR #86 / `SDD-FR-136` verified）フェーズ正規語彙が7語に確定したため、保留していた
  フェーズ行を次のとおり確定する。併記は英語主。

  | phase_code | 表示ラベル |
  |---|---|
  | `map` | `Map（未着手）` |
  | `discovery` | `Discovery（企画）` |
  | `design` | `Design（設計）` |
  | `plan` | `Plan（要件定義）` |
  | `execute` | `Execute（実装）` |
  | `verify` | `Verify（検証）` |
  | `done` | `Done（確定待ち: Promotion Gate）` |

  - **`done` に Gate 名を併記する理由**: `SDD-FR-136` の受入基準に「`done` の表示ラベルは
    Promotion Gate 待ちであることを示す」があり、回帰テストがラベル中の `Promotion Gate` を
    検査している。訳語「確定待ち」だけでは当該条文を満たさないため、辞書の訳語に Gate 名を
    合成して表示する（辞書自体は `done`=`確定待ち` を持つ）。
  - **`promoted` を `正式版` から `確定` に改めた理由（脚注）**: ①`正式版` は文書の版数や
    製品エディションを想起させるが、Promotion Gate が行うのは永続層（`docs/`）への書き戻しと
    feature の畳み込みであり「版」ではない ②フェーズ `確定待ち` → status `確定` で語が連結し、
    Gate の前後関係が表示から読み取れる ③検討過程で挙がった `採用待ち`/`正式採用` は
    spec-issue の `採用`/`不採用` と語族が衝突し、`リリース待ち`/`リリース` は
    `release_check.py`・`docs/05_リリース・運用/` が指す配布の概念と衝突するため不採用。
  - **逆引きの一意性を再確認**: 新語 `確定`（promoted）と `確定待ち`（フェーズ done）は
    文字列として別。フェーズは英語主表記のため正規化入力の対象外で、status 側と競合しない。
- **裁定（2026-07-21, 人間）— 対訳辞書の配置**: 上記「設計上の論点」の**推奨案を採用**する。
  sdd-core の `scripts/spec_labels.py` を SSOT とし、sdd-report は同内容の複製を持ち、
  両者の一致を `scripts/release_check.py` が機械検証する（乖離があれば CI が落ちる）。
  スキル自己完結原則を破らずに「訳語変更が1 PR で済む」を満たすため。
