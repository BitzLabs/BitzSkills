# レビュー台帳の照合記録（SI-FLW-091）

- **日付**: 2026-08-24
- **起点**: `FLW-REV-027`「過去9レビューの未解決P0/P1が機械台帳上88件ある一方で、
  後続レビューは`PASS`判定を出している」
- **記録者**: claude
- **実装**: `FLW-TSK-122`（`tests/test_flow_review_ledger.py`）

## 実測して分かったこと

**`carried_over`の生成そのものは正しかった。** `FLW-REV-027`の88件は、先行レビューの
未解決（`open`／`tracked`）P0/P1と**完全に一致**しており、欠落も余剰も0件だった。

したがって本 issueの実体は「台帳が壊れている」ではなく、**「台帳が正しいことを
検査する仕組みが無い」**である。生成器がずれても、`carried_over`から未解決項目が
落ちても、誰も気づかず緑のままになる。

## 実施した照合

**機械的に証明できるものだけ**を`resolved`へ遷移させた。証跡は実在するschema・testを
名指ししている。

| finding | 優先度 | 指摘 | 解消の証跡 |
|---|---|---|---|
| `FLW-REV-018:SYN-005` | P1 | `ORPHAN`／`quarantine`／`recovery_class`がresult schemaの閉集合外で、enum三者照合の対象外 | `worktree_state`／`release_class`を含む12 namespaceが`FLW-CON-007`の三者照合対象。指摘対象の`ORPHAN`は値ごと廃止 |
| `FLW-REV-019:SYN-003` | P1 | `cause="quarantined"`が実装定数にだけあり公開schemaに無い | `result-v1.schema.json`の`cause` enumに登録済み。`tests/test_flow_contract_vocabulary.py`が設計表・schema・実装の三者一致を機械検査 |

`carried_over`は **88 → 86** へ減った。

## 照合しなかったもの（86件）と、その理由

残る86件は`tracked`または`open`のまま据え置いた。**憶測でresolved化しない。**
これは`FLW-REV-027`が指摘した過大主張そのものになるためである。

内訳と据え置きの理由は次のとおり。

- **70件は今回の是正（`FLW-TSK-115`〜`121`）と話題が重ならない。** 予算、
  measurement system、Issue駆動フロー、squash運用など、M2 Local Safety Profileの
  外側の指摘である。後続レビューがPASSを出したのは**当時のscopeに対してPASS**で
  あって、これらを解消したからではない。
- **16件は話題が重なるが、個別に証跡照合が必要。** 例えば
  `FLW-REV-016:SYN-004`（raw logをdigest化直後に破棄）は、証跡保存の実装を
  確認しないとresolvedと言えない。1件ずつ実体を当たる作業であり、
  本taskの範囲（台帳の機械検査の確立）とは別に行う。

## 導入した機械検査

`tests/test_flow_review_ledger.py`（8種・75 test）。

1. 最新レビューの`carried_over`が未解決P0/P1と**厳密一致**すること（欠落・余剰の双方）。
2. `carried_over`のIDが実在する findingを指すこと。
3. `status`が既知の語彙（`open`／`tracked`／`resolved`）であること。
4. `tracked`の`tracked_by`が実在するspec-issueまたはgate preconditionを指すこと。
5. `resolved`が実在する証跡（`resolved_by`）を名指しすること。
6. `status` field導入前の記録（`schema_version`なし）は免除するが、
   **その免除がP0/P1を隠していないこと**を別途検査する。

変異検査で次の4件が検出されることを確認した。

- `carried_over`から未解決を1件落とす
- **証跡なしでresolved化する（台帳を綺麗に見せる）**
- 実在しないspec-issueを`tracked_by`にする
- 実在しない証跡でresolved化する

## 残件

86件の個別照合は未了である。`FLW-REV-027`のGate blocking条件は
「`SI-FLW-091`で過去P0/P1台帳を再照合し、未解決項目を欠落させていないこと」であり、
**欠落させないこと**は本taskの機械検査が保証する。個別の解消判定は、
対応するscopeの作業を行うときに証跡付きで行う。
