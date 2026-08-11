# Recovery Matrix

失敗 result を安全に契約内へ着地させるための決定表（`FLW-DSN-015`）。
**この表が recovery class 決定の単一の正**であり、実装側へ写経しない（決定器はこの表を参照する）。

## fail-closed の既定

**未登録の tuple、未知 field、code と cause の矛盾は例外なく `human-stop`** とする。
「該当行が無いので安全側の retry」といった暗黙 default を設けない。

## recovery class（閉集合）

| class | 意味 | 許される次の一手 |
|---|---|---|
| `retry-read` | 読み取りをやり直せば収束する | 同一 read operation の再実行 |
| `reconcile-only` | 副作用の有無を read-only で確定させる | postcondition の照合、completed / remaining の確定 |
| `replan-human` | plan からやり直す。人間が新しい plan を承認する | inspect と新 plan の提示 |
| `human-stop` | 自動継続を止める | 空 `next_actions` と `required_human_input` |

`FLW-DSN-010` の復帰原則と同じ閉集合である。

## 決定表

| operation | phase / stage | code・状態 | recovery class | 許可 NEXT | 禁止 |
|---|---|---|---|---|---|
| 全 read | inspect 前 | `INVALID_INPUT` | `retry-read` | 同一 read ＋ 正規化済み候補 | shell、生値 echo |
| 全 write | apply 前 | `STALE` | `replan-human` | inspect、新 plan | apply 自動連結 |
| stage / sync / publish | apply 後 | `PARTIAL` | `reconcile-only` | operation 固有 read reconcile | 残 step 自動 apply |
| 全 write | apply 後 | timeout / output-limit / unclassified | `reconcile-only` | postcondition 最大2回 | command blind retry |
| 全 write | reconcile 不能 | `INDETERMINATE` | `human-stop` | 空 NEXT ＋ 必要な人間入力 | mutation 全般 |
| 全 write | pending / quarantine 既存 | `BLOCKED` | `human-stop` | record 参照、解除証跡提示 | 新 plan / apply |
| 全 write | precondition 競合 | `STALE` | `replan-human` | inspect、新 plan | 旧 operation ID 再利用 |
| commit | object 保存前 | `PENDING_INTENT` | `reconcile-only` | planned OID と object 有無の照合 | commit object blind 再生成 |
| commit | CAS 後 receipt なし | `INDETERMINATE` | `human-stop` | ref / object / intent の read-only 照合 | DONE 推定、再 commit |
| fetch | ref 集合の一部更新 | `PARTIAL` | `reconcile-only` | completed / remaining ref 集合の確定 | fetch 再実行 |
| stage | index digest 不一致 | `STALE` | `replan-human` | index / worktree 再 inspect | 旧 patch apply |
| sync | fetch 済み・branch 未更新 | `PARTIAL` | `reconcile-only` | completed=`fetch`、remaining=`branch-update` の提示 | 自動 branch 更新 |
| publish | remote ref 不一致 | `STALE` | `replan-human` | remote ref 全件再照会、新 plan | force / update 再実行 |

### 行の一意性と優先順位

同一の (operation, phase, code) を持つ行を2つ以上置かない。
`全 read` / `全 write` の行は operation の**既定**であり、同じ code に対して operation と phase が
より具体的な行がある場合はそちらが優先される（例: `sync` の `PARTIAL` は、apply 後の一般行ではなく
「fetch 済み・branch 未更新」の行で解決する）。
具体行と既定行のどちらにも当てはまらない組み合わせは、上の fail-closed 規定により `human-stop` とする。

## next_actions は 1 段ではなくグラフで検査する

返却された 1 段だけでなく、**許可グラフの到達可能性**を検査する。
`PARTIAL` / `STALE` / `INDETERMINATE` から**人間の新しい裁定なしに mutation node へ到達できる**
グラフは不正とする。

安全な候補が無い場合は空の `next_actions` を返し、`stop_reason` と `required_human_input` を添える。
「とりあえず何か提案する」ことを安全性より優先しない。

## 状態の射影

各 write の `PENDING_INTENT` / `MUTATING` / `RECONCILING` は、timeout・出力打切り・応答喪失時に
**必ず上表のいずれかの行へ射影する**。未分類のまま返さない。

## 到達不能な tuple（明示）

暗黙 default に頼らず、到達し得ないことを表として宣言する。

| tuple | 理由 | 代わりに返す状態 |
|---|---|---|
| `commit` × `PARTIAL` | 単一 ref の CAS は原子的であり、部分完了が存在しない | receipt 欠落は `INDETERMINATE` |

到達不能 tuple は schema test で明示的に検査し、決定器が構築しないことを機械判定する。

## 診断に載せてよいもの

失敗診断へ含めてよい入力は**引数名・リポジトリ相対の安全表現・長さ・digest・許容候補**だけである。
絶対 path、URL の userinfo、token pattern、制御文字は出さない（`FLW-FR-013`）。
観測 cause と postcondition は分離して扱い、照合できない場合は `INDETERMINATE` として
target を quarantine し、再 apply を禁止する。
