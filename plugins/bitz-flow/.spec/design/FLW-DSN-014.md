---
id: FLW-DSN-014
title: "GitHub capability・M0検証設計"
status: active
version: 1.11
updated: 2026-08-11
owner: hide
implements: FLW-FR-003, FLW-FR-008, FLW-FR-012, FLW-NFR-001, FLW-NFR-008, FLW-NFR-004
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
| trialの「答え」 | taskに一致するflow.py呼出のうち、省略が無く**成功した最後のもの**。成功呼出が1件も無ければ不合格とする |
| 呼出の成否 | 出力の**result code**（compact先頭token / JSONの`code`。語彙は`result-v1.schema.json`が正）で判定する。process の exit codeはplatformごとに実体が異なるため採点に使わない |
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
| M2 worktree | 2 PR / 8 session | **2 + 2 = 4 PR** | 14 | repo identity衝突0、repo外承認、finish/discard fault全通過 | M0 read-only prereleaseへ縮退。worktree-first未完了のためM1 Git writeも公開しない |
| M3 Issue/SDD | 3 PR / 12 session | **3 + 3 = 6 PR** | 20 | capability matrix、marker重複0、link reconcile全通過、独立10 Issue/SDD flow canary green | M2までをprerelease出荷し、全`issue.*`を`UNSUPPORTED`にする |
| M4 PR | 3 PR / 12 session | **3 + 3 = 6 PR** | 20 | push/PR/merge各partialから収束、CI/head誤判定0、独立10 PR flow canary green | M3までをprerelease出荷し、全`pr.*`を`UNSUPPORTED`にする |
| M5 Release | 2 PR / 8 session | **2 + 2 = 4 PR** | 14 | changelog atomicity、tag/draft収束後にpublishを段階有効化 | M4までを出荷。release draftだけがgreenならprerelease限定で公開し、publishは`UNSUPPORTED`にする |

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
