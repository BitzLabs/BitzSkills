# 調査 — 承認 capability を脅威モデルへ縮退できるか（選択肢 B）

- **日付**: 2026-08-15
- **作成**: claude（`decision-2026-08-15-m0-shipping-surface-and-m2-rescope.md` が
  「A / C 完了後に別途扱う」とした選択肢 B の検討）
- **裁定者**: hide（本書は裁定ではない。争点と選択肢の提示にとどまる）
- **対象**: `FLW-DSN-016` §4 の承認 capability 機構

## 先に訂正

`analysis-2026-08-15-v2-scope-reassessment.md` §4 は
「署名が効く前提の外部鍵保持者を `FLW-CON-005` が scope 外としている」と書いたが、
**これは言い過ぎだった**。`FLW-DSN-016` の脅威モデル節（L729-731）は次を明記している。

> 秘密鍵は可能なら executor と別の owner-only process/keystore へ隔離する。
> **隔離不能なら悪意ある executor への防御を主張せず、単回 nonce・監査 chain・
> 明示承認による事故防止だけを保証する。**

設計は「鍵を隔離できない場合は悪意ある executor への防御を主張しない」と
**自ら claim を縮退させている**。過大な主張はしていない。
したがって B の争点は「設計が嘘をついているか」ではなく、
**「隔離できない配備において、この機構は割に合うか」**である。

## 現況の正確な把握

### 承認判定の内訳

`worktree_capability._authorize_worktree_write()` は9つの検査を順に行う。

| # | 検査 | 暗号に依存するか |
|---:|---|---|
| 1 | capability が存在する | いいえ |
| 2 | `algorithm == "Ed25519"` | **はい** |
| 3 | `key_id ∈ trusted_key_ids` | **はい** |
| 4 | 署名検証 | **はい** |
| 5 | `expires_at` 未経過 | いいえ |
| 6 | nonce 状態が許可集合内（単回性） | いいえ |
| 7 | scope 一致（`operation_id` / dir guard / registry guard / root / case sensitivity） | いいえ |
| 8 | freshness 一致（parent dir identity / nonexistence digest / instance identity digest） | いいえ |
| 9 | operation 別の identity field 整合 | いいえ |

**暗号に依存するのは 2 / 3 / 4 の3つだけ**で、残る6つは平文の比較である。

### 宣言された脅威と、それを閉じている検査

| 脅威（`FLW-DSN-016` L729） | 実際に閉じている検査 |
|---|---|
| 誤操作 | 7（scope 一致）、8（freshness）、9（identity field） |
| 承認再利用 | 6（nonce 単回性） |
| 別 process の取り違え | 7（`operation_id` と guard key の一致） |

**署名（2/3/4）はこの3脅威のいずれにも直接対応していない。**
署名が守るのは「envelope が発行後に改竄されていないこと」であり、
改竄者が鍵を持たない場合にだけ意味を持つ。

### trusted key registry の境界（`FLW-REV-016:RSK-204` の再確認）

レビューは「`apply()` は trusted key を呼び出し側から受け取るだけで、owner-only registry を
mutation 境界で強制していない」と指摘した。実装を確認した結果、**部分的に正しい**。

- `worktree_runtime.apply(..., public_keys: Mapping[str, str], ...)` は
  呼び出し側から鍵を受け取る。`apply()` 自体は registry を読まない
- ただし**公開経路は強制している**。`cli.py:405` が
  `worktree_runtime.load_trusted_keys(plan_value.common_dir)` を呼んでから `apply()` へ渡す
- 鍵を直接注入しているのは `tests/test_flow_m2_runtime.py`（library 直呼び）である

したがって「公開経路に穴がある」わけではなく、**強制が呼び出し側にあり `apply()` 自体は
防御しない**という多層防御上の弱さである。レビューの指摘は API 形状とテストについては正確、
公開経路の含意については過大であった。

### 鍵の所在（現状）

`load_trusted_keys()` が読むのは
`<git-common-dir>/bitz-flow-v2/trusted-worktree-keys.json`（owner-only regular file）である。
**これは被験リポジトリ自身の内部**であり、worktree を書き換えられる主体は同じ
common-dir へも書ける。現状の配備では鍵は executor と同じ信頼領域にある。

## 争点

**隔離された鍵保持者を持つ配備が、現実に存在する（または計画されている）か。**

- **ある**なら、署名は設計どおりの価値を持つ。B は採らず、代わりに
  `apply()` 側で registry を強制する（多層防御の是正）方が筋が通る。
- **ない**なら、2/3/4 は隔離不能な配備における儀式であり、
  維持コスト（鍵生成・registry 管理・fault fixture・例外分類）だけが残る。

### 隔離不能でも署名が持つ弱い性質（steelman）

想定する主体が「悪意ある人間」ではなく **improvise する AI エージェント**である点は、
この判断に固有の事情である。

署名付き envelope は、エージェントが**それらしい JSON を書いて `--capability-file` に渡す**
経路を塞ぐ。鍵が手元にあっても、keygen と署名という明示的な手順を踏む必要があり、
「出力を捏造して先へ進む」失敗モードに対する速度制限になる。
M0 が測定した失敗モード（生コマンドへの迂回・improvise）と同種の防御である。

ただしこの性質は**単回 nonce でも部分的に得られる**。nonce は plan が発行するため、
エージェントが値を捏造しても ledger の `UNUSED` 状態と一致しない。
差が出るのは「plan の出力をそのまま転記して他 field を改変する」経路だけである。

## 選択肢

| 案 | 内容 | 得るもの | 失うもの |
|---|---|---|---|
| **B1 完全撤去** | 2/3/4 と registry・鍵管理を削除し、6/7/8/9 だけで承認を構成 | 維持コストの削減。`SI-FLW-057` の例外分類が扱う面が縮む。fault fixture が減る | 隔離配備への将来の拡張路。plan 転記＋field 改変への速度制限 |
| **B2 条件付き縮退** | 鍵隔離を**前提条件として明文化**し、隔離できない配備では capability の署名を要求しない（nonce＋freshness のみ）。隔離配備では現行どおり | 実態に合う。二重の儀式をやめられる | 2 モードの分岐が増え、どちらで動いているかを result に出す必要がある |
| **B3 維持＋境界の是正** | 署名は維持し、`apply()` 自体が registry を読むよう変更（`RSK-204` の是正）。鍵隔離の手順を運用文書化 | 多層防御が閉じる。隔離配備が実際に機能する | 維持コストはそのまま。B の目的（縮退）を達しない |
| **B4 現状維持** | 何もしない | 変更コスト 0 | `FLW-REV-016` の再発3類型のうち「実体のない層」が残り続ける |

## 推奨

**B2 を軸に検討し、その前提として B3 の境界是正を先に入れる。**

理由:

1. 設計は既に「隔離できないなら claim を縮退する」と書いており、B2 はその方針を
   **実装と result にも反映するだけ**で、設計思想の転換ではない
2. B1 は将来の隔離配備を閉ざす。M3 以降で remote write を扱うとき、
   署名付き承認の器が必要になる可能性がある
3. B3 の是正（`apply()` が registry を読む）は B1/B2 いずれを選んでも無駄にならない

## 裁定に必要な情報（本書では未確定）

- **隔離された鍵保持者を持つ配備の予定があるか**（これが最大の分岐点）
- B2 を採る場合、2 モードの判別を result のどの field で表すか
- B1/B2 の実装規模（未見積もり。`SI-FLW-057` と同じ `apply()` を触るため相互作用がある）
- `FLW-REV-013:GP-002` / `GP-011`（capability 化を求めた前提条件）の再裁定要否

## 参照

- `plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_capability.py`
  （`_authorize_worktree_write` L120-176、`NonceLedger` L180-205）
- `plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py`
  （`apply` L301、`load_trusted_keys` L217）
- `plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py` L405（registry の強制点）
- `plugins/bitz-flow/.spec/design/FLW-DSN-016.md` L729-731（脅威モデル）
- `plugins/bitz-flow/.spec/requirements/FLW-CON-005.md`（人間本人を認証しない前提）
- `plugins/bitz-flow/.spec/reports/analysis-2026-08-15-v2-scope-reassessment.md` §4（本書で訂正）
