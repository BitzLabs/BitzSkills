# 裁定記録 — M2 着手前の設計ギャップ2件

- **日付**: 2026-08-12
- **裁定者**: hide
- **対象**: `SI-FLW-041`（guard identity の拡張）/ `SI-FLW-042`（namespace 表と表記規則）

## 前提: 補強詳細設計は作らない

`FLW-DSN-006`（worktree-first ライフサイクル詳細設計）は active であり、配置と命名・
create / resume の状態遷移・audit 分類8種・finish / discard 手順・検証項目まで揃っている。
M1 で `FLW-DSN-015` を新規に書いたのは多観点レビューで P0/P1 が出たためであり、
M2 は既存設計で足りると判断した。下の2件は既存設計の**不足**ではなく、
**M1 で凍結した契約との接続**の問題である。

## 裁定1 — `SI-FLW-041` guard identity を拡張する

**採用する。** `worktree-dir` と `worktree-registry` を guard identity の閉集合へ追加する。

`worktree.create` / `discard` は directory・worktree registry・branch ref の**3者を同時に**変えるが、
M1 で凍結した閉集合は Git の ref と index だけを対象にしており、前2者を守れない。
`FLW-DSN-006` の `orphan` state（「directory / ref / registry の**一部だけ存在**」）は、
3者を同時に守る guard が無ければ**検出しかできず防げない**。
M1 が commit で「記録なしの重複 write」を構造的に排除したのと同じ扱いを worktree にも与える。

条件:

- **raw path を key にしない**という既存の規律は維持する。`worktree-dir` の key は canonical path を
  digest 化し、symlink・相対 path・case 差・別 clone を正規化して同一 worktree へ収束させる。
- repo 外を指すため、canonical path を提示して apply 前に人間承認を求める既存規定は変えない。
  guard はその承認の**後**に取る。
- 3者は canonical key の昇順でまとめて取得する（既存の昇順取得規約に乗る）。
- enum の**加算**であり既存 key の意味を変えないため、`output-contract.md` の互換性規定に収まる。

## 裁定2 — `SI-FLW-042` 性質ごとの表記規則を明文化する

**選択肢 B を採用する。** 「**状態・判定結果は大文字スネーク、分類・語彙・種別は小文字 kebab**」を
namespace 表へ明記し、worktree state と WorkUnit state を表へ加える（どちらも状態なので大文字スネーク）。

### 根拠（既存 enum 12個の実測）

| 表記 | field | 性質 |
|---|---|---|
| 大文字スネーク | `code` / `write_state` / `intent_record_state` / `gate_status` / `attempt_status` | 状態・判定結果 |
| 小文字 kebab | `cause` / `stage` / `platform` / `credential_class` / `guard_identity_kind` | 分類・語彙・種別 |

この区別は既に一貫して効いている（`trial_kind` の `Q-NORMAL` のみ接頭辞付きの例外）。
`cause`（`not-repository`）と `code`（`INVALID_INPUT`）が同じ result 内で表記を変えているのは
偶然ではなく種類が違うためである。**規則は既に存在しており、明文化されていないだけ**である。

### 却下した案 — 内部値と表示を分ける

「schema は `ACTIVE_CLEAN`、文書と compact 出力は `active-clean`」とする案は**採らない**。

- `SI-FLW-039` の事故は「文書の表記と schema の値が違う」ことで起きた。変換表を持てば、
  その変換表自体が新しい二重定義になり、同型の事故を招く。
- 現状の compact renderer は内部値をそのまま出力しており、**変換層が存在しない**。
  導入すれば renderer に層が増え、両表記をテストで照合し続ける必要が出る。

### 追加で書くこと

複数 namespace に現れる語（少なくとも `planned`）を一覧として明示し、読み手が
「どの namespace の `planned` か」を必ず意識できるようにする。

## 影響

どちらも M0 / M1 で凍結済みの5 namespace の**意味は変えない**。
write は未公開のため外部影響は無い。M2 の契約凍結タスクがこの裁定を前提に schema を作る。
