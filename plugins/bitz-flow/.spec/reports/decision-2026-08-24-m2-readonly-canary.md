# 裁定記録 — M2 read-only operationの限定公開（canary）

- **日付**: 2026-08-24
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `worktree.doctor` / `worktree.audit` / `worktree.verify-receipt` の公開集合復帰
- **裁定原文**: 「推奨通り b->aで進めましょう」
- **提示済み提案**: `FLW-REV-028`のGate blocking条件`GP-001`〜`008`がすべて消化済みに
  なった一方、7観点の`実証済み`は依然0件である。production E2Eはgatingが続く限り
  **構造的に取得できない**ため、安全性の証明だけを積んでも`実証済み`は増えない。
  read系だけを限定公開すれば「接続完全性」に初めて実証が入り、三度目のレビューの
  材料が実質的に変わる。B（限定公開）→ A（`FLW-REV-029`）の順で進める。
- **記録者**: claude（裁定者の明示指示に基づく代行記録・実行者未検証）

## 裁定

次の**read-only 3 operation**を公開集合（`PUBLISHED_OPERATIONS`）へ戻す。

- `worktree.doctor`
- `worktree.audit`
- `worktree.verify-receipt`

## 公開しないもの（gatedを維持）

| operation | 理由 |
|---|---|
| `worktree.create` / `resume` | Git write を伴う。M2 出口条件の充足前 |
| `worktree.reconcile` | closure event を durable 追記する。`create`/`resume` が非公開である以上、reconcile すべき crash-held marker が生じない |
| `worktree.finish` / `discard` | M3 へ移送済み（裁定 2026-08-15） |

## 限定公開の根拠

1. **persistent write 0件が機械強制されている。** 3 operation はいずれも
   `worktree_operability._read_only_guard` 配下にあり、実行前後の
   `persistent_state_digest` 不変を検査する。変化すれば例外経路でも
   `INDETERMINATE` へ閉じる。受入行`readonly-invariance`に対応する。
2. **Gate blocking条件が消化済みである。** `GP-001`〜`008`（operator action、
   operation deadline、Linux限定、旧形式前提条件、未捕捉例外、symlink実証、
   self-test乖離、mount単位解決）をすべて閉じた。
3. **production E2Eはこれ以外の方法で取得できない。** `FLW-CON-008`が要求する
   「production既定dispatcherを起点とするblack-box」は、公開集合に無い operation では
   原理的に成立しない。`FLW-REV-028`が`実証済み`0件である主因はここにある。
4. **失敗しても状態を壊さない。** read-only であるため、公開して問題が出た場合の
   後退は `PUBLISHED_OPERATIONS` から外すだけで済み、repository state の復旧を伴わない。

## 縮退規則3との関係

ROADMAP フェーズ3の縮退境界は「M0 read-only prerelease へ縮退」であり、解除条件は
M2 出口条件の充足としている。本裁定は**その全面解除ではない**。write class
（M1 local-write、M2 `create`/`resume`）は引き続き非公開であり、公開面は
**read-only のまま**である。したがって縮退規則3の趣旨（write を出さない）は維持される。

ROADMAP の当該記述は「M1 local-write と M2 worktree を**同時に**公開できる」と書いており、
read系のみの先行公開を想定していない。本裁定でその先行を認める。

## 実施後に得るもの

`FLW-DSN-017` §13.1 の行9（audit）・行11（doctor）・verify-receipt が
**production 既定 dispatcher 起点の black-box test** を持てるようになる。
`FLW-CON-008` の 7 観点のうち「接続完全性」に初めて `実証済み` が入る見込みである。

## 後退条件

次のいずれかで直ちに `PUBLISHED_OPERATIONS` から外す。

- read-only 3 operation のいずれかで persistent state の変化が観測された。
- 公開経路で未捕捉例外（traceback）が観測された。
- `FLW-REV-029` が本公開に対して P0 を出した。

## 次工程

公開後に production E2E を取得し、`FLW-DSN-017` §13.1／§13.7 を実測へ更新したうえで、
`FLW-REV-027`／`FLW-REV-028`と同じ5観点で`FLW-REV-029`を実施する。
Promotion Gate は`FLW-REV-029`の判定を経てから判断する。
