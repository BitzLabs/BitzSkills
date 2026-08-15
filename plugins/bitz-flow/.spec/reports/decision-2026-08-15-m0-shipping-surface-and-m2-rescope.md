# 裁定記録 — M0 出荷面の限定と M2 scope の縮小

- **日付**: 2026-08-15
- **裁定者**: hide
- **対象**: `FLW-REV-016:GP-005`（M2 是正の追加予算再裁定）および V2 の scope
- **提示した材料**: `.spec/reports/analysis-2026-08-15-v2-scope-reassessment.md`
- **提示した選択肢**: A（M0 先行出荷）/ B（capability 縮退）/ C（M2 scope 縮小）/ D（継続）
- **裁定原文**: 「A + C で進めましょう」
  および A の解釈について「出荷面を M0 read-only へ絞る」
- **記録者**: claude（裁定者の明示指示に基づく代行記録・実行者未検証）

## 裁定前に判明した事実（A の意味が反転した）

分析文書 §5 は A を「未出荷の M0 を出荷する」と記述していたが、**これは誤りであった**。
裁定に先立つ実測で、次が確認された。

```
$ python3 plugins/bitz-flow/skills/flow-core/scripts/flow.py worktree audit
OK worktree.audit snapshot=sha256:616e worktrees=1
```

- `flowlib/cli.py` の `PUBLISHED_OPERATIONS` と `_HANDLERS` は
  `worktree.{audit,create,resume,finish,discard}` を含む
- bitz-flow 0.5.12 は `.claude-plugin/marketplace.json` に登録済みである
- したがって**インストールした利用者は、M2 出口 FAIL のまま worktree 操作へ到達できる**
- これは ROADMAP の縮退規則3（「M2 が閉じるまで M1 Git write も M2 worktree も公開しない」）に
  出荷物が違反している状態である
- `FLW-REV-016:SYN-016` が指摘した「`--help` は M0 read-only と書いてあるのに破壊 write が
  公開されている」は、文言のズレではなく**出荷面のズレ**であった

## 裁定

1. **A — 出荷面を M0 read-only へ限定する。**
   `worktree.{audit,create,resume,finish,discard}` を dispatcher の公開集合から外し、
   `UNSUPPORTED` へ戻す。これにより縮退規則3 が出荷物の側で実際に守られ、
   M0 read-only 3 operation（`repo.inspect` / `git.status` / `git.diff-summary`）が
   正しい出荷面になる。安全核の実装は削除せず、ゲート通過時に再公開できる形で残す。

2. **C — M2 の scope を縮小する。**
   `worktree.audit` / `create` / `resume` を M2 の範囲とし、
   破壊系の `finish` / `discard` を **M3 へ移送**する。retention ref・quarantine・
   receipt chain の複雑さの大半は破壊操作に由来するため、M2 が現実的に閉じる形にする。

3. **B（capability の脅威モデルへの縮退）は今回採らない。**
   設計の再裁定を伴うため、A / C 完了後に `FLW-DSN-016` の改訂として別途扱う。

4. Completion Gate は引き続き**保留**。M2 出口条件は新 scope で再定義する。

## 帰結（本裁定から生じる変更）

| 対象 | 変更 |
|---|---|
| `flowlib/cli.py` | 公開集合を M0 3 operation へ限定。`PUBLISHED_OPERATIONS` と `_HANDLERS` の二重定義を SSOT 化（`SYN-016`）。`--help` 文言を実態へ |
| `ROADMAP.md` | 縮退規則3 の現況、フェーズ3 出口条件の縮小、ゲート一覧 |
| `FLW-DSN-014` | M2 出口条件・budget、M3 入口条件（`finish`/`discard` の移送） |
| `FLW-DSN-016` | scope 注記（破壊系は M3） |
| `FLW-REV-016` | `GP-001` を新 scope で再定義 |
| テスト | 公開集合を固定する2件、dispatcher 経由の worktree テスト |

## 未確定（後続の裁定に送る）

- B（capability 縮退）の実施可否と時期
- `SI-FLW-057` / `058` / `059` の accept / reject（C により `057` の一部は M3 送りになる）
- M3 の budget 再校正（`finish` / `discard` の移送分）
