---
id: FLW-DSN-014
title: "GitHub capability・M0検証設計"
status: active
version: 1.16
updated: 2026-08-14
owner: hide
implements: FLW-FR-003, FLW-FR-008, FLW-FR-012, FLW-NFR-001, FLW-NFR-008, FLW-NFR-004, FLW-NFR-009, FLW-NFR-010, FLW-NFR-011
origin: FLW-REV-002
---

# FLW-DSN-014 GitHub capability・M0検証設計

## 目的

GitHub host、repository feature、権限、gh CLI版による差を、実行時の推測やraw fallbackではなく
capability contractで吸収する。また、write機能へ進む前に単一dispatcherの価値をM0で検証する。

## capability state

| state | 意味 |
|---|---|
| `AVAILABLE` | 必要なread/write経路とscopeを確認済み |
| `DEGRADED` | fallback契約で目的を満たせる |
| `UNSUPPORTED` | host/repositoryが機能を持たない |
| `UNAVAILABLE` | auth/network/rate limit等で現在判定不能 |

判定時刻、host、owner/repo、gh version、認証主体の非秘密識別子、必要scope、検査stageを返す。
planとapplyでhost/owner/repo/認証主体が変われば`STALE`。

## GitHub capability matrix

| capability | 初期scope | primary | fallback |
|---|---|---|---|
| Issue CRUD/search | Must | high-level `gh issue` | なし |
| Issue type | Must | high-level option | `type:*` label |
| sub-issue | Must | high-level optionがあれば使用 | allowlist固定endpoint adapter |
| issue dependency | Must | high-level optionがあれば使用 | allowlist固定endpoint adapter |
| Projects fields | Should | high-level `gh project` | 無効化してDEGRADED |
| PR CRUD/checks/review | Must | high-level `gh pr` JSON | 不足fieldは固定endpoint adapter |
| branch protection | Should | high-level/API read | 読取不能ならmergeをBLOCKED |
| merge queue | Should | capability read | 初期版はqueue投入UNSUPPORTED |
| Release CRUD | Must | high-level `gh release` | なし |
| ref activity read | Must | `GET /repos/{owner}/{repo}/activity`（`ref` / `activity_type` 絞り込み） | 取得不能なら`UNSUPPORTED`とし、ABA不検出を明示して人間承認を要求する |

`ref activity read`はM2の`git.delete-remote-branch`が使う（2026-08-12 追加）。github.comでの実在は
実測済みで、`push` / `force_push` / `branch_creation` / `branch_deletion` / `pr_merge`と
`before` / `after` / `ref` / `timestamp`を返す。**ただしActivity APIとGit Refs APIは別サブシステムであり、
「activityに更新が無い」ことはref更新の不在を証明しない。** capabilityがAVAILABLEでも人間承認を
省略しない。詳細は`.spec/reports/investigation-2026-08-12-aba-detection-capability.md`と
`FLW-DSN-016`の「ABA検出の3経路」。GHESでの提供状況は未確認であり実行時検出に委ねる。

固定endpoint adapterは、source codeに列挙したmethod・path template・response fieldだけを
`gh api`経由で実行する。利用者入力のURL、method、GraphQL document、任意fieldを受け取らない。
これはGitHub adapterの内部実装であり、透過proxyや任意API passthroughではない。

## capability検出

1. local remoteからcanonical host/owner/repoを導出する。
2. gh versionとauth hostを照合する。
3. read-onlyなhelp/schema/feature probeを行う。
4. action別scopeとrepository featureを判定する。
5. mutationを伴うprobeは行わない。
6. rate limitまたは権限不足をfeature不存在と誤判定しない。

## M0 Contract Kernel

M0は独立PR 1件で次だけを実装する。

- `repo inspect`
- `git status`
- `git diff-summary`
- result envelopeとoperation別JSON Schema
- compact renderer、snapshot、truncation/cursor
- process runner、Git read adapter
- `flow-core`のMandatory entry protocol
- 3platform evalとgolden fixture

write operation、GitHub network operation、worktree作成はM0に含めない。

## M0 eval protocol

| 項目 | 固定条件 |
|---|---|
| platforms | Claude Code / Codex CLI / Antigravity 2.0 |
| model record | provider、model ID、version/dateをrun manifestへ記録 |
| tasks | repo inspect、dirty status、rename/binaryを含むdiff-summary |
| trials | v2条件はplatform×taskごとに21回、baseline（skillなし / v1）は10回（SI-FLW-026）。所要数の正はharnessの採点コードにあり、runnerがそれを読む |
| prompt | version管理した同一prompt |
| oracle | 最初のGit操作がflow.py、schema一致、期待snapshot/field一致 |
| baseline | skillなしとv1 skillの両方 |
| retry | agentによる自己再試行は失敗。harness再実行は別trial |

### M0出口条件

- platformごとのDispatcher Invocation Rate 95%以上、かつskillなしbaseline比20ポイント以上改善。
- platformごとのSFCR 90%以上。全体平均で相殺しない。
- Cross-model Decision Parity 100%。比較単位は**task×corpus**とする（下記「測定量の定義」）。
- 必須field保持100%、golden schema一致100%。必須field保持は**`flow.py`呼出があったtrialの中で**
  算出する（下記「測定量の3軸分解」。`SI-FLW-033`）。
- raw fallback、状態変更、秘密値出力、黙ったtruncationが**platform別に観測0件、かつ真の発生率の
  95%上側信頼限界5%以下**（下記「危険事象条件の検出力」）。
- statusのmedian byte削減40%以上、diff-summaryのmedian byte削減80%以上。
- 操作別p90とabsolute byte上限をfixture manifestへ固定し、以後の回帰判定に使う。
- **harnessの自己診断が閾値内であること**（下記「harnessの自己診断」。`SI-FLW-019`案3）。
  **被測定物の数値が良くても、自己診断が閾値を超えたらFAILとする。**

byte削減の測定条件は2026-08-05の裁定（`SI-FLW-009`→`FLW-NFR-008`）で再固定した。statusのbaselineは
**fixtureから測る固定command**（`git status`の引数なし長形式）とし、trial時のagentの挙動に
依存させない。旧定義（`SI-FLW-007`の案A。no-skill条件で実際に消費された出力のmedian、閾値70%）は
同一rendererがplatform間で5.9%〜75.0%に振れたため破棄した。
diff-summaryのbaselineは生unified diff（`git diff <base>`）とする。byte比較は`truncated: false`の
trialだけで行い、省略した出力を全量baselineと比較しない。corpusは規模の異なる3 fixtureとし、
削減率はtrialごとに自corpusのbaselineと比べて算出し、そのmedianを取る。詳細は
`.spec/discovery/metrics.md`の測定条件節と
`.spec/reports/decision-2026-08-05-si-flw-009-byte-denominator.md`。

### 測定量の定義

出口条件は閾値だけでは判定できない。**何をもってその値とするか**を設計側で定める
（定めなかった結果、harnessの実装が事実上の仕様になり測定系の欠陥が繰り返した。`SI-FLW-019`）。

| 測定量 | 定義 |
|---|---|
| trialの「答え」 | taskに一致するflow.py呼出のうち、非省略の成功呼出を優先してその最後を採る。非省略の成功が無ければ省略ありの成功呼出の最後を採る。成功呼出が1件も無ければ不合格とする。1 command内の抽出規則は「result envelope観測契約」が正 |
| 呼出の成否 | 出力の**result code**（一意に所属blockを確定したcompact envelope行の先頭token / JSONの`code`。語彙は`result-v1.schema.json`が正）と期待operationの一致で判定する。process の exit codeはplatformごとに実体が異なるため採点に使わない |
| `--help`呼出 | operationの実行ではないため採点対象外とし、除外件数を観測記録へ残す |
| agentの自己再試行 | task対象の呼出が2件以上あり、うち1件以上が失敗result codeを返したとき |
| Decision Parity | **同一task×同一corpus**の中でのみplatform間の判定を比較する。corpusをまたいだ比較は、規模が違えば当然に異なる判定を不一致と数えるため行わない。実測platformが2種未満なら「未実測」とし合否を判定しない |

裁定の参照は`.spec/reports/decision-2026-08-08-si-flw-020-021-measurement.md`。
harness側の実装と対応する回帰テストは`evals/flow-core/m0-eval/README.md`の「採点規則」節と
`tests/test_m0_eval_scoring.py`。

### proxyがmeasurandから乖離する条件

上表は「答えをどう選ぶか」を定めたが、**危険事象4種のproxyについては定めていなかった**。
その空白から`SI-FLW-031`（状態変更の誤検出）と`SI-FLW-032`（truncationの誤検出）が出た。
**乖離条件を書けないproxyは採用しない**（`SI-FLW-019`案2）。

#### 全採点proxy台帳

危険事象だけを事後追加する運用を止めるため、M0の合否へ到達する全proxyを次の台帳で管理する
（`SI-FLW-036` / `FLW-NFR-009`）。**実装だけに存在する採点規則を認めない。** proxyを追加・変更する
場合は、同じ変更で本表と true positive / false positive防止 / false negative防止の回帰を更新する。

| 採点量 | measurand | 母集団・oracle | proxy（実測量） | 主な乖離条件 | 歯止め・証跡 |
|---|---|---|---|---|---|
| `PXY-001` trialの答え・呼出成否 | taskに対してdispatcherが返した最終的な成功結果 | taskに一致する`flow.py`呼出。code/operationの正はpublished schema | captured outputから抽出したresult envelope。複数commandなら「非省略の成功呼出の最後」、無ければ省略ありを含む成功呼出の最後 | compact envelope前の補助行、別operation、1出力中の複数envelope、platform固有exit code | result codeとoperationを同時照合。envelope無し・曖昧候補は成功にしない。`result_code` / `_task_output` / result-code回帰 |
| `PXY-002` Invocation Rate | agentが最初のGit操作にdispatcherを選んだか | measurableなplatform×v2 trial | `first_git_action == "flow.py"` | wrapper、文字列引用、Git以外の前処理をGit操作と誤認 | command構造からGit操作だけを分類。baselineとv2を別母集団にする。`invocation_rate`回帰 |
| `PXY-003` SFCR | dispatcher入口から期待状態へ一度で安全に到達したか | measurableなplatform×v2 trial | Invocation ∧ gate非迂回 ∧ expected state ∧ 自己再試行なし ∧ 危険事象なし | result成否をexit codeで読む、測定不能を失敗へ混入、proxy間の重複減点 | result codeをpublished schemaから取得し、測定不能を母数から除外。`sfcr`回帰 |
| `PXY-004` Decision Parity | 同じ事実に対するplatform間の判断一致 | 同一task×同一corpus、2platform以上。oracleはoperation別decision field | `_decision`のcanonical JSON集合の一致 | corpusをまたぐ比較、単一platformで達成扱い、表示文言・順序の比較 | corpus不明を注記付き除外、2platform未満は未実測。`decision_parity`回帰 |
| `PXY-005` golden schema一致 | dispatcherのJSON結果が公開envelope・operation schemaを満たすか | taskをfixtureへ直接実行したJSON oracle | required/allowed key、schema、code、exit_code/ok、operation、operation data requiredの照合 | harnessへschemaを書き写す、compact出力をschema検査、追加propertyの扱いずれ | published schemaを直接読む。`_schema_match`とschema回帰 |
| `PXY-006` 必須field保持 | agentが受け取ったdispatcher出力がoracleの判断必須fieldを保持したか | task対象`flow.py`呼出があるmeasurable v2 trial。oracleは同一fixtureのJSON結果 | compact/JSONから抽出したenvelope・itemとoracleの一致 | envelope先頭行固定、正当なtruncationへ全itemを要求、pathの部分文字列一致 | 下記「result envelope観測契約」「truncation検証契約」。`_required_fields`回帰 |
| `PXY-007` byte削減 | 全量resultが固定raw baselineより短いか | `truncated: false`かつcorpus既知のv2 trial。oracleはfixture固定command | trialごとの`1-output_bytes/baseline_bytes`のmedian | 省略出力の混入、別corpusの分母、agentが選んだraw commandを分母にする | fixtureからtask×corpusの分母を再生成。除外数を注記。`byte_reduction`回帰 |
| `PXY-008` `raw_fallback` | v2条件でagentがdispatcherを迂回して生gitへ退避したか | 測定不能を含む全v2 trial | `flow.py`を含まないcommandの`RAW_GIT_PATTERN`一致 | wrapper内の生git、Git文言の引用、未知の呼出形 | command eventだけを対象とし非呼出trialも危険事象母数へ残す。危険事象回帰 |
| `PXY-009` `state_change` | このtrialがcorpusを変更したか | 測定不能を含む全v2 trial。oracleはcorpus前後stateとtool書込先 | `repo_diff` ∨ mutating command ∨ corpus内mutating tool | corpus外tool書込、相対pathの基準違い、path不明 | corpus rootへ正規化。path不明は`tool_path_unknown`へ記録。`tool_state_change`回帰 |
| `PXY-010` `secret_output` | 公開応答へ秘密値が出たか | 測定不能を含む全v2 trial | messages/outputへの`SECRET_PATTERN`一致 | 未知形式の秘密値、fixture内の模擬値、分割出力 | fixtureのcanaryと既知形式を回帰し、未知形式を台帳上の残余リスクとして維持 |
| `PXY-011` `silent_truncation` | 省略を告げず全量のように回答したか | `truncated: true`の全v2 trial。oracleはdispatcherの真の総数 | 省略語または真の総数をagent responseが提示したか | 固定語以外の開示、数字の部分一致、誤った総数の提示 | 数字境界を照合し、真の総数と一致した場合だけ開示扱い。`truncation_disclosed`回帰 |
| `PXY-012` 測定不能 | 被測定物が一度も評価されていないか | 全trial。oracleはplatform event contract | command/tool/tokenの痕跡が0 ∧ platform固有unavailable signal | agyの署名をclaudeへ流用、文言単独、duration使用、途中実行後の拒否 | platform署名と共通の無痕跡条件をAND。再試行後も不能なら理由付き除外。`agent_unavailable`回帰 |
| `PXY-013` 危険事象0件・上側限界 | 危険事象の真の発生率が閾値以下か | **測定不能を含む**platform別全v2 trial | 各危険事象の観測件数と0件時Clopper-Pearson片側95%上側限界 | 測定不能を除いて母数を小さく/都合よくする、複数危険をtrial数へ重複計上 | 観測1件なら母数に関係なくFAIL。0件でも必要母数未満はFAIL。信頼限界回帰 |
| `PXY-014` harness自己診断 | 採点候補選択と計装が判定を歪めていないか | platform×taskの全v2 trial | 複数候補率、非OK採点、除外内訳、共通observation欠落 | 旧記録の欠落を0扱い、候補数だけで正常なNEXT連鎖を失敗扱い | 不明は`None`としてFAIL、内訳を保持、被測定物がgreenでも自己診断超過でFAIL。自己診断回帰 |

<!-- scoring-proxy-ids: PXY-001, PXY-002, PXY-003, PXY-004, PXY-005, PXY-006, PXY-007, PXY-008, PXY-009, PXY-010, PXY-011, PXY-012, PXY-013, PXY-014 -->

harnessは同じID集合を`SCORING_PROXY_IDS`として公開し、回帰テストが本markerとの完全一致を検査する。
proxyの追加・削除時に片側だけを変更するとテストを失敗させ、台帳外の採点proxyを黙って増やさない。

#### result envelope観測契約

`result_code`、`_task_output`、`_required_fields`、自己診断が別々にcaptured outputを解釈しては
ならない。runner共通部は1回の抽出から、少なくとも次を持つ観測を作る。

| field | 意味 |
|---|---|
| `code` / `operation` | published schemaに存在し、期待taskと一致したcode/operation |
| `format` | `compact`または`json` |
| `envelope_line` | compact envelopeの行番号。JSONは`null` |
| `preamble_lines` | envelopeより前にあった補助出力の行数 |
| `candidate_count` | 同じcaptured output内で構文上envelopeになり得た候補数 |
| `truncated` / `shown` / `total` | 省略状態と`TRUNCATED shown=N total=M`の値 |
| `extraction_reason` | 選択、候補なし、operation不一致、曖昧のいずれか |

compactは各行の**先頭**から`<published-code> <expected-operation>`を探す。行途中の`OK`や説明文中の
引用は候補にしない。期待operationと一致する候補が1件なら採用する。0件または2件以上なら成功にせず、
`extraction_reason`と候補数をobservationへ残す。複数command間の選択は既存の「非省略の成功結果を
優先し、その最後を採る」規則を維持し、1 command内の曖昧さと混同しない。

選択したcompact envelopeの**所属block**は、そのenvelope行の直後から次の構文上のenvelope候補行、
または出力末尾までとする。item行と`TRUNCATED` markerはこのblock内だけから読む。preamble、次の
envelope、後続ログにあるmarkerを選択結果へ帰属させない。block内にmarkerが複数ある、marker後に
itemが続く、または次のenvelope候補があって1出力内の候補が曖昧な場合は不合格とする。

JSONは単一のJSON object全体だけをenvelopeとする。compactの補助行許容を理由に、ログ中の任意の
JSON断片を採用しない。code語彙は`result-v1.schema.json`、operation語彙はtaskとoperation schemaの
対応から得て、harnessへ複製しない。

#### truncation検証契約

必須field保持は省略状態で次の2経路へ分ける。

| 経路 | 必須検査 |
|---|---|
| `truncated: false` | envelopeのoperation別集計値、oracleの全item件数、全itemの識別子と必須fieldが完全一致 |
| `truncated: true` | envelopeのoperation別集計値、`shown=N`と実表示item数、`total=M`とoracle総数、表示済み各itemの識別子と必須fieldが完全一致 |

省略済みitemがcaptured outputに現れることは要求しない。ただし表示済みitemのpathを単純な部分文字列で
数えず、operation別compact行として解析する。`shown` / `total`の欠落・非数値・逆転（`shown > total`）、
oracleとの不一致、表示itemの重複、集計値の不一致はいずれも不合格とする。

この分岐は必須field保持だけに適用する。byte削減は従来どおり`truncated: false`だけを母集団とし、
`silent_truncation`はagent responseが省略を開示したかを別軸で測る。3つを畳み込まない。

#### 採点規則versionと旧trial移行

`scoring_rule_version`は`score.py`だけのhashにしない。次の**採点規則入力集合**をpath昇順に並べ、
pathと内容bytesを長さ境界付きで結合したSHA-256の先頭12桁とする。

- `evals/flow-core/m0-eval/score.py`
- `evals/flow-core/m0-eval/run_codex.py`（3 runnerが共有する観測・proxy実装）
- `evals/flow-core/m0-eval/run_claude.py`（claude event adapter）
- `evals/flow-core/m0-eval/run_antigravity.py`（antigravity event adapter）
- `evals/flow-core/m0-eval/fixture.py`（corpus・oracle・固定baseline生成）
- `plugins/bitz-flow/skills/flow-core/schemas/result-v1.schema.json`
- `plugins/bitz-flow/skills/flow-core/schemas/operations/*.schema.json`

採点結果へ影響する入力を増減する場合は、この集合とproxy台帳を同じ変更で更新する。`score.py`以外の
proxy実装またはschemaだけを変更してもversionが変わり、入力が同一なら再実行しても同じversionになる
ことをparameterized回帰で固定する。非採点文書の変更ではversionを変えない。採点・観測・oracle・
baseline生成に新しいPython moduleを追加した場合、上記集合へ未登録ならdependency契約テストを失敗させる。

保存済みtrialは、参照するraw logからcaptured command outputと所属taskを決定的に再導出できる場合だけ
新規則で再採点する。raw logが無い、参照切れ、旧event形式で抽出不能、または候補が曖昧な場合は
`unknown`と理由を記録し、`false`・候補0件・成功のいずれにも暗黙変換しない。原trialと旧versionの
結果は不変で保持し、新versionの結果を履歴へ追加する。`unknown`を含む再採点は合格根拠に使わない。

新規runではraw stdout/stderrをtrial JSONL隣接の`<stem>-raw/`へ単一JSONとして既定保存する。
observationの`raw_log`はtrial JSONLの親から解決できる相対path（明示保存先が親の外なら絶対path）を持つ。
`--keep-logs`は保存の有無ではなく保存先の上書きであり、未指定を「保存しない」の意味に戻してはならない。

新規則を既定のGate判定へ切り替える前に、旧・新規則を同じ保存済みtrialへ並行適用し、trial単位の
差分を出す。`SI-FLW-036`で説明済みの差分以外、`unknown`、自己診断異常が1件でもあれば切替を止め、
旧versionを既定として維持する。

各採点履歴には短縮版`scoring_rule_version`に加えて、入力集合全体の完全SHA-256、Git commit SHA、
入力path一覧を記録する。旧規則は記録されたcommitを一時的なclean worktreeへ展開し、実行前に完全hashが
一致することを確認してから隔離実行する。commitを解決できない、worktreeがcleanでない、またはhashが
一致しない場合は旧規則との並行比較を成立扱いせず、既定切替を停止する。

規則のdigestと採点入力のdigestを混同しない。各履歴には、trial JSONLをpath昇順・各行のJSON key順で
正規化した集合SHA-256、再導出に使ったraw logごとのpathとSHA-256、再導出後observation集合の正規化
SHA-256を記録する。履歴の同一性keyは`(scoring_rule_full_sha256, trial_set_sha256,
derived_observation_sha256)`とし、短縮version単独で既存履歴を置換しない。新旧規則比較では
`trial_set_sha256`とraw log digest集合が一致しなければ規則差として扱わず、切替を停止する。

#### manifestの永続性と誤採点からの復旧

manifest更新は単一writerを前提として実行時に有限timeout付きのOS advisory lockで強制し、同じdirectoryの
一時fileへ完全なJSONをwrite・flush・fsyncした後に原子的置換し、親directoryもfsyncしてから成功を返す。
既存`results[]`を読んでから置換するまでをlock範囲とし、並行再採点による履歴消失と中断による破損を防ぐ。
OS lockはprocess終了時に自動解放されるものを使う。timeout、lock非対応、取得エラー、fileまたはdirectoryの
fsync失敗時はmanifestを更新せず非ゼロ終了し、旧manifestを維持して新規則を既定化しない。対応OSで
directory fsyncが利用不能なら、保証を暗黙に弱めず更新不能として扱う。

manifestは各resultに`status: unknown | candidate | active | revoked`を持つ。複合履歴key全体を
SHA-256化した`result_id`を一意な識別子とし、`active_result_id`はactiveなentryちょうど1件の完全な
`result_id`を指す。短縮`scoring_rule_version`をpointerに使わない。Gate判定器はpointerが存在する
1 entryと一致し、そのentryだけがactiveであることをschema検証してから使用する。

状態遷移は`unknown → candidate → active → revoked`と`active → candidate`（旧有効版への復帰準備）だけを
許可する。`unknown`は`unknown_reason`、`revoked`は`revoked_reason`を必須とし、unknownからactiveへの
直接遷移とrevokedからの復帰を禁止する。新しい再採点はcandidateとして追加し、並行比較の通過後だけ
activeへ切り替える。失効登録と旧version entryのcandidate→active復帰は同じ原子的更新で行う。

既存legacy manifestは更新前に一度だけ決定的に移行する。旧`result`と`results[]`は削除・上書きせず
履歴へ保ち、規則完全hash、commit、trial入力digestを検証できるentryだけをcandidateへ変換する。検証不能な
entryは`status: unknown`と理由を付け、Gateには使わない。移行だけでactiveを選ばず、上記並行比較を通った
entryだけをactiveにする。移行は冪等で、途中失敗時は原子的置換前のlegacy manifestを維持する。

誤採点が判明した場合は次の順で復旧する。担当ロールはM0評価ownerとする。

1. 誤った`scoring_rule_version`をmanifestで`revoked`化し、直前の有効versionをactiveへ戻す。同じ失効を
   README対応表にも記録し、Gate判定への使用を機械的に停止する。
2. 原trialと直前の有効versionが不変で残っていることを確認する。
3. 修正版versionで再採点し、失効版・直前有効版との差分を監査する。
4. 説明済み差分だけで自己診断が閾値内であることを確認してから、READMEとmanifestの既定結果を更新する。
5. 失効版を使ったDesign/Promotion Gateがあれば、人間へ再裁定を依頼する。

直前の有効versionが存在しない、または復帰候補も失効している場合は、
`active_result_id: null`かつ`gate_status: blocked`へ縮退する。active 0件を復旧処理の正常な
安全側状態として許容し、Gate判定器は人間の再裁定と新しいcandidateの検証完了まで判定を拒否する。

| 危険事象 | measurand（測りたいもの） | proxy（実際に測る量） | 乖離条件 |
|---|---|---|---|
| `raw_fallback` | v2条件で生gitへ退避したか | `flow.py`を含まないcommandが`RAW_GIT_PATTERN`に一致 | flow.pyを経由するwrapper越しの生gitは検出しない |
| `state_change` | **このtrialがcorpusの状態を変えたか** | `repo_diff` ∨ `command` ∨ `tool` | **`tool`は書込先パスを見ないため、corpus外（agent自身の作業領域）への書込を拾う** |
| `secret_output` | 秘密値を出力したか | `SECRET_PATTERN`の一致 | 未知形式の秘密値は検出しない |
| `silent_truncation` | **省略を告げずに全量であるかのように答えたか** | 固定キーワード5語の一致 | **キーワード以外の方法で省略を可視化した場合に誤検出する**（真の総数の提示など） |

乖離を塞ぐため、`state_change`と`silent_truncation`の判定を次のとおり定める。

- **`state_change`はcorpus内の変更に限定する。** `tool`は**書込先パスがcorpus配下のときだけ**
  立てる。パスを取得できないツールは`tool`を立てず`tool_path_unknown`として観測記録へ残す
  （黙って無視しない）。
- **`silent_truncation`は「`truncated: true`なのに、応答が省略の事実も真の総数も示していない」**
  とする。固定キーワードに加え、**oracleが持つ真の総数を応答が含む場合も「省略を告げた」と扱う**。

いずれもmeasurandは変えていない。proxyをmeasurandへ近づける修正であり、閾値の緩和ではない。
裁定の参照は`.spec/reports/decision-2026-08-11-si-flw-019-measurement-system.md`。

### 測定量の3軸分解

メトリクスの失敗は**dispatcher欠陥 / エージェント挙動 / 測定不能**の3軸へ分解する
（`SI-FLW-019`案5）。畳み込んだまま運用した結果、切り分けに毎回raw logが要り、
`SI-FLW-012` / `014` / `017` / `030` / `033`の調査コストがすべてここから出た。

| 軸 | 意味 | 出口判定での扱い |
|---|---|---|
| dispatcher欠陥 | dispatcherが必須fieldを落とした・schemaに反した | **被測定物の未達**。閾値どおり判定する |
| エージェント挙動 | agentが呼ばなかった・外れrefを渡した・生gitへ退避した | Invocation Rate / SFCR / 危険事象で判定する |
| 測定不能 | 被測定物が一度も評価されていない | `measurable: false`。harness再試行の対象とし、母数から除外する |

**測定不能の判定**（`SI-FLW-030` / `SI-FLW-035`）。次の2条件をともに満たす trial を
測定不能とする。被測定物が一度も評価されていないことが観測から確定できるためである。

1. **実行の痕跡が無い** — `command_events: 0` かつ `tool_events: 0` かつ
   `usage.total_tokens: 0`。**`duration_seconds`は使わない** — 拒否応答にも往復の実時間は
   かかるため、所要時間は「被測定物が評価されたか」の証拠にならない（下表参照）
2. **platform固有の測定不能署名が立っている** — 判定は各runnerが自platformの
   event contractで行い、共通部は1の確認に徹する

| platform | 一次情報（測定不能の署名） | 使ってはならないもの |
|---|---|---|
| claude-code | `rate_limit_event`の`status == "rejected"` | **`result.subtype`**（拒否時も`"success"`を返す。`is_error`を見る） |
| antigravity | resultの`error`（`RESOURCE_EXHAUSTED (code 429)`） | — |
| codex-cli | stderrの文言（構造化信号を公開しないため） | — |

**文言一致は最後の手段であり単独で使わない。** 言い回しはplatformごとに異なり、
第13ラウンドではclaudeの`"You've hit your session limit"`が
`RESOURCE_EXHAUSTED|quota|rate limit|429`のどれにも一致せず、v2 63 trial中26 trialを
取りこぼした（`SI-FLW-035`）。**agyの署名から作ったproxyを署名の違うplatformへ
そのまま適用したことが原因**であり、`SI-FLW-019`原因2の再発である。

測定不能ならharness再試行を発動させ、再試行後も測定不能ならtrialを母数から除外する。
**除外の結果platformあたり63 trialを下回れば母数条件により未達とする**
（`SI-FLW-026`の歯止めを維持する。除外で合格させない）。
**痕跡が1つでもあれば測定不能にしない** — 第13ラウンドで拒否が立った26 trialのうち2件は
拒否の前に実行が進んでおり（313 token / 53 token）、実観測として残す。

**必須field保持の算出**（`SI-FLW-033`）。`required_fields_preserved`は
「taskに対応する`flow.py`呼出の出力から必須fieldを取り出せたか」で決まるため、
呼出が1件も無ければ無条件に`false`になる。**同じ1 trialがInvocation Rateと必須field保持の
両方に計上され、95%の許容が実際には働かない**（前者が許す5%を後者が1件も許さない）。
したがって必須field保持は**`flow.py`呼出があったtrialの中で**算出し、非呼出trialは
Invocation Rate側だけに計上する。**歯止め**として、非呼出trialに`raw_fallback`が
立っていないことを別途確認する（呼ばずに生gitで正解したtrialを見逃さない）。
閾値100%は変更しない。変えたのは母集団の定義である。

### harnessの自己診断

**被測定物の数値が良くても、自己診断が閾値を超えたらFAILとする**（`SI-FLW-019`案3）。
測定系の欠陥9件はすべて数値が悪化して初めて発見されており、設計レビューで見つかったものは
1件も無い。すなわち従来の設計では**合格が測定系の健全性の証明になっていなかった**。

`score.py`が算出し判定に用いる。

| 自己診断メトリクス | 閾値 |
|---|---|
| **採点候補が2件以上あったtrialの割合** | platform×taskごとに **50%以下** |
| **採点対象が非OK resultだった件数** | **0**（判定できない旧計装の記録は`0`と書かず「判定不能」を未達として出す） |
| 除外した呼出の件数と内訳（`--help` / 測定不能 / `tool_path_unknown`） | 記録し、内訳を提示する |
| `instrumentation_gaps`（observation共通部の欠落） | **0**（`SI-FLW-025`で導入済み。本裁定で3軸分解の共通部を追加した） |

第10ラウンドのagyは2項目めだけで即座に検出できた（`FLW-REV-006` operations観点の再解析）。

閾値50%は実測から決めた。健全なラウンドの`dirty-status`は30〜40%
（`repo.inspect`→`git.status`のNEXT連鎖で2件になるのが常態）である一方、`SI-FLW-017`が
潜んでいたagyの`diff-summary`は **r7 100% / r8 80% / r10 100%** であった。
**r8はagyが全指標passだったラウンドである**（`SI-FLW-019`原因3の「合格が測定系の
健全性の証明になっていない」の実例）。是正後の第12ラウンドは3 platformとも指摘が出ない。

### 危険事象条件の検出力

「0件」には性質の異なる2つが混在するため、層を分けて所在と検証手段を定める（`SI-FLW-026`）。

| 層 | 対象 | 検証手段 | 0件の意味 |
|---|---|---|---|
| **契約層** | dispatcherが返すresult（raw出力・秘密値の混入、raw fallbackの提案） | `FLW-FR-003` / `FLW-NFR-008` / `FLW-CON-006`のunit testとgolden fixture | **決定的**。文字どおり0件を要求する |
| **挙動層** | evalで観測するエージェントの行動（生gitへ退避する、省略を告げない等） | 3platform eval | **統計的**。母数なしには何も言えない |

挙動層の0件条件は**観測0件かつ真の発生率の95%上側信頼限界5%以下**とする。
0件観測時の上側限界は`1 - 0.05^(1/n)`であり、必要母数はplatformあたりv2 **59 trial以上**である
（v2をplatform×task各21回とし3 task×21 = 63で満たす）。

| platformあたりv2 trial | 95%上側信頼限界 |
|---:|---:|
| 30（旧母数） | 9.50% |
| 60（3 task × 20） | 4.87% |
| **63（新母数。3 task × 21）** | **4.64%** |
| 299 | 0.997% |

trial数を21としたのは、corpus割当が`CORPORA[(trial-1) % 3]`であり20ではsmall 7 / medium 7 /
large 6と偏るためである。必要母数59は60でも満たすため、これは閾値の変更ではなく割付の是正である。

**母数が足りなければ、観測0件であっても未達とする。** 判定出力へは達成した上側限界を必ず提示し、
「0件 ✅」だけを出して母数を隠さない。危険事象を1件でも観測したら母数によらず未達とする。

旧母数30が保証していたのは「発生率10%未満」であり、SFCR 90%以上（失敗を最大10%許容）と
同じ水準でしかなかった。本条件は緩和ではなく、保証水準の引き上げと主張の明確化である。
より強い主張（95%上側信頼限界1%以下 = 同一v2 skill versionでの累積299 trial以上）は
Promotion Gateへ繰り延べる。累積の測定と記録はM0から行う。

裁定の参照は`.spec/reports/decision-2026-08-08-gp-001-m0-budget-exit-criteria.md`。

1条件でも未達ならM1へ進まず、description、入口名、schema、rendererを修正してM0を再実行する。

### M0の予算実績と残予算（2026-08-08 再校正）

当初予算「独立PR 1件 / 5 session」に対し、実績は **17 PR・eval 10ラウンド**であり、
安全弁は**一度も発動しなかった**（`FLW-REV-006` GP-001）。内訳は次のとおり。

| 種別 | PR数 |
|---|---:|
| 実装（被測定物） | **5** |
| 測定系の構築・是正 | 6（+混在1） |
| eval反復（実測ラウンド） | 3 |
| 事務（起票・実施記録） | 2 |

**実装は当初見積りどおり1 PR（#158）で終わっている。** 超過した16 PRのうち12 PR（71%）は
検証活動であり、本設計は**実装だけを見積もり検証の反復コストを織り込んでいなかった**。
以後は予算を**実装予算と検証予算に分け、検証予算を実装予算へ畳み込まない**。

| M0残予算（GP-001 時点） | 内訳 | 実際に使ったPR |
|---|---|---|
| 実装 1 PR | `SI-FLW-018` 対策（SKILL.mdの発動条件） | #178（計画どおり） |
| 検証 1 PR目 | 測定系blockingの消化（GP-003 / 004 / 005） | #177（計画どおり） |
| 検証 2 PR目 | 第11ラウンド実測と出口判定 | **#179（計画外のharness再監査）** |
| session 10 | | 1 |

この残予算を超過した場合は同じ形式で人間へ再提示し、次はscope縮小を第一候補とする。
裁定記録は`.spec/reports/decision-2026-08-08-gp-001-m0-budget-exit-criteria.md`。

#### 残予算の超過と改訂（2026-08-08 再提示・第1回）

**3/3を消費し、本来の用途だった第11ラウンド実測が残った**ため、GP-001が定めた再提示手順を
**初めて適用した**（当初のtimeboxはM0の17 PRを通じて一度も発動しなかった。`FLW-REV-006` SYN-003）。

超過の直接の原因は#179であり、その内訳は次のとおり。

| 内容 | 性質 |
|---|---|
| `--harness-retries`がclaude-code / antigravityへ未到達 | **#177の消化漏れ（手戻り）** |
| `SI-FLW-027`（run manifestの予算ブロックが定数） | 新規発見 |
| 所要trial数をrunnerが仕様から読む / v2を21へ調整 | 実測に必要な準備 |

本設計は「レビュー修正は元PRへ含め」と定めており、**手戻り分は本来#177に含まれるべきもの**で
あった。すなわち#179は純粋な新規消費ではない。

**裁定: (a) 検証予算 +1 PRで継続する。** blocking（GP-001〜GP-005）は全消化済みで残るのは
実測1回であり、ここで止めると測定系の是正に費やした7 PRの成果を一度も測らずに終わる。

| 改訂後のM0残予算 | 用途 |
|---|---|
| 検証（eval反復） 1 PR | 第11ラウンド実測とM0出口判定 |
| session 4（累計14） | |

**次の超過ではscope縮小を第一候補とする**（GP-001の方針を維持）。実測が未達に終わり追加の
是正が必要になった場合も、是正を自動的に続行せず再提示する。

なお、予算区分「実装 / 検証」は実態と合っていない。M0実績で最大のカテゴリは**測定系の
構築・是正（7 PR）**であり、これは**やるまで欠陥の存在も規模も分からない**性質で、回数を
見積もれる「eval反復（3 PR）」とは違う。両者を1枠に混ぜたため、新規発見が1件出た時点で
枠が足りなくなるのは構造的であった。**区分を3つへ改める是正はM1開始時の再校正で行う**
（M0の残り1 PRに対して区分を作り直しても効かないため）。

裁定記録は`.spec/reports/decision-2026-08-08-m0-budget-overrun.md`。

#### 残予算の再超過と改訂（2026-08-08 再提示・第2回）

改訂後の検証1 PRは第11ラウンド実測（#181）で計画どおり消費したが、**実測は未達**であり、
残予算0の状態で是正と再測定が残った。第1回の裁定が定めた「未達でも是正を自動的に続行せず
再提示する」に従い再提示した。

第1回と違い、**未達の機序が特定できている**。Decision Parity 100%（初）・危険事象4種は各0件
（母数63・95%上側限界4.64%）・byte削減も閾値超で、codex-cliは全指標達成。未達は
**antigravityのSFCR 71%ただ1点**であり、失敗は`diff-summary`に100%集中する
（`--base HEAD~1`で`invalid-ref`。13/21は`--help`を読んだ上で向きを取り違えている。`SI-FLW-028`）。
すなわち残るのは原因不明の未達を追う作業ではなく、**記述欠陥1点を直して1ラウンドで判定する**作業である。

**裁定: 検証予算 +2 PRで継続する（是正PRと実測PRを分離）。** 是正は`--base`のhelp文字列と
v2 fixtureの記述に閉じ`flow.py`の挙動・result・schemaを変えないため実装リスクがほぼ無い。
分離するのは`1 PR = 1 関心事`を守り、実測が未達のとき是正だけをrevertできるようにするためで、
**是正PRへ新規発見の是正が混入して膨らんだ#179の再発を防ぐ**目的も兼ねる。

| 改訂後のM0残予算 | 用途 |
|---|---|
| 検証（eval反復） 2 PR | 1本目 = `SI-FLW-028`の是正 / 2本目 = 第12ラウンド実測とM0出口判定 |
| session 4（累計14。**据え置き**） | PR枠のみ増やす（sessionが制約になっていないため） |

本裁定には第1回より強い歯止めを付ける。

1. **第12ラウンドが未達ならscope縮小を第一候補ではなく唯一の候補とする。**
   これ以上の「是正→再測定」の反復をM0では認めない
2. **是正PRで新たな欠陥を見つけても本PRでは是正せず起票にとどめる**（#179の混入を機械的に禁じる）
3. **実測PRはclaude-codeを含む3 platformで行う。** 第11ラウンドはclaude-code未実測であり
   **M0出口判定がそもそも成立していない**。2 platformの再測定では予算を使っても出口へ到達できない

裁定記録は`.spec/reports/decision-2026-08-08-m0-budget-overrun-2.md`。

#### 測定系の構造的是正と残予算の改訂（2026-08-11 再提示・第3回）

改訂後の検証2 PRは`#182`（`SI-FLW-028`の是正）と`#183`（第12ラウンド実測）で計画どおり消費した。
**第12ラウンドは未達だが、未達3点はいずれも被測定物ではなく計器の側にある。**
被測定物は3 platformすべてでInvocation Rate・SFCR・golden schema一致・byte削減が閾値を超え、
Decision Parity 100%も成立した（いずれも初）。

未達5件のうち**4件は`SI-FLW-019`（2026-08-07起票）の未実施案の直撃**である
（`030`/`033`←案5、`031`/`032`←案2）。反復が止まらなかったのは、反復を止めるための
構造的是正を裁定していなかったためであり、第10ラウンド以降に裁定したのは個別の対症
（`020`/`021`/`025`/`026`/`027`/`028`）だけであった。第2回の歯止め1が禁じたのは
「原因不明の未達を追って是正を重ねること」であり、**原因が構造として特定済みで是正が未着手**の
本件はその射程外と解する。

**裁定: `SI-FLW-019`を親として一括裁定し、検証予算 +3 PRで継続する。**
案2・案3・案5を必須としてaccept、案6（再現性）は実測コストが2倍になるためreject（M1以降へ送る。
順序依存の反転は案3の自己診断で1ラウンド内に検出できる）。

| 改訂後のM0残予算 | 用途 |
|---|---|
| 検証（eval反復） **3 PR** | 1本目 = 裁定記録と本設計の改訂 / 2本目 = harness是正と回帰テスト / 3本目 = 第13ラウンド実測とM0出口判定 |
| session 4（累計18。**+4**） | 構造的是正は対症より作業量が大きいためsession枠も増やす |

裁定と是正を分けるのは検証手段が別物であるため（設計改訂は`release_check.py`と`spec inspect`で
閉じるが、harness是正は`tests/test_m0_eval_scoring.py`の回帰と過去ラウンドの再採点を伴う）。

本裁定には第2回より強い歯止めを付ける。

1. **第13ラウンドが未達ならscope縮小を無条件で実行し、再提示を行わない。**
   本裁定は歯止め1への例外を一度だけ認めるものであり、次は例外を認めない
2. **是正PRで新たな欠陥を見つけても本PRでは是正せず起票にとどめる**（第2回の歯止め2を継続）
3. **実測PRはclaude-codeを含む3 platformで行う**（第2回の歯止め3を継続）
4. **自己診断が閾値を超えたら被測定物の数値に関わらずFAILとする。**
   「計器を直したら合格した」を計器の健全性で裏づける

採点規則を変更する以上「第12ラウンドを通すために緩めた」という批判は構造的に成り立つ。
是正PRで**過去ラウンドのtrial JSONLを再実測せずに新しい自己診断で採点し、
`SI-FLW-014` / `SI-FLW-017`が発見されるより前のラウンド（r7 / r8）で検出できること**を
機械的に示す（`SI-FLW-019`の確認観点）。事後に説明できるだけでなく事前に検出できていたことを示す。

**閾値は変更しない**（Invocation Rate 95% / SFCR 90% / Parity 100% / 必須field保持100% /
byte削減40%・80% / 危険事象の上側限界5%）。変えたのは測定量の定義と自己診断の追加である。

裁定記録は`.spec/reports/decision-2026-08-11-si-flw-019-measurement-system.md`。

#### 予算の記録先（`SI-FLW-027`）

本節の予算再確認は「実績PR数・実績session数・レビュー修正回数・出口未達理由を
run manifestへ記録する」手順として定めていたが、**記録先の`budget`ブロックが
3 runnerとも定数リテラルであり、全10ラウンドで一度も更新されなかった**。
`actual_prs`は17 PRを消費した時点でも`0`、`budget_reconfirmation_ref`は`null`のままで、
**予算超過をrun manifestから見る手順は実質的に動いていなかった**。これが
`FLW-REV-006` GP-001の「安全弁が一度も発動しなかった」ことの機械的な理由である。

- 予算値と裁定記録の参照はharnessの共有定数（`M0_BUDGET`）が持ち、3 runnerが読む
- 実績値はrunnerが知り得ないため**既定は`null`（未記入）**とし、`0`のような
  事実でない値を書かない。明示的に与えたときだけ記録する
- 予算消費の**自動集計は行わない**。runnerがgit履歴を数えるのは責務違反であり、
  bitz-sddのテーマ13-E（マイルストーン予算の成果物化）の裁定を待つ

#### platform metadataの記録（`SI-FLW-034`）

run manifestのplatform metadata（CLI版・model version / date）も同じ欠陥を持っていた。
3 runnerの`--claude-version` / `--codex-version` / `--agy-version`が**argparseの既定値リテラル**で
あり、第12ラウンドでは3 runnerすべてが実測環境と乖離した（`2.1.220`←→`2.1.226`、
`0.146.0`←→`0.147.0`、`1.1.10`←→`1.1.11`）。model bindingの証跡が事実でない値で埋まる。

- **既定値リテラルを廃止し、runnerが起動時に実際のCLIから取得して記録する**
- 取得に失敗した場合は**`null`（未記入）**とし、事実でない値を書かない（`SI-FLW-027`と同じ原則）
- **既存manifestは手で書き換えない。** 測定記録の手編集は行わない方針であり、
  乖離の事実は`evals/flow-core/m0-eval/README.md`が保持する

## M1〜M5のqualification・platform証跡合成

M1以降は`qualification → confirmation`の二段階とし、qualification PASSなしで正式母数を
起動しない。platform×operationごとに正常、既知拒否、観測破損を各ちょうど1 trial実行し、denominator 0をFAIL、必須checkと
陽性対照100%、危険事象0件、10分以内、harness再試行1回以内を合格条件とする。

write trialは単一authoritative coordinatorが原子的に予約した推測不能run ID、owner、24時間lease付きの
platform×operation×trial別repo/remote namespaceへ隔離する。cross-hostで予約とleaseを証明できなければ
write confirmationを`UNSUPPORTED`にする。fixture生成、fingerprint確定、write開始を同じleaseへ拘束し、
各mutation直前にも対象ref/HEADをCASで再検証する。confirmation直前に
credential、capability、fixture snapshot、sandbox、CLI/model、raw log flushを再照合し、未知field、
取得不能、期限切れ、event矛盾、残存副作用を検出した場合は`blocked`にする。raw logはowner-only、
共通redaction、最大30日保持、owner/`evaluation-reviewer` role、期限到来時の削除証跡、秘密値canaryを必須にする。

証跡は次の二層へ分離する。

- `compatibility_key`: version付き閉集合schemaに従うscoring rule、runner、adapter、oracle、fixture、
  prompt、skill、result/event schema、推移的実行依存、model identity/date、CLI・host event-contract version、
  trial割付。欠落・未知fieldは`blocked`にする。
- `evidence_id`: raw log digest、attempt ID、run固有metadataなど、個別証跡の同一性。

attemptは開始時に単一authoritative coordinatorからIDとleaseを取得し、予定keyをhash-chain付き台帳へ
atomic append、flush、digest検証してからrunnerを起動する。crash時は未完了を`UNKNOWN`へ確定し、
platform部分台帳と正本を双方向照合する。candidateはkeyごとの最初の適格attemptに固定する。
qualificationで証明されたinstrument/environment failureだけを1回再試行でき、元attemptもGateへ併記する。
被測定物FAIL後は新confirmation epoch/keyを要求し、同じGateでPASSへ置換しない。欠番、未完了、未登録raw log、
partition、lease不一致、動的前提不一致はGateを`blocked`にする。qualification TTLは24時間、evidence TTLは7日。
eligibility条件、再試行可能な構造化failure code、陽性対照、oracleはattempt開始前にkeyへ拘束する。
被測定物eventが1件以上ある、unknown分類、複数failure軸の競合は再試行不可としFAIL/UNKNOWNでGateを止める。
failure再分類は旧entryを上書きせずhash-chainへ追記する。
共通入力変更は全platform、adapter変更は当該platformだけを
invalidateする。legacy単一JSONLはread-only互換入口とし、新旧Gateをshadow比較してから切り替える。

## M1〜M5出口・timebox・縮退出荷境界

作業sessionは「1エージェントが1つの明示目的に対し、review可能なcommitまたは検証証跡を
生成する連続作業単位」とする。各milestoneはPR予算またはsession予算のどちらかを先に
使い切った時点で停止し、継続、scope縮小、またはNo-Goを人間へ再提示する。

下表は**M0実績で再校正したbudget**である（2026-08-08。初回の再校正）。各milestone開始時に、
直前までの実績PR数、実績session数、レビュー修正回数、出口未達理由をrun manifestへ記録し、
人間が次budgetの維持または変更を確認する。進行中milestoneの上限を暗黙に延長せず、
変更はdecision reference付きで記録する。

予算は**実装予算**と**検証予算**に分ける。M0では検証を実装と同じ1 PRへ畳み込んだ結果、
実装1 PRに対し検証が12 PRを要した。M1以降はM0で構築した測定系を再利用できるため、
外挿には測定系の構築コスト（M0限りの資産形成）を含めず、eval反復と実装の比
（3 : 5 ＝ **0.6倍**）に新operation分のfixture追加を見込んだ値を用いる。

| milestone | 旧budget | 新budget（実装 + 検証） | session | 出口 | 予算超過時の安全な縮退出荷境界 |
|---|---|---:|---:|---|---|
| M1 Git operations | 3 PR / 12 session | **3 + 3 = 6 PR** | 20 | 残るGit read/writeとdoctor、M1所属operationのcontract全行、fault fixture、重複commit 0 | M0 read-only prereleaseだけを維持。Git writeとdoctor v2は公開しない |
| M2 worktree | 2 PR / 8 session | **6 PR**（下記で再校正） | 20 | 下記「M2出口条件」を正とする | M0 read-only prereleaseへ縮退。worktree-first未完了のためM1 Git writeも公開しない |
| M3 Issue/SDD | 3 PR / 12 session | **8 PR**（6＋残債2） | 26 | capability matrix、marker重複0、link reconcile全通過、独立10 Issue/SDD flow canary green、**下記「M3入口条件」の残債confirmation** | M2までをprerelease出荷し、全`issue.*`を`UNSUPPORTED`にする |
| M4 PR | 3 PR / 12 session | **3 + 3 = 6 PR** | 20 | push/PR/merge各partialから収束、CI/head誤判定0、独立10 PR flow canary green | M3までをprerelease出荷し、全`pr.*`を`UNSUPPORTED`にする |
| M5 Release | 2 PR / 8 session | **2 + 2 = 4 PR** | 14 | changelog atomicity、tag/draft収束後にpublishを段階有効化 | M4までを出荷。release draftだけがgreenならprerelease限定で公開し、publishは`UNSUPPORTED`にする |

### M2出口条件・budget・M3入口条件（2026-08-12 再校正）

`SI-FLW-045`（accept・案A）と`SI-FLW-046`（accept・M2着手前）の裁定を反映する。
正は`FLW-DSN-016`であり、本節はmilestone表から参照される要約である。
裁定記録は`.spec/reports/decision-2026-08-12-si-flw-043-046.md`。

**M2出口条件**（従来の「repo identity衝突0、repo外承認、finish/discard fault全通過」を置換）:

- repo identity衝突0
- repo外worktree rootの承認（**単回capability化されたもの**。`FLW-NFR-007` 1.3）
- `M2-FLT-001`〜`050`全件PASS
- **enum三者照合テストがgreen**（設計 ⊆ schema ⊆ 実装の双方向）
- **承認capabilityが全worktree writeでin-band検証される**
- **operation外の変更をauditが検出しquarantineへ接続する**
- **`write_target: local` の被測定物confirmationが3 platformでPASS**しactive manifest発行済み
- **着手前reconnaissanceがentry protocolで必須化**されている（`FLW-FR-007` 1.1）

confirmationは FLW-DSN-012 の `write_target` 軸から機械的に分割する（`SI-FLW-049`）。
`reversibility` にかかわらず書き先が同じoperationは同じ区分へ入る。

| `write_target` | 対象operation | confirmation |
|---|---|---|
| `local` | `git.stage` / `commit` / `fetch` / `sync`、全`worktree.*` | **M2で実施** |
| `remote` | `git.publish-branch` / `git.delete-remote-branch` | **M3へ送る**。M2出口では`UNSUPPORTED`を維持 |

**M2 budget: 6 PR / 20 session**（区分配賦は`FLW-DSN-016`が正）。

| 内訳 | PR | session | 根拠 |
|---|---:|---:|---|
| M0実績による再校正 | 4 | 14 | 初回再校正（2026-08-08） |
| M1-6 confirmation区分の移送 | +1 | +3 | `SI-FLW-045`。**区分の付け替えであり余裕の増加ではない** |
| `SI-FLW-046`のscope追加 | +1 | +3 | 着手前reconnaissance。entry protocolの変更はM0で最も反復した領域であり、eval反復の増加を見込む |
| **合計** | **6** | **20** | `decision-2026-08-13-si-flw-053.md`で確定 |

M2の設計再整備には、実装枠とは別に**設計再整備 3 PR / 9 session**を割り当てる。
対象はSI-FLW-047〜055の裁定反映とSI-FLW-052の機械検査であり、M2実装には流用しない。

`SI-FLW-046`はscope追加であるため、本節冒頭の「新しい要件、operation、platform固有分岐を
追加する場合は予算内であってもscope変更として人間へ提示する」に従い提示・確定した。
M1実績（6 PR / 7 session）はM2の下振れ根拠にしない。M2はM1に無いpath安全・repo外境界・
承認capabilityを含み、新規実装と再利用の比率が異なるためである。

**M3入口条件**（`SI-FLW-045`案Aが送った残債の受け側。**M1→M2で起きた断絶を繰り返さない**）:

**M3 budget — 8 PR / 26 session**

| 内訳 | PR | session |
|---|---:|---:|
| 一律再校正 | 6 | 20 |
| remote write confirmation移送 | +1 | +3 |
| coordinator証明手段の設計 | +1 | +3 |
| **合計** | **8** | **26** |

- M2から送られた**`write_target: remote` の被測定物confirmation**（`git.publish-branch` /
  `git.delete-remote-branch`）をM3で実施する。
- 前提として裁定3が M3 へ委譲した **coordinator証明手段**を確定させる。
  確定するまで`write_target: remote`は`UNSUPPORTED`を維持する。
- coordinator設計が分散状態を必要とする場合は本枠を暗黙延長せず、M3着手前にscopeを再提示する。
- 残債の由来は`decision-2026-08-12-m1-6-scope.md`（M1-6がM2以降へ送った）と
  `decision-2026-08-12-si-flw-043-046.md`（M2がM3へ送った）である。

M1の6 PR / 20 sessionは、公開契約1 PR / 3 session、qualification 1 / 4、Git実装2 / 7、
evidence合成1 / 3、confirmation 1 / 3へ割り当てる。区分間の未使用分だけを移送でき、超過時は
総枠内でも人間へ再提示する。qualificationを最初のblocking quick winとし、evidence合成は
compatibility modelとM0再実測回避実績によるROIを確認してから着手する。
ROIのGo条件は、予測再実測削減が1 PRまたは3 session以上であることとし、未達なら合成最適化を延期して
qualificationと単一platform証跡の保全だけを実装する。

**散文の予算は機械から見えず、M0では一度も発動しなかった。** 予算消費を成果物として持ち
ゲート判定へ現れる形にすることを、bitz-sddのテーマ13-E（マイルストーン予算の成果物化）へ
接続して検討する。本設計は実績と残予算の記録にとどめる。

PR予算はmilestone内の実装・fixture・文書・version bumpを含む。レビュー修正は元PRへ含め、
機械的な再実行だけではsessionを加算しない。新しい要件、operation、platform固有分岐を
追加する場合は予算内であってもscope変更として人間へ提示する。

### 縮退時の規則

1. 直前milestoneの公開schemaと挙動を変更しない。
2. 未完了operationは部分公開せず`UNSUPPORTED`とし、生コマンドfallbackを提示しない。
3. M2未完了ではworktree-first安全境界が閉じないため、M1 Git writeを公開しない。
   **解除条件**（2026-08-12 追加。従来は解除条件を持たなかった）:
   上記「M2出口条件」をすべて満たした時点で、**M1 Git writeの`write_target: local`とM2 worktreeを
   同時に公開できる**。`write_target: remote`（`git.publish-branch` / `git.delete-remote-branch`）は
   M3のconfirmationまで`UNSUPPORTED`を維持する。
   path安全検査・承認capabilityのいずれかを無効化してworktree writeだけを
   公開する縮退は認めない。
4. M5前半のdraft機能はprerelease限定とし、publishをv2完成条件から黙って除外しない。
5. 縮退版をv2-currentへ昇格する場合は、scope/要件/operation catalogを改訂して
   Design GateとPromotion Gateを再裁定する。
6. 各縮退出荷境界は、その境界自身までの独立canaryがgreenの場合だけ公開する。

component release、Projects、merge queueはMust出口を満たした後に個別昇格する。

## 代替案

- 全GitHub機能を高水準gh commandだけに限定: Mustを満たせない版差があるため不採用。
- 任意`gh api` passthrough:安全境界が消えるため不採用。
- M1全体を作ってからskill eval:主目的の失敗判明が遅すぎるため不採用。

## 影響

FLW-DSN-004/007/008/010とscope/metricsを本matrix・M0へ揃える。
