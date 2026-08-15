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

## 由来 — なぜ鍵を必要としたのか

**worktree 固有の脅威分析から出た機構ではない。M1 の器を流用したものである。**

`FLW-DSN-016` §4（L328-331）は採用理由をこう書いている。

> M1 の capability envelope（`algorithm=Ed25519` の閉集合、trusted key ID、key generation、
> signed payload、signature）を**そのまま再利用**し、署名対象を worktree 用に定める。
> （中略）これは M1 が quarantine 解除後の mutation に対して既に採っている方式であり、
> **新規機構ではない**。

### M1 では鍵に必然性があった

`FLW-DSN-015`（L248-254）の原型は **quarantine 解除**の文脈である。

> 解除後の mutation には `target, snapshot_digest, prior_operation_id, **reviewer**,
> expires_at, nonce` を署名した単回 authorization capability と新 operation ID を要求する。
> （中略）trusted key registry は **repository owner** が rotation/revocation し…

異常状態を人間（`evaluation-reviewer` / `repository owner`）が検分して解除を承認する
**例外イベント**であり、署名者は executor とは別の役割として設計に明記されている。
この構図では署名は機能する。

### M2 への移植で前提が落ちた

署名対象 field を比べると、移植時に何が失われたかが分かる。

| | M1（`flowlib/intent.py` の `Capability`） | M2（`flowlib/worktree_capability.py` の `WorktreeApprovalCapability`） |
|---|---|---|
| 署名対象 | `target`, `snapshot_digest`, `prior_operation_id`, **`reviewer`**, `expires_at`, `nonce` | guard keys, `parent_dir_identity`, `nonexistence_digest`, `instance_identity_digest`, `worktree_root_canonical`, `case_sensitivity`, `expires_at`, `nonce`, `operation_id` |
| 承認者を名指す field | **あり**（`reviewer`） | **なし** |
| 文脈 | quarantine 解除（例外・人間検分） | 通常の worktree write |
| 鍵の保持者 | repository owner（rotation/revocation する主体） | executor と同じ信頼領域 |

**`reviewer` は移植時に落ちている。** 別の承認者が存在するという前提を表していた
唯一の field が消え、器だけが残った。

### `FLW-REV-011` の指摘を実際に閉じているもの

capability 化を要求した2件について、何が閉じているかを分解する。

| 指摘 | 実際に閉じている機構 | 暗号依存 |
|---|---|---|
| `SYN-002` TOCTOU（承認後の symlink 差し替え・先行占有・root 設定変更） | **2点での再観測**（guard 取得直後・各副作用直前）による `parent_dir_identity` / `nonexistence_digest` / `instance_identity_digest` / guard key の比較。**git・filesystem の観測値比較そのもの** | いいえ |
| `SYN-011` 承認の使い回し | **単回 nonce**（`UNUSED → USED_PENDING` の linearizable CAS） | いいえ |

署名はどちらも直接には閉じていない。署名が固有に足すのは
**「承認者と実行者が別のとき、実行者が承認後に scope を広げられない」**ことだけである。
M2 には承認者を名指す field が無いため、実行者が範囲の広い envelope を再発行すれば足りてしまう。

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

由来を踏まえると、争点は次のように具体化する。

**M2 の worktree write に、`reviewer` に相当する「executor とは別の承認者」を立てる運用を採るか。**

- **採る**なら、M1 が持っていた前提を M2 でも復活させることになり、署名は設計どおりに機能する。
  この場合は B を採らず、`reviewer` 相当 field の復活と、`apply()` 側での registry 強制
  （`RSK-204` の是正）を行う。
- **採らない**なら、署名は「M1 からの流用時に前提が落ちたまま残った器」であり、
  維持コスト（鍵生成・registry 管理・fault fixture・例外分類）だけが残る。

この問いは実装からは判定できない。M2 の worktree 作成・再開を、
**人間または別プロセスが1件ずつ承認する運用**を想定しているかどうかによる。
（M1 の quarantine 解除は例外イベントなので1件ずつの承認が現実的だったが、
M2 の worktree write は通常操作であり、頻度が違う）

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
| **B3 維持＋前提の復活** | 署名を維持し、M1 の `reviewer` に相当する承認者 field を復活させる。あわせて `apply()` 自体が registry を読むよう変更（`RSK-204` の是正）し、鍵隔離の手順を運用文書化する | 移植時に落ちた前提が戻り、署名が設計どおり機能する | 維持コストはそのまま。通常操作を1件ずつ承認する運用負荷が発生する |
| **B4 現状維持** | 何もしない | 変更コスト 0 | `FLW-REV-016` の再発3類型のうち「実体のない層」が残り続ける |

**B1 / B2 は設計の後退ではない。** 由来の節が示すとおり、これらは
「M1 からの流用時に落ちた前提（`reviewer` の不在）を、実装と宣言にも反映する」変更である。
逆に B3 は「落ちた前提を復活させる」変更であり、どちらも一貫した選択肢である。

## 推奨

**B2 を軸に検討する。**

理由:

1. `FLW-REV-011` が要求した2件（`SYN-002` TOCTOU / `SYN-011` 使い回し）は、
   由来の節が示すとおり**再観測と nonce で閉じており、署名は関与していない**。
   B2 は要求を満たしたまま器だけを外す
2. 設計は既に「隔離できないなら claim を縮退する」と書いており、B2 はその方針を
   実装と result にも反映するだけで、設計思想の転換ではない
3. B1 は将来の隔離配備（および M3 の remote write）を閉ざす。B2 なら隔離配備の道を残せる
4. `apply()` 側での registry 強制（`RSK-204` の是正）は B2 / B3 いずれでも無駄にならないため、
   **どちらを選ぶ場合でも先に入れてよい**

M2 の worktree write を1件ずつ人間が承認する運用を採るなら、推奨は **B3** に変わる。

## 裁定に必要な情報（本書では未確定）

- **M2 の worktree write に `reviewer` 相当の承認者を立てる運用を採るか**（最大の分岐点）
- B2 を採る場合、2 モードの判別を result のどの field で表すか
- B1/B2/B3 の実装規模（未見積もり。`SI-FLW-057` と同じ `apply()` を触るため相互作用がある）
- `FLW-REV-013:GP-002` / `GP-011`（capability 化を求めた前提条件）の再裁定要否

## 参照

- `plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_capability.py`
  （`WorktreeApprovalCapability` L34-67、`_authorize_worktree_write` L120-176、
  `NonceLedger` L180-205）
- `plugins/bitz-flow/skills/flow-core/scripts/flowlib/intent.py` L112-125
  （M1 の `Capability`。`reviewer` field を持つ）
- `plugins/bitz-flow/.spec/design/FLW-DSN-015.md` L248-254（M1 の原型と repository owner による鍵管理）
- `plugins/bitz-flow/.spec/design/FLW-DSN-016.md` §4 L317-360（流用の宣言と署名対象表）
- `plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py`
  （`apply` L301、`load_trusted_keys` L217）
- `plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py` L405（registry の強制点）
- `plugins/bitz-flow/.spec/design/FLW-DSN-016.md` L729-731（脅威モデル）
- `plugins/bitz-flow/.spec/requirements/FLW-CON-005.md`（人間本人を認証しない前提）
- `plugins/bitz-flow/.spec/reports/analysis-2026-08-15-v2-scope-reassessment.md` §4（本書で訂正）
