# codex（OpenAI）による起票計画レビュー — 2026-08-25
## 総合判定: 却下

現案は、既知の2欠陥を再発防止 canary にする点では有効ですが、3回連続した根本原因を止める仕組みにはなっていません。

中心命題である「変異義務が証拠能力を包含する」は、今回の実測で既に反証されています。`UNSUPPORTED → BLOCKED` 変異では、振る舞いテストは通った一方、ファイル指紋テストだけが失敗しています。つまり source／指紋テストでも mutant は kill できます。[FLW-REV-030](/home/inoue332/BitzLabs/BitzSkills/plugins/bitz-flow/.spec/reviews/FLW-REV-030.md:38)

## Findings

### P0 — 変異 kill と証拠能力は別の性質

「1件以上のテストが失敗」を合格条件にすると、次も kill として数えられます。

- source文字列・ファイル指紋・内部定数の照合
- import／collection error
- 構文を壊した無効 mutant
- timeout、クラッシュ、無関係な flaky failure
- 公開APIを通らない内部helperの assertion

実際、問題の receipt テストは製品の `verify_receipt()` ではなく、同じ判定式を `_chain_is_valid()` に再実装しています。[問題のテスト](/home/inoue332/BitzLabs/BitzSkills/tests/test_flow_m2_judgement_quality.py:73) と [公開API実装](/home/inoue332/BitzLabs/BitzSkills/plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_operability.py:350)

したがって次の2ゲートを独立に必要とします。

1. evidence admissibility：公開API/CLIを実行し、振る舞いを観測したか
2. mutation assurance：許容される証拠が mutant を kill したか

mutation は証拠能力の代替ではなく、補強証拠です。

### P0 — curated 台帳は同一主体の盲点を閉じない

台帳は「登録済み mutant の検出」を保証できますが、「登録すべき mutant の欠落」は検出できません。

今回有効だった順序は、外部レビュアーが欠陥仮説を発見し、その後に変異で確証する流れでした。[FLW-REV-030](/home/inoue332/BitzLabs/BitzSkills/plugins/bitz-flow/.spec/reviews/FLW-REV-030.md:60)

提案にはこの独立発見工程がありません。必要なのは次の順序です。

1. 実装者とは独立したレビュアーが判定点・欠陥仮説を列挙
2. 公開経路テストを作成
3. targeted mutation で確証
4. 統合判定前に再度 second opinion
5. 指摘をローカルで再現してから採用

curated 台帳だけでは未知の欠陥を発見できません。

### P0 — 「安全判定」の適用境界が機械収集不能

FLW-CON-008 は `implements: FLW-CON-008` から対象を動的収集し、対象0件もFAILさせます。[FLW-CON-008](/home/inoue332/BitzLabs/BitzSkills/plugins/bitz-flow/.spec/requirements/FLW-CON-008.md:35)

FLW-CON-009案には同等の閉包がありません。「安全判定」を自然言語だけで定義すると、危険な判定を台帳へ登録しないだけで対象外になります。

先に機械可読な judgement inventory が必要です。最低限、次を持たせます。

- stable judgement ID
- requirement ID
- production callable
- public entrypoint
- 入力分割
- 公開される code／cause／action
- hazard class
- admissible test ID
- curated mutant ID

対象0件、公開判定の未登録、孤児test／mutantをFAILさせる必要があります。ただし marker 自体の付け忘れは完全には機械検出できないため、inventory completeness は独立レビュー対象として残します。

### P0 — 共有作業ツリーのバックアップ復元は危険

このリポジトリは共有作業ツリーへの並行作業を前提としています。[AGENTS.md](/home/inoue332/BitzLabs/BitzSkills/AGENTS.md:62)

対象ファイルを直接変更してバックアップから戻す方式は、SIGKILL、CIキャンセル、runner crash、別セッションの同時編集で次を起こし得ます。

- mutant が残留する
- 他セッションの変更をバックアップで上書きする
- 後続pytestが変異済みsourceを読む

REV-030自身も harness 事故を受けて使い捨てcloneを採用しています。[FLW-REV-030](/home/inoue332/BitzLabs/BitzSkills/plugins/bitz-flow/.spec/reviews/FLW-REV-030.md:72)

原本を一切変更せず、mutantごとに一時コピー／使い捨てcheckoutで実行してください。hardlinkは不可、各実行はfresh Python process、開始前後に原本hash不変を確認します。

### P1 — test範囲の自己申告は、証拠ではなく最適化情報

範囲を狭くすること自体は問題ではありません。同じnodeidがbaselineでPASSし、mutant時に意図したassertionでFAILするなら強い証拠です。

問題は、台帳の自由記述をそのまま信頼する点です。runnerは最低限、次を区別すべきです。

- baseline PASS
- collected test > 0
- mutantがちょうど1箇所へ適用された
- 指定した公開経路が実行された
- assertion failure → `KILLED`
- survive → `FAIL`
- collection/import error、timeout、signal、0 test → `BLOCKED`
- 復元後または隔離環境の再baseline PASS

testファイルではなく exact nodeid／judgement marker／coverageから実行対象を導出し、台帳の `expected_killers` は診断情報に留めるのが妥当です。

### P1 — runner自身への変異は循環している

壊れたrunnerが自分自身を「正常」と報告する可能性があります。

runner自身への変異を主根拠にせず、独立したfixture projectからblack-boxテストしてください。fixtureには少なくとも以下が必要です。

- 必ずkillされるmutant
- 必ずsurviveするmutant
- baseline red
- patch 0件／複数件一致
- collection error
- timeout／process crash
- mutant適用確認
- 原本hash不変
- JSON/JUnit receiptの内容

### P1 — 1要件への統合は片直りを防がない

証拠能力、mutation infrastructure、独立レビューは検証方法と責任主体が異なります。単一 `verification_method: unit-test` では外部レビュー工程を検証できません。

また、2 issueを独立裁定するのに「裁定後は必ず1要件へ統合」では、片方だけacceptedになった場合が未定義です。

推奨は次です。

- FLW-CON-009：公開経路に基づく証拠 admissibility
- FLW-CON-010：judgement inventory と mutation assurance
- 外部レビュー順序：Gate process条件
- 同じGateで両要件をAND評価して片直りを防止

### P1 — Design Gateに設計成果物がない

JSON schema、隔離方式、kill分類、timeout、CI、receiptは設計判断です。FLW-GATE-007を置くなら、先に runner／registry design を作り、要件と設計の両方をscopeへ含める必要があります。

現案の「要件だけをscopeにしたDesign Gate」は不足です。

## curated と生成型の比較

結論は hybrid です。

- curated：`UNSUPPORTED → BLOCKED` のようなドメイン固有の禁止丸め込みに強い。一方、作者の選択バイアスを共有する。
- generated：条件反転・比較演算子・return値などを機械列挙し、選択バイアスを減らす。一方、同値mutant、実行費用、複数moduleにまたがる意味変異が残る。

mutmut は対象testの自動選択、incremental実行、並列実行を備えますが、現行3系は関数外コードを変異しないため、`_AUDIT_ACTIONS` のようなmodule-level mappingを取りこぼします。またfork対応環境が必要です。[mutmut公式ドキュメント](https://mutmut.readthedocs.io/en/latest/)

Cosmic Ray はoperator pluginで拡張でき、timeoutとsession管理を備えますが、local実行はsourceを直接書き換えるため隔離コピーが必須です。[Cosmic Ray concepts](https://cosmic-ray.readthedocs.io/en/latest/concepts.html)、[公式tutorial](https://cosmic-ray.readthedocs.io/en/latest/tutorials/intro/index.html)

どちらを採るかは未検証です。まず対象2moduleへ10〜20 mutantのspikeを行い、生成数、実行時間、invalid／equivalent／survivor率を測るべきです。

## 修正版の計画

1. 既知2件の公開API／CLIテストを先に修正し、使い捨て環境で手動mutationをkillする。
2. safety judgementの機械定義、inventory、admissible kill契約を設計する。
3. SI-FLW-093／094を依存付きで起票し、片方だけacceptedの場合も裁定する。
4. generated toolの小規模spikeを実施する。
5. 証拠能力とmutation assuranceを別要件にする。
6. runner／registry／隔離／CIを扱う設計成果物を作成する。
7. 独立レビュー後に、両要件と設計をscopeとするDesign Gateを通す。
8. タスクを最低4件へ分割する。

   - 公開APIテスト＋既知2 canary
   - judgement inventory＋admissibility検査
   - isolated runner＋black-box fixture
   - generated mutation＋専用CI job＋診断artifact

9. 統合判定前に外部レビュアーが新しい判定点またはmutant候補を最低1件提示する。
10. 既知curated mutant 100% kill、generated survivorの裁定、通常pytest、`release_check.py`、spec inspectをすべて通してGP-002を閉じる。

mutation runnerは通常pytestへ再帰的に埋め込まず、専用required CI jobにするのが安全です。現CIはpytestとrelease checkだけで、mutation用依存・timeout・artifactがありません。[CI設定](/home/inoue332/BitzLabs/BitzSkills/.github/workflows/ci.yml:29)

## 見積り

現見積りは根拠不足で、特にTSK-133の1 sessionは過小です。

暫定値は以下ですが、すべて未検証です。

- 既知test是正：0.5〜1 session
- inventory／admissibility／runner設計：1〜2
- isolated runner＋black-box検証：2〜4
- generated tool／CI統合／survivor整理：1〜3
- 外部再レビュー：0.5〜1

合計は概ね5〜10 sessionです。tool spike後に再見積りしてください。

レビューは読み取り専用で実施し、ファイル変更は行っていません。
173,262
## 総合判定: 却下

現案は、既知の2欠陥を再発防止 canary にする点では有効ですが、3回連続した根本原因を止める仕組みにはなっていません。

中心命題である「変異義務が証拠能力を包含する」は、今回の実測で既に反証されています。`UNSUPPORTED → BLOCKED` 変異では、振る舞いテストは通った一方、ファイル指紋テストだけが失敗しています。つまり source／指紋テストでも mutant は kill できます。[FLW-REV-030](/home/inoue332/BitzLabs/BitzSkills/plugins/bitz-flow/.spec/reviews/FLW-REV-030.md:38)

## Findings

### P0 — 変異 kill と証拠能力は別の性質

「1件以上のテストが失敗」を合格条件にすると、次も kill として数えられます。

- source文字列・ファイル指紋・内部定数の照合
- import／collection error
- 構文を壊した無効 mutant
- timeout、クラッシュ、無関係な flaky failure
- 公開APIを通らない内部helperの assertion

実際、問題の receipt テストは製品の `verify_receipt()` ではなく、同じ判定式を `_chain_is_valid()` に再実装しています。[問題のテスト](/home/inoue332/BitzLabs/BitzSkills/tests/test_flow_m2_judgement_quality.py:73) と [公開API実装](/home/inoue332/BitzLabs/BitzSkills/plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_operability.py:350)

したがって次の2ゲートを独立に必要とします。

1. evidence admissibility：公開API/CLIを実行し、振る舞いを観測したか
2. mutation assurance：許容される証拠が mutant を kill したか

mutation は証拠能力の代替ではなく、補強証拠です。

### P0 — curated 台帳は同一主体の盲点を閉じない

台帳は「登録済み mutant の検出」を保証できますが、「登録すべき mutant の欠落」は検出できません。

今回有効だった順序は、外部レビュアーが欠陥仮説を発見し、その後に変異で確証する流れでした。[FLW-REV-030](/home/inoue332/BitzLabs/BitzSkills/plugins/bitz-flow/.spec/reviews/FLW-REV-030.md:60)

提案にはこの独立発見工程がありません。必要なのは次の順序です。

1. 実装者とは独立したレビュアーが判定点・欠陥仮説を列挙
2. 公開経路テストを作成
3. targeted mutation で確証
4. 統合判定前に再度 second opinion
5. 指摘をローカルで再現してから採用

curated 台帳だけでは未知の欠陥を発見できません。

### P0 — 「安全判定」の適用境界が機械収集不能

FLW-CON-008 は `implements: FLW-CON-008` から対象を動的収集し、対象0件もFAILさせます。[FLW-CON-008](/home/inoue332/BitzLabs/BitzSkills/plugins/bitz-flow/.spec/requirements/FLW-CON-008.md:35)

FLW-CON-009案には同等の閉包がありません。「安全判定」を自然言語だけで定義すると、危険な判定を台帳へ登録しないだけで対象外になります。

先に機械可読な judgement inventory が必要です。最低限、次を持たせます。

- stable judgement ID
- requirement ID
- production callable
- public entrypoint
- 入力分割
- 公開される code／cause／action
- hazard class
- admissible test ID
- curated mutant ID

対象0件、公開判定の未登録、孤児test／mutantをFAILさせる必要があります。ただし marker 自体の付け忘れは完全には機械検出できないため、inventory completeness は独立レビュー対象として残します。

### P0 — 共有作業ツリーのバックアップ復元は危険

このリポジトリは共有作業ツリーへの並行作業を前提としています。[AGENTS.md](/home/inoue332/BitzLabs/BitzSkills/AGENTS.md:62)

対象ファイルを直接変更してバックアップから戻す方式は、SIGKILL、CIキャンセル、runner crash、別セッションの同時編集で次を起こし得ます。

- mutant が残留する
- 他セッションの変更をバックアップで上書きする
- 後続pytestが変異済みsourceを読む

REV-030自身も harness 事故を受けて使い捨てcloneを採用しています。[FLW-REV-030](/home/inoue332/BitzLabs/BitzSkills/plugins/bitz-flow/.spec/reviews/FLW-REV-030.md:72)

原本を一切変更せず、mutantごとに一時コピー／使い捨てcheckoutで実行してください。hardlinkは不可、各実行はfresh Python process、開始前後に原本hash不変を確認します。

### P1 — test範囲の自己申告は、証拠ではなく最適化情報

範囲を狭くすること自体は問題ではありません。同じnodeidがbaselineでPASSし、mutant時に意図したassertionでFAILするなら強い証拠です。

問題は、台帳の自由記述をそのまま信頼する点です。runnerは最低限、次を区別すべきです。

- baseline PASS
- collected test > 0
- mutantがちょうど1箇所へ適用された
- 指定した公開経路が実行された
- assertion failure → `KILLED`
- survive → `FAIL`
- collection/import error、timeout、signal、0 test → `BLOCKED`
- 復元後または隔離環境の再baseline PASS

testファイルではなく exact nodeid／judgement marker／coverageから実行対象を導出し、台帳の `expected_killers` は診断情報に留めるのが妥当です。

### P1 — runner自身への変異は循環している

壊れたrunnerが自分自身を「正常」と報告する可能性があります。

runner自身への変異を主根拠にせず、独立したfixture projectからblack-boxテストしてください。fixtureには少なくとも以下が必要です。

- 必ずkillされるmutant
- 必ずsurviveするmutant
- baseline red
- patch 0件／複数件一致
- collection error
- timeout／process crash
- mutant適用確認
- 原本hash不変
- JSON/JUnit receiptの内容

### P1 — 1要件への統合は片直りを防がない

証拠能力、mutation infrastructure、独立レビューは検証方法と責任主体が異なります。単一 `verification_method: unit-test` では外部レビュー工程を検証できません。

また、2 issueを独立裁定するのに「裁定後は必ず1要件へ統合」では、片方だけacceptedになった場合が未定義です。

推奨は次です。

- FLW-CON-009：公開経路に基づく証拠 admissibility
- FLW-CON-010：judgement inventory と mutation assurance
- 外部レビュー順序：Gate process条件
- 同じGateで両要件をAND評価して片直りを防止

### P1 — Design Gateに設計成果物がない

JSON schema、隔離方式、kill分類、timeout、CI、receiptは設計判断です。FLW-GATE-007を置くなら、先に runner／registry design を作り、要件と設計の両方をscopeへ含める必要があります。

現案の「要件だけをscopeにしたDesign Gate」は不足です。

## curated と生成型の比較

結論は hybrid です。

- curated：`UNSUPPORTED → BLOCKED` のようなドメイン固有の禁止丸め込みに強い。一方、作者の選択バイアスを共有する。
- generated：条件反転・比較演算子・return値などを機械列挙し、選択バイアスを減らす。一方、同値mutant、実行費用、複数moduleにまたがる意味変異が残る。

mutmut は対象testの自動選択、incremental実行、並列実行を備えますが、現行3系は関数外コードを変異しないため、`_AUDIT_ACTIONS` のようなmodule-level mappingを取りこぼします。またfork対応環境が必要です。[mutmut公式ドキュメント](https://mutmut.readthedocs.io/en/latest/)

Cosmic Ray はoperator pluginで拡張でき、timeoutとsession管理を備えますが、local実行はsourceを直接書き換えるため隔離コピーが必須です。[Cosmic Ray concepts](https://cosmic-ray.readthedocs.io/en/latest/concepts.html)、[公式tutorial](https://cosmic-ray.readthedocs.io/en/latest/tutorials/intro/index.html)

どちらを採るかは未検証です。まず対象2moduleへ10〜20 mutantのspikeを行い、生成数、実行時間、invalid／equivalent／survivor率を測るべきです。

## 修正版の計画

1. 既知2件の公開API／CLIテストを先に修正し、使い捨て環境で手動mutationをkillする。
2. safety judgementの機械定義、inventory、admissible kill契約を設計する。
3. SI-FLW-093／094を依存付きで起票し、片方だけacceptedの場合も裁定する。
4. generated toolの小規模spikeを実施する。
5. 証拠能力とmutation assuranceを別要件にする。
6. runner／registry／隔離／CIを扱う設計成果物を作成する。
7. 独立レビュー後に、両要件と設計をscopeとするDesign Gateを通す。
8. タスクを最低4件へ分割する。

   - 公開APIテスト＋既知2 canary
   - judgement inventory＋admissibility検査
   - isolated runner＋black-box fixture
   - generated mutation＋専用CI job＋診断artifact

9. 統合判定前に外部レビュアーが新しい判定点またはmutant候補を最低1件提示する。
10. 既知curated mutant 100% kill、generated survivorの裁定、通常pytest、`release_check.py`、spec inspectをすべて通してGP-002を閉じる。

mutation runnerは通常pytestへ再帰的に埋め込まず、専用required CI jobにするのが安全です。現CIはpytestとrelease checkだけで、mutation用依存・timeout・artifactがありません。[CI設定](/home/inoue332/BitzLabs/BitzSkills/.github/workflows/ci.yml:29)

## 見積り

現見積りは根拠不足で、特にTSK-133の1 sessionは過小です。

暫定値は以下ですが、すべて未検証です。

- 既知test是正：0.5〜1 session
- inventory／admissibility／runner設計：1〜2
- isolated runner＋black-box検証：2〜4
- generated tool／CI統合／survivor整理：1〜3
- 外部再レビュー：0.5〜1

合計は概ね5〜10 sessionです。tool spike後に再見積りしてください。

レビューは読み取り専用で実施し、ファイル変更は行っていません。
