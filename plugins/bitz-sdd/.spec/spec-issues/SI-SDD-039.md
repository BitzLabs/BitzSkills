---
id: SI-SDD-039
raised_by: bitz-flow v2 Design Gate の GatePassage 起票（2026-07-31）
target: GatePassage の scope が spec-issue ID を解決できず、代行遷移の対象を明示列挙できない
proposed_change_type: modify
status: open
---
- **目的**: `spec_inspect.py` の `check_gate_passages` は GatePassage の `scope` を
  `global_reqs`（`ARTIFACT_DIRS = ("requirements", "discovery", "design", "reviews")` から
  構築されるレジストリ）だけで解決する。**spec-issue は別系統で収集され
  （`.spec/spec-issues/`、委託チェック用。`SDD-FR-132`）`global_reqs` に入らない**ため、
  `scope` に spec-issue ID を書くと幽霊参照として FAIL する。

  一方 `references/lifecycle.md` は、未検分の代行遷移の判定を **`decision_ref` 単位**とする
  理由として「代行遷移は spec-issue の `open → accepted` にも起きており、spec-issue は
  promoted 状態を持たないため」と明記している。つまり **spec-issue は GatePassage が検分する
  対象そのもの**であるのに、`scope` へ列挙できない。

  `references/gates.md` は「`scope` の ID と `confirmed_decision_refs` の参照先は実在検査の
  対象（幽霊参照を許さない）」「対象は `scope` に明示列挙する（feature 単位に固定しない）」と
  規定するが、**列挙できる ID 種別の制限を書いていない**。実装と文書の間に齟齬がある。

  2026-07-31 の bitz-flow で実測した。`FLW-GATE-001`（`gate: design`）の `scope` へ
  Design Gate の対象である `SI-FLW-002`〜`SI-FLW-005` と `FLW-DSN-*` を列挙したところ:

  | scope の ID | 実体 | 判定 |
  |---|---|---|
  | `FLW-DSN-000` / `FLW-DSN-002`〜`014` | `.spec/design/*.md` | 解決される |
  | `SI-FLW-002`〜`SI-FLW-005` | `.spec/spec-issues/*.md` | **「存在しない（幽霊参照）」で FAIL**（4件） |

  回避策として spec-issue を `scope` から外し、備考へ日本語で記述して PASS させた。
  この回避は次の副作用を持つ:

  1. Gate が実際に裁定した対象の一部が**機械可読でなくなる**（GatePassage の目的である
     「人間が裁定した事実を機械可読に残す」が部分的に失われる）。
  2. `spec_status.py` の `unreviewed_proxy_decisions` は `decision_ref` 単位で判定するため
     未検分は 0 件になる。つまり**検分の成立と scope の記載が乖離**し、
     「どの spec-issue がその Gate で検分されたか」を機械では追えない。
  3. 同じ裁定記録を参照する無関係な代行遷移があった場合、それも自動的に検分済みになる。
     `scope` で対象を絞れないため、この過剰検分を検出できない。

- **提案する修正**:
  1. `check_gate_passages` の解決集合へ spec-issue のレジストリを加える。
     `inspect()` は既に `.spec/spec-issues/` を収集しているので、`scope` の解決だけを
     `global_reqs` ∪ spec-issue ID へ広げる（他の幽霊参照検査の解決集合は変更しない）。
  2. モノレポでは他ワークスペースの spec-issue（委託先で起票されたもの）を `scope` に
     書きうるため、`global_reqs` と同様にワークスペース横断で解決するかを裁定する。
  3. `references/gates.md` に `scope` へ列挙できる ID 種別を明記する
     （実装と文書の二重定義を残さないため、どちらか一方を正とする）。
  4. 加法的変更とし、既存の GatePassage（`SDD-GATE-*` 等）が新たに FAIL しないことを先に実測する。

- **対象ファイル**: `skills/sdd-core/scripts/spec_inspect.py`（`check_gate_passages` の解決集合）、
  `skills/sdd-core/references/gates.md`（`scope` の記載規則）、
  `skills/sdd-core/references/lifecycle.md`（代行遷移と GatePassage の対応の記述）、
  `tests/test_spec_inspect.py`（GatePassage の scope 解決の回帰）。

- **確認観点**:
  - 重複: `SI-SDD-038` は `.spec/design/` と `.spec/reviews/` を**発信参照の走査元**へ加える
    issue であり、本 issue は GatePassage `scope` の**解決先**を広げるもので対象が異なる。
    `SI-SDD-014`（workspace 外テスト参照の集計）とも別物。
  - 既存要件との関係: `SDD-FR-155`（GatePassage の必須項目と実在検査）の判定仕様の変更であり、
    `PROJECT.md` の公開契約に触れるため**軽量レーン不適**。
  - ガードレール: 解決集合を広げるだけでは、`scope` に書かれた spec-issue が
    **その Gate で実際に検分されたか**は担保されない。GatePassage は人間が書く不変記録である
    という前提（自動化しない）を崩さないこと。
  - 過剰検分（副作用3）を機械検出まで求めるかは別論点。本 issue では `scope` の表現力回復に
    限定し、`decision_ref` 単位の判定ロジックは変更しない案を推す。
  - 検証: spec-issue ID の解決、他ワークスペースの spec-issue、存在しない ID の FAIL 継続、
    既存 GatePassage の無影響、`spec status` の未検分集計が変わらないことを回帰テストする。
  - 軽量レーン適否: **不適**（`spec_inspect.py` の判定仕様は公開契約）。

- **影響推定・ロールバック**: 変更は `check_gate_passages` の解決集合に閉じ、単独 revert できる。
  2026-07-31 時点で `.spec/gates/` を持つワークスペースは bitz-flow のみ（`FLW-GATE-001`。
  別 PR で追加）で、その `scope` は回避策により設計成果物だけを列挙しているため、
  加法的変更では新たな FAIL が出ない見込み。

- **依存**: なし。`SI-SDD-038` とは独立に実施できる。
  V4 の Promotion Gate（bitz-sdd ROADMAP 順序30）より前に解消すると、
  V4 の代行遷移を GatePassage で正確に列挙できる。

- **予備判定（推薦）**: **accept 推奨**。提案1（解決集合の拡張）と提案3（文書の明記）は
  加法的かつ小さく、GatePassage の設計意図（`lifecycle.md` が spec-issue の代行遷移を
  明示的に対象としている）と実装の齟齬を埋める。提案2（ワークスペース横断解決）は
  モノレポの委託運用に依存するため、`SI-CORE-023` の canonical inspect 規約と
  あわせて裁定するのが安全である。
