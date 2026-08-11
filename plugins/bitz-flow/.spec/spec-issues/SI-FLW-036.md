---
id: SI-FLW-036
raised_by: 第13ラウンド claude-code 再実測（2026-08-11）
target: evals/flow-core/m0-eval/run_codex.py の _required_fields / result_code（採点対象の所在と truncation の扱い）
proposed_change_type: modify
status: open
---
- **目的**: 第13ラウンド（claude-code 再実測後）の残る未達2点は、いずれも
  **`_required_fields` / `result_code` の proxy が measurand から乖離**して生じている。
  measurand は「**dispatcher の出力が必須 field を保持していたか**」であるが、
  proxy は「**captured command output の1行目が result envelope である**」かつ
  「**data.items の全 path が出力に現れる**」を前提に置いている。

  | 未達 trial | 実際に起きたこと | 乖離した前提 |
  |---|---|---|
  | `claude-code / v2 / repo-inspect#6`（large） | 呼出は成功し `OK repo.inspect ... branch=main head=09aca6a dirty=true remotes=0` を返した。ただしエージェントが `SKILL_DIR=$(find ...); echo "$SKILL_DIR"; python3 "$SKILL_DIR" repo inspect` と組み立てたため、**1行目が echo したパス**になった | **envelope は1行目**（`output.splitlines()[0]`） |
  | `antigravity / v2 / diff-summary#15`（large） | 1行目は正しい（`OK git.diff-summary snapshot=... files=122 added=121 deleted=120 binary=1`）。出力は `TRUNCATED` 付きで、**省略は契約どおり可視化されている** | **`data.items` の全 path が出力に現れる** |

- **観測**:
  - `result_code()` は先頭行の先頭 token を読むため、`repo-inspect#6` では
    `./.claude/skills/flow-core/scripts/flow.py` を code として読み `None` を返す。
    その結果 **harness 自己診断（`SI-FLW-019` 案3）が「採点対象が非 OK result」を検出した**。
    自己診断は設計どおり機能しており、本 issue はその指摘の中身にあたる。
  - `_required_fields()` の compact 経路（`run_codex.py:478` 以降）は
    `first = output.splitlines()[0]` を使う。JSON 経路（同 474）は
    `not observed.get("truncated", False)` で truncation を明示的に扱うが、
    **compact 経路には truncation の分岐が無い**。そのため
    `all(item["path"] in output ...)` が省略された項目で必ず落ちる。
  - `diff-summary#15` は `truncated: true` / `danger.silent_truncation: false` であり、
    **省略を告げたうえで省略している**。契約違反ではない。

- **提案する修正**:
  1. **envelope の所在を1行目に固定しない。** captured output の中から
     result envelope の開始行（result code 語彙で始まる行）を探して採点対象とする。
     見つからなければ従来どおり不合格とし、**探索したことを観測記録へ残す**。
  2. **compact 経路に truncation の分岐を入れる。** `truncated: true` の出力に対して
     `data.items` の全件一致を要求しない。省略時に検査するのは
     **envelope の集計値（`files` / `added` / `deleted` / `binary` / `total`）と
     `TRUNCATED shown=N total=M` の整合**とし、全件の存在は
     `truncated: false` の trial にのみ要求する。
  3. `FLW-DSN-014` の「proxy が measurand から乖離する条件」表へ
     **必須 field 保持の proxy** を追加する。危険事象4種と `agent_unavailable` は
     すでに列挙したが、**必須 field 保持の proxy は未記載**である。

- **`SI-FLW-019` 原因2 の3度目の再発である**。乖離条件の列挙が
  危険事象4種（`SI-FLW-031` / `032`）→ `agent_unavailable`（`SI-FLW-035`）→
  必須 field 保持（本件）と、**指摘を受けた proxy から順に事後で埋められている**。
  裁定にあたっては「個別に埋める」ではなく
  **採点に使う全 proxy を一度に棚卸しする**ことを検討されたい。

- **対象ファイル**:
  - `evals/flow-core/m0-eval/run_codex.py`（`_required_fields` / `result_code`）
  - `plugins/bitz-flow/.spec/design/FLW-DSN-014.md`（proxy 乖離条件表）
  - `tests/test_m0_eval_scoring.py`（回帰）

- **確認観点**:
  - 第13ラウンドの記録を**再実測せずに**再採点し、当該2 trial が
    必須 field 保持を満たすこと。**満たさないなら被測定物の欠陥として扱う**
  - 全件表示（`truncated: false`）の trial では従来どおり全 path の存在を要求すること
    （省略を口実に検査を緩めない）
  - envelope 探索が、**envelope が本当に無い trial を成功にしない**こと
  - 採点に使う proxy の棚卸し結果が `FLW-DSN-014` に列挙されていること

- **影響推定・ロールバック**: harness の採点に閉じる。配布物
  （`plugins/bitz-flow/skills/`）と v2 fixture、被測定物の挙動には影響しない。
  ただし**採点規則の変更にあたるため、過去ラウンドの再採点で数値が変わる**。
  `scoring_rule_version` と README の対応表で由来を保つこと。

- **依存**: `SI-FLW-019` 案2（proxy の乖離条件。本件はその3度目の再発）。
  `SI-FLW-035`（同じ構図の直前の事例）。`SI-FLW-033`（必須 field 保持の母集団。
  本件は同じ指標の proxy 側）。`FLW-DSN-014`（変更対象）。
