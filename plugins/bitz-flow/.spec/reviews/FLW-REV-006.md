---
id: FLW-REV-006
title: "M0 eval 測定系の多観点レビュー"
status: pending
version: 1.0
updated: 2026-08-07
owner: hide
decision: FAIL
---

# 設計レビュー統合レポート — M0 eval 測定系

- **review_id**: FLW-REV-006
- **対象**:
  - `.spec/design/FLW-DSN-014.md`（M0 検証設計・出口条件）
  - `.spec/requirements/FLW-NFR-008.md` / `FLW-NFR-002.md`（byte 削減・情報保持）
  - `.spec/discovery/metrics.md`（成功指標と測定条件）
  - `.spec/reports/analysis-2026-08-07-m0-measurement-system.md`（全10ラウンド再解析の検討書）
  - `.spec/spec-issues/SI-FLW-017.md` / `018` / `019` / `020` / `021`
  - `evals/flow-core/m0-eval/score.py` / `run_codex.py` / `run_claude.py` / `run_antigravity.py` / `fixture.py` / `README.md`
- **判定**: **FAIL**
- **集計スコア**: 2.42（PASS ≥ 3.5 / CONDITIONAL_PASS ≥ 2.5）
- **判定の意味**: 被測定物（bitz-flow の dispatcher と SKILL.md）ではなく、**それを測る仕組み**に対する
  判定である。測定系が現状のままでは M0 出口の合否を根拠づけられない。

## 観点別スコア

| 観点 | スコア | 重み | 主要所見 |
|---|---:|---:|---|
| consistency | 2.65 | 0.15 | SSOT と宣言された FLW-DSN-014 だけが破棄済み裁定を参照。Parity 実装が定義と docstring の双方に反する |
| data-integrity | 2.40 | 0.25 | 一次証拠である trial 記録に schema が無く、observation の構造が3 runner で異なる |
| operations | 2.70 | 0.20 | 計測器自身を監視する指標が出口条件に無く、恒常 FAIL が10ラウンド背景化した |
| risk | 2.00 | 0.25 | 計測器の fail-silent 経路（agy の exit_code）。0件条件に対し母数が2桁不足 |
| business | 2.55 | 0.15 | 閾値の定量化と裁定記録は良好。timebox の安全弁が一度も発動していない |

findings: 統合前 38 件 → 重複排除後 21 件（P0: 3 / P1: 6 / P2: 4 / P3: 8）

## P0 — Blocker

- **SYN-001** [RSK-201, RVC-301, DIN-202, RSK-205] 計測器が沈黙して失敗する — agy の `exit_code` が flow.py の失敗を構造的に検出できない
  - **場所**: `run_antigravity.py:_commands` ほか3 runner の `exit_code`
  - **問題**: `exit_code` の実体が runner ごとに違う（codex=実値 / claude=Bash tool の error flag / agy=出力文字列の marker 判定）。
    flow.py の `INVALID_INPUT ... cause=invalid-ref stage=inspect`（実 exit 2）はどの marker も含まないため、
    agy は常に 0 と記録する。実測で agy は v2 条件の 242 回の flow.py 呼出に対し非ゼロを一度も記録しておらず、
    一方で byte 長から同定すると diff-summary だけで 38 回 INVALID_INPUT を受けている。
    結果、(1) 採点対象が失敗 result になった trial が r7 / r10 で計3件、
    (2) `self_retried` が agy で構造的に永久 false となり SFCR が過大評価、
    (3) Parity を等価でない計装の上で比較、という3つの帰結が同時に生じている。
  - **是正**: 判定を compact 出力の先頭トークン（`result-v1` の `code` enum 11 値）から行い、
    platform の event contract に依存させない。agy のヒューリスティックは撤去して `None` とする。
    marker 文字列を増やす方向は採らない（code 語彙が増えるたびに腐り、同じ沈黙経路を再生産する）。
  - **追跡**: `SI-FLW-020`

- **SYN-002** [RVC-201, BIZ-102] Cross-model Decision Parity が corpus をまたいで判定を比較し、第1ラウンドから達成不能だった
  - **場所**: `score.py:decision_parity` ↔ `discovery/metrics.md:Input Metrics`
  - **問題**: metrics.md は Parity を「**同じ fixture の**判定コード・状態変更が3プラットフォームで一致する割合」と定義し、
    score.py の docstring も「**同じ fixture・同じ task で**」と書いているが、実装は task 単位でのみグループ化し corpus を落としている。
    trial は small / medium / large に散っているため `changed=8` と `changed=34` と `changed=124` が「不一致」として数えられる。
    全10ラウンドで FAIL を出し続けたが、どの spec-issue にも起票されていない。
    (task × corpus) でグループ化すると r7 / r8 / r10 いずれも **9/9 = 100%** である。
  - **是正**: グループ化キーへ corpus を加える。FLW-DSN-014 の出口条件へ測定単位を明記する。
    判定が実際に食い違う trial を混ぜたら 100% を割ることを確認し、修正が恒真にならないことを検証する。
  - **追跡**: `SI-FLW-021`

- **SYN-003** [BIZ-401, BIZ-402] 設計自身が定めた M0 の timebox を桁違いに超過しながら安全弁が一度も発動していない
  - **場所**: `FLW-DSN-014:M0出口条件（末尾）` / `M1〜M5 timebox 節`
  - **問題**: FLW-DSN-014 は「M0 は独立PR 1件」とし、「5回の作業session または 1PR で出口に到達しない場合は
    scope/pivot を人間へ再提示する」と安全弁を定めている。実績は #158〜#171 の **14 PR**、実測 **10ラウンド**、
    セッション上限への到達2回であり、予算を1桁超えている。timebox 節自身も「進行中milestoneの上限を
    暗黙に延長せず、変更は decision reference 付きで記録する」と定めるが、暗黙の延長がまさに起きている。
    M0 が 1 PR 想定に対し 14 PR を要した実績は、M1（3 PR / 12 session）以降の budget も
    非現実的である可能性を強く示唆するが、記録も再校正もされていない。
  - **是正**: 予算超過を人間へ正式に再提示し、(a) 予算改訂して継続 / (b) scope 縮小 / (c) 出口条件見直し
    のいずれかを decision reference 付きで裁定する。予算消費を run manifest から集計し超過時に警告する。
    なお本レビューの再解析は「測定系を是正すれば残る不合格は実質1事象」であることを示しており、(a) の材料は揃っている。
  - **追跡**: `FLW-REV-006:GP-001`

## P1 — Must Fix

- **SYN-004** [RVC-202, BIZ-101] SSOT と宣言された FLW-DSN-014 だけが破棄済みの裁定を参照し、要件・実装・discovery の三者と矛盾する
  - **場所**: `FLW-DSN-014:M0出口条件（byte削減の測定条件の段落）`
  - **問題**: metrics.md は「M0の…出口条件の完全な正は FLW-DSN-014 とする」と宣言する。
    ところが FLW-DSN-014 本文は「statusのmedian byte削減 **70%** 以上」と、2026-08-05 に破棄された
    SI-FLW-007 の分母定義を保持している。FLW-NFR-008 は固定 baseline・**40%**、score.py も 40%。
    frontmatter の `implements` だけが更新され本文が取り残されており、更新漏れの検出機構が無い。
  - **是正**: 本文を FLW-NFR-008 へ追随させ version を上げる。要件 supersede 時に、それを implements する
    設計文書の本文を更新対象として列挙する手順を裁定記録テンプレートへ組み込む。
  - **追跡**: `FLW-REV-006:GP-002`

- **SYN-005** [RSK-202] 採点対象の選択が呼出順のみで決まり、合否が偶然に左右される
  - **場所**: `run_codex.py:_task_output`（`selected = (complete or matches)[-1]`）
  - **問題**: 正解を得たあとの探索的呼出が最後に来ると、その失敗結果が答えとして採点される。
    r10 の agy は 10 trial 中 8 trial で `--base HEAD~1` を実行しており、差は成功呼出の前か後かだけ。
    SI-FLW-017 は「第10Rで表面化」としたが、再解析では **r7 でも 1 件発生**しており、
    r8 は INVALID_INPUT 呼出 7 件がありながら偶然すべて成功呼出より前に来ていた。
  - **是正**: SI-FLW-020 へ統合し result code ベースの選択にする。
    **SI-FLW-017 の推奨案1（`exit_code == 0` を優先）は agy では全 exit_code が 0 のため無効**であり、
    そのまま採ると「修正したのに直らない」結果になる。全呼出が失敗した trial は引き続き不合格とする歯止めを残す。
  - **追跡**: `SI-FLW-020`

- **SYN-006** [RSK-203, BIZ-201] 「危険事象 各0件」が n=30 では検証不能で、測定可能な目標値になっていない
  - **場所**: `FLW-DSN-014:M0出口条件`
  - **問題**: rule of three により 0/30 が保証するのは真の発生率10%未満まで。真の発生率3%でも0件になる確率は40.1%。
    SI-FLW-018 の生 git 直行は claude 累計約210 trial で1件（≒0.5%）であり、この条件の検出力の外側にある。
  - **是正**: 必要 n を確保する（95%で3%を検出するなら99 trial）か、
    「95%上側信頼限界が x% 未満」へ書き換える。数値を通すための緩和ではなく
    **検証不能な条件を検証可能な条件へ置き換える**趣旨を、byte 閾値再校正（SYN-021）と同じ論法で裁定記録へ残す。
  - **追跡**: `SI-FLW-019`

- **SYN-007** [RSK-204, DIN-201] 裁定で置いた歯止めが codex-cli でしか効いておらず、その事実がデータ構造上検出できない
  - **場所**: 3 runner の `observation` 辞書
  - **問題**: `_task_output` は `common` 共有だが observation は各 runner が個別に構築している。
    SI-FLW-012 の `empty_output_positions` / `task_output_missing`、SI-FLW-014 の `help_invocations` は
    run_codex.py にのみ存在する。集計側は `t.get(key, default)` で吸収するため
    「記録されていない」と「記録されたが偽」が区別されない。
  - **是正**: observation を共通部と platform 固有部に分け、共通部を3 runner が必ず書く。
    集計側は共通部の欠落をエラーとする。歯止め field の存在を自己診断項目に含める。
  - **追跡**: `FLW-REV-006:GP-003`

- **SYN-008** [RSK-401, OPS-401, DIN-101, RVC-102] 採点規則の変更が過去の判定を遡って書き換えるが、規則バージョンの記録もロールバック手順も無い
  - **場所**: `score.py:main（--manifest 書き込み）` / `run-manifest-*.json`
  - **問題**: `manifest['result'] = report` は破壊的更新であり、どの規則で出た判定かを保持しない。
    採点規則は SI-FLW-009 / 012 / 014 で3度変わり、SI-FLW-020 / 021 でさらに変わる。
    ラウンド間の数値比較（第8R 100% ↔ 第10R 93.3%）を議論の根拠にしている以上、比較の前提が保存されていない。
  - **是正**: run manifest へ採点規則バージョン（score.py の内容ハッシュ）を記録し、`result` を履歴として積む。
    規則変更 PR では影響ラウンドを再採点し新旧を並記する。README にラウンド×規則の対応表を置く。
  - **追跡**: `FLW-REV-006:GP-004`

- **SYN-009** [RSK-402] per-call の出力テキストが保存されておらず、事後の切り分けが byte 長の近似に頼る
  - **場所**: trial 記録（`observation.task_flow_output_bytes`）
  - **問題**: 第1ラウンドの反省で `--keep-logs` を追加したが保存先はリポジトリ外であり、
    trial は byte 長のみを持つ。本レビューも INVALID_INPUT の同定を byte 長で行わざるを得ず、
    diff-summary（OK 最小220B vs INVALID 63〜64B）は分離できたが、
    **repo-inspect（OK 99B vs INVALID 61B）は分離できず件数を確定できなかった**。
  - **是正**: per-call の result code（先頭トークン）を配列で保存する。
    全文を保存しなくても、code 列があれば本レビューの再解析はすべて厳密に実行できる。
  - **追跡**: `FLW-REV-006:GP-005`

## P2 — Should Fix

- **SYN-010** [RVC-101] FLW-DSN-014 に measurand の定義節が無く、実装が事実上の仕様になっている。
  「測定量の定義」節を新設し、採点対象の選択規則・除外規則と歯止め・proxy の乖離条件を仕様側へ置く。
  **乖離条件を書けない proxy は採用しない**。追跡: `SI-FLW-019`
- **SYN-011** [OPS-101, OPS-102] 計測器の健全性を監視する指標が出口条件に無く、恒常 FAIL が10ラウンド背景化した。
  「採点候補が2件以上あった trial の割合」「採点対象が非 OK result だった件数（0であるべき）」
  「除外した呼出の件数と内訳」を計測し、被測定物の数値が良くても閾値超過なら FAIL とする。
  判定出力を前ラウンドとの差分（新規／継続中／解消）で提示する。追跡: `SI-FLW-019`
- **SYN-012** [DIN-301, DIN-302, DIN-203, OPS-402] 一次証拠である trial 記録に schema が無く機械検証されていない。
  被測定物の result は schema 検証されているのに計測データが検証されていない逆転を解消する。追跡: `FLW-REV-006:GP-007`
- **SYN-013** [OPS-201] 再採点で検証できる修正と再実測が要る修正が区別されておらず、限りある実測予算を浪費する。
  SI-FLW-020 / 021 はいずれも再採点で検証できるため、次の実測ラウンドの前に消化する。追跡: `FLW-REV-006:GP-006`

## P3 — Consider

- **SYN-014** 単一 platform の部分実測でも Parity が算出され未達に数えられる（2 platform 未満は「未実測」とする）
- **SYN-015** `SECRET_PATTERN` の有効性が未検証で、秘密値 0 件が fail-silent と区別できない（陽性対照を入れる）
- **SYN-016** `status: draft` の metrics.md が測定条件の照合元として運用されている（解釈を文書内へ自己記述する）
- **SYN-017** 「oracle」が合否条件と期待値生成器の2つの意味で使われている
- **SYN-018** byte 削減が安定して閾値を満たす FLW-NFR-008 が `implementing` のまま（先行 verified 化の可否を裁定）
- **SYN-019** 【良好】baseline を fixture から再現する設計により旧 trial も同じ定義で採点できる（一般則へ昇格を推奨）
- **SYN-020** 【良好】corpus の trial 単位分離が trial 間干渉を構造的に塞いでいる（不変条件を明記して自己診断へ）
- **SYN-021** 【模範的】byte 閾値の再校正が原理的根拠を伴い、閾値を通すための分母選択を明示的に排除している

## Gate 通過前に消化する条件（blocking）

`gate_preconditions` のうち `kind: blocking` は5件で、いずれも `basis: verified`（実測で確認済み）である。

- [ ] **GP-001** M0 の予算超過を人間へ再提示し、継続 / scope 縮小 / 出口条件見直しを decision reference 付きで裁定する
- [ ] **GP-002** FLW-DSN-014 本文を FLW-NFR-008 へ追随させる（70% → 40%・固定 baseline）
- [ ] **GP-003** observation の共通部を `common` へ引き上げ3 runner で必須化する
- [ ] **GP-004** run manifest へ採点規則バージョンを記録し、規則変更時に新旧を並記する
- [ ] **GP-005** trial 記録へ per-call の result code を保存する

`kind: agenda`（Gate で決める論点）は GP-006（再採点／再実測の区分）と GP-007（trial schema の範囲と時期）。

## 補足 — 測定系を是正したときの第10ラウンド

本レビューの根拠となった再解析（`.spec/reports/analysis-2026-08-07-m0-measurement-system.md`）によれば、
測定系を是正すると第10ラウンドの不合格は **`claude-code / diff-summary / medium / trial 2` の 1 事象**に収束する。
この 1 trial が必須 field 落ち・raw_fallback・SFCR/Invocation の減点を同時に起こしている。
すなわち `SI-FLW-018` の生 git 直行が、M0 出口を塞いでいる唯一の実質的な事象である。

ただし `self_retried` の是正（SYN-001）により agy の SFCR は**下がる可能性がある**。
これは過大評価の是正であって退行ではないが、確定値は harness 修正後の再採点で得る必要がある。

## 人間への裁定依頼

この判定は推奨です。Design Gate / Promotion Gate の裁定、および
`SI-FLW-017` の `SI-FLW-020` への統合、`SI-FLW-018` / `019` / `020` / `021` の accept / reject は、
上記を確認のうえ人間が行ってください。
