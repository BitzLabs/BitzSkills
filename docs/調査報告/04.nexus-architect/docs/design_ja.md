# Design Notes: Product ↔ Architect Integration

**product** Pluginがその成果物を**architect** Pluginにどのように引き継ぐかに関する内部設計の参照資料である。このファイルはハンドオフマッピングのSingle Source of Truth (信頼できる唯一の情報源) であり、SKILL.mdやルールファイルはテーブルを複製するのではなく、このセクション番号（特に**§1.3**）を参照する。

このドキュメントは内部のエンジニアリングドキュメントである（リポジトリの規約により英語で記述されている）。生成されるレポートの内容ではなく、Plugin間の*契約（contract）*について記述している。

## 1. Product → Architect Handoff Contract

### 1.1 Overview

2つのPluginは1つの連続したチェーンを形成する：

```
/product:start (vision → … → define-nfr / map-domains / design-api / design-architecture)
      │   product reports/ + work/traceability.json
      ▼
/architect:define-requirements   (requirements baseline)
      ▼
/architect:start | :investigate → :analyze → … → :design-* → :review-* → :report
```

product Pipelineは、**論理的でビジネス向け**の仕様（ビジョン、スコープ、ペルソナ、ジャーニー、機能、論理データモデル、Bounded Context (境界づけられたコンテキスト)、論理APIサーフェス、SLO/NFR目標、および候補となるアーキテクチャ）を生成する。architect Pipelineは、それを**物理的で実装向け**の設計（Actor (アクター)/Role (ロール)/Permission (権限) マトリックス、物理DBインベントリ、トランザクション一貫性の分類、ScalarDBスキーマとエディション、インフラストラクチャ、セキュリティ、運用）に変換する。

`/architect:define-requirements`は、productの出力を取り込む**単一のエントリポイント**である。productの成果物は`--input`ドキュメントとして渡されるか、または共有の`reports/`ツリーから自動検出される（§1.2を参照）。

### 1.2 Handoff Mechanism

2つの補完的なパスが存在する：

1. **自動検出（同じ場所に配置されている場合に推奨）。** productとarchitectが同じプロジェクトルートの下で実行される場合、`define-requirements`は`reports/00_core/`、`reports/01_ux/`、`reports/02_spec/`、`reports/03_domain/`、`reports/04_quality/`の下にあるproductのレポートを自動検出し、それらを（`work/traceability.json`と共に）取り込みセットに追加する。`define-requirements`のPrerequisites / Step 1を参照。**オーケストレーター**（`/architect:start`、`/architect:pipeline`）は事前にも同じ検出を実行する。productの成果物が存在する場合、それらはハンドオフをアナウンスし、レポートが入力された状態でgreenfield (新規開発) パスにルーティングするため、ブリッジは暗黙的ではなく可視化される。

2. **明示的な `--input`。** productの出力が他の場所にある場合は、関連するファイル（またはそのディレクトリ）を明示的に渡す。例：
   `/architect:define-requirements --input=reports/04_quality/nfr.md --input=reports/03_domain/`。

2つの成果物は`define-requirements`をバイパスし、後続のarchitect Skillに直接ブリッジされる：

- `reports/03_domain/tech-stack-fitness.md` — ScalarDB / ScalarDLの**Adopt**判定は、`/architect:select-scalardb-edition` → `/architect:design-scalardb`（および `/architect:design-scalardb-analytics`）にブリッジされる。`define-requirements`は、独自のScalarDB適用可能性のステップ（§1.3、scalardb-applicabilityの行）において、ゼロから再導出するのではなく、既存のAdopt判定を事前情報（prior）として扱うべきである。
- `reports/03_domain/architecture.md` — `/architect:design-microservices`が洗練させる候補となるランタイムアーキテクチャ。

**IDの連続性。** productは、§1.3のIDスキームで`work/traceability.json`を維持する。`define-requirements`はそのグラフを取り込み、無関係なIDを新しく発行するのではなく、**productのIDを前方に引き継ぐ**べきである：`FEAT-`は1つ以上の`FR-`のソースになる（`FEAT-→FR-`のリンクを記録する）。そして、productの`NFR-`は再ナンバリングされることなく**そのまま再利用**される（同じID、同じ意味）。これにより、`VIS-`/`NSM-`から物理設計に至るまでの単一のトレースチェーンが維持される。メカニズムについては§1.5を参照。

### 1.3 Artifact Mapping Table

productの出力 → architectの `define-requirements` 成果物。**non-functional inputs** の行（SLA/NFR）と、**bounded-context inputs** の行（ドメイン）は、他のファイルが名前で引用する2つの行である。

| Product output (ID prefix) | Source skill | → `define-requirements` deliverable / section | Fit |
|----------------------------|--------------|-----------------------------------------------|-----|
| `00_core/vision-mission-value.md`, `pr-faq.md` (`VIS-`) | define-vision | requirements-definition.md → Business context | ✓ |
| `00_core/success-metrics.md` (`NSM-`) | define-success-metrics | requirements-definition.md → Business goals / success criteria | ✓ |
| `00_core/scope-definition.md`, `constraints.md` (`SCP-`) | define-scope | requirements-definition.md → Scope (in/out), Constraints | ✓ |
| `00_core/assumptions.md`, `validation-plan.md` (`ASM-`) | validate-assumptions | open-questions.md → unresolved items / open risks | ✓ |
| `01_ux/personas.md` (`PER-`, `JOB-`) | generate-persona | requirements-definition.md → Actor list (**シードのみ**; ペルソナはJobs-to-be-Done (ジョブ理論) ユーザーセグメントであり、Role/Permissionマトリックスではない — architectが `:analyze` でRole/Permissionを導出する) | △ |
| `02_spec/feature-list.md` (`FEAT-`) | define-features | requirements-definition.md → Functional Requirements (`FEAT-`→`FR-`、リンクを記録する) | ✓ |
| `02_spec/data-model.md` (`ENT-`) | define-data-model | data-transaction-requirements.md → data requirements (**論理ER**であり、バージョン/ボリュームを含む物理DBインベントリではない) | △ |
| `03_domain/bounded-contexts.md`, `domain-map.md`, `ubiquitous-language.md` (`CTX-`) | map-domains | **Bounded-context inputs** — requirements-definition.mdのスコープ設定 + `/architect:analyze`のUbiquitous Language (ユビキタス言語) に供給する; `CTX-`ごとの一貫性のヒント（`Strong`/`Eventual`/`TBD`）はトランザクションマトリックスの**シード**となる（§1.4を参照） | ✓ |
| `03_domain/api-design.md` (`API-`) | design-api | 後続の`/architect:design-api`のためのリファレンス; FRのスコープに情報を提供する | ✓ |
| `04_quality/sla.md` (`SLO-`, `SLA-`) | design-sla | **Non-functional inputs** — NFRの目標: 可用性、RPO/RTOのソース | ✓ |
| `04_quality/nfr.md` (`NFR-`) | define-nfr | **Non-functional inputs** — requirements-definition.mdのNFRテーブル（`NFR-` IDをそのまま再利用する） | ✓✓ |
| `03_domain/architecture.md` (`ARCH-`) | design-architecture | `/architect:design-microservices` にブリッジされる（define-requirementsではない） | → |
| `03_domain/tech-stack-fitness.md` (`TECH-`) | design-architecture | scalardb-applicability.md → 適用可能性判定の**事前情報（prior）**; Adoptは `/architect:select-scalardb-edition` にブリッジされる | → |

Fitの凡例: ✓✓ ほぼ1:1 · ✓ カバーしている · △ 部分的（architectが拡張する必要がある） · → define-requirementsではなく、後続のarchitect Skillにブリッジされる。

### 1.4 Designed Gaps (product does **not** supply these)

これらは意図的に`define-requirements`の引き出し、または後続のarchitectフェーズに残されている — これらは論理的なproduct仕様では決定されない物理的な関心事である。これらが偶発的な漏れではなく、*設計によるもの（by-design）*として理解されるように以下にリストする：

| Gap | Owner | Note |
|-----|-------|------|
| **ビジネスプロセスごとのトランザクション一貫性** (Strong/ACID · Eventual/Saga · Local Tx) | define-requirements Step 3 | `data-transaction-requirements.md`の背骨。productはプロセスごとの*拘束力のある*分類を出力しないが、`map-domains`は現在、大まかな`CTX-`ごとの`Strong`/`Eventual`/`TBD`のヒントをシードする。architectはそれを確認/上書きし、拘束力のあるACID/Saga/Local-Txの判断を下す。 |
| **物理DBインベントリ** (エンジン、バージョン、ボリューム) | define-requirements Step 3 | productの`data-model.md`は論理ERのみである。 |
| **Actor / Role / Permission マトリックス** | `/architect:analyze` | productのペルソナはJobs-to-be-Done セグメントである。システムのRole/Permissionは後続で導出される。 |
| **まだ決定されていない数値的なNFR目標** | define-requirements (TBD → open-questions.md) | productは`TBD`を`work/context.md`に記録する。これらを`open-questions.md`に引き継ぐ。 |

### 1.5 Cross-Plugin Traceability Write-Back

単一のトレースグラフは、`define-requirements`がproductが書き込んだのと**同じ`work/traceability.json`にそのノードを追加する**ことによって維持される。この際、既存のノードの形式を使用する（スキーマの変更なし — ノードはすでに汎用的である）：

```json
{ "id": "FR-007", "type": "requirement", "title": "...", "skill": "define-requirements",
  "source_file": "reports/00_requirements/requirements-definition.md",
  "upstream": ["FEAT-012"] }
```

ルール：

1. **配置または作成。** `work/traceability.json`が存在する場合（productが実行された場合）、そこに追加する。存在しない場合（純粋なarchitectパス）、まず `{ "schema_version": 1, "nodes": [] }` として作成してから追加する。2つ目のグラフファイルを決して作成してはならない。
2. **`FR-` ノード** — 機能要件ごとに1つ、`type: "requirement"`とし、派生元のすべてのproduct機能に対して`upstream: ["FEAT-…"]`を設定する（FRが新しく引き出された、つまりproductに由来しない場合のみ、`upstream`は空にする）。
3. **`NFR-` ノード** — NFRがproductから引き継がれる場合、**2つ目のノードを作成しないこと**。productの`NFR-`ノードはすでに存在し、そのまま再利用される。architectで発生した（productが設定しなかった引き出された目標）NFRについてのみノードを作成し、`type: "nfr"`とし、`upstream`は`SLO-`/`CTX-`またはビジネスドライバーを指すようにする。
4. **物理のみのノード** （トランザクション一貫性クラス、DBインベントリエントリ、Actor/Role/Permission — §1.4のギャップ）には、**productのアップストリームがない**。そのため、`upstream`を空にして記録し、グラフがそれらをarchitect由来として示すようにする。

**検証（これが契約を単なる文章以上のものにする）。** productの `review`（トレーサビリティのレンズ）とarchitectの `review-consistency` は、結合されたグラフについて以下の点を確認する：すべての`FR-`が`FEAT-`から到達可能であるか、または新規としてフラグ付けされていること。productの`NFR-`が暗黙のうちに再ナンバリングされていないこと。Pluginの境界を越えてダングリング（未解決）な`upstream` IDが存在しないこと。これらが壊れている場合は一貫性の指摘事項であり、静かな乖離（サイレントドリフト）ではない。

> セクション 2–6（その他のPluginの内部情報）は、まだこのドキュメントに移行されていない。セクション 7はproduct適応エンジンの正式な仕様である。`rules/product/adaptation-engine.md`はその運用リファレンスであり、ここを参照している。

## 7. Adaptation / Re-propagation Engine (product `adapt-change`)

`/product:adapt-change` の正式な仕様。このエンジンは変更を受け取り、`work/traceability.json` から影響を受けるスコープを計算し、人間に（または `--auto` で）それを確認させ、影響を受けるSkill**のみ**を再実行し、整合性をチェックする。原則は**最小限の再実行（minimal re-run）**である — 変更が及ばないSkillには決して触れない。運用リファレンス（変更タイプのヒント、プロンプト）は `@rules/product/adaptation-engine.md` である。

### 7.1 The Edge Store

`work/traceability.json` は依存関係エッジの単一の情報源である。すべてのSkillは最終ステップとして自身のIDを追加するため（§1.5はこれをproduct→architectの境界を越えて拡張する）、エンジンは1つのファイルを読み込む。ノードの形状は§1.5の通りであり、キーとなるフィールドは `upstream` である：

```jsonc
{ "id": "FEAT-012", "type": "feature", "skill": "define-features",
  "source_file": "reports/02_spec/feature-list.md",
  "upstream": ["JOB-003", "JNY-005", "NSM-001"] }
```

`upstream` は、ノードが派生する元のノードを指す。**ダウンストリーム（downstream）**の方向（誰が私に依存しているか）は `upstream` の逆であり、それが伝播が従う方向である。

### 7.2 Engine Steps

1. **取り込み（Intake）** — 変更を `reports/05_adaptation/change-log.md` に記録する（説明、`--type`、渡されたタイムスタンプ — スクリプトは時計を読み取れないため、オーケストレーターがそれを提供する）。
2. **候補となる影響範囲（決定的）** — 変更が直接触れるノードを見つけ（`--type` ヒントによってシードされる、§7.4）、次に `upstream` エッジを逆方向にたどってその**ダウンストリームの推移的閉包（transitive closure）**を計算する。純粋なグラフ作業であり — まだ判断は行われず、候補を提案するのみである。
3. **判断パス（Opus）** — 各候補を調べ、変更にもかかわらずそのアップストリームの参照が*まだ有効か*どうかを判断し、セットを**拡大または縮小**する。グラフが提案し、判断パスが決定する。「変更 → 影響を受けるID → 再評価するか？ + 理由」を `reports/05_adaptation/impact-analysis.md` に記録する。
4. **人間の確認** — 確認された影響セットを `AskUserQuestion` 経由で提示する（`--auto` の下ではスキップされる）。
5. **最小限の再実行（Minimal re-run）** — 既存の成果物を入力として提供し、確認された影響を受けるSkillのみを再実行し、`traceability.json` の対応するエッジを更新する。
6. **整合性チェック（Coherence check）** — 再伝播によって導入された矛盾を捕捉するために `/product:review`（一貫性 + トレーサビリティのレンズ）を実行する。変更がarchitectの境界に達した場合、§1.5のPluginをまたいだチェックも適用される。

### 7.3 Principles

- **最小限の再実行（Minimal re-run）** — 推移的閉包 + 判断により、過剰到達（影響を受けないSkillに触れること）と到達不足（真の依存関係を見逃すこと）の両方を防ぐ。
- **可逆性（Reversibility）** — `change-log.md` は再実行されたすべての成果物の変更前/変更後の差分サマリーを記録するため、変更を理解し、元に戻すことができる。
- **人間のチェックポイント** — いずれかの成果物が書き換えられる前に、影響セットが確認される（`--auto` でない限り）。
- **冪等なエッジ（Idempotent edges）** — 再実行後、`traceability.json` は新しい現実を反映する。同じ変更を再実行しても何も起こらない（no-op）。

### 7.4 Change-Type Entry Points

`--type=constraint | market | competitor | tech | regulation` は変更がグラフのどこに入るかを示し、ステップ2の「直接触れられる」セットをシードする：

| `--type` | Entry nodes |
|----------|-------------|
| `constraint` | `CON-` / `SCP-` (constraints, scope) |
| `market` / `competitor` | market-landscape / positioning (`POS-`) |
| `tech` | `TECH-` / `ARCH-` (tech-fitness, architecture) |
| `regulation` | constraints / `NFR-` |
