# 裁定記録 — SI-FLW-051（機械強制層の廃止と M2 実装区分の順序）

- **日付**: 2026-08-13
- **裁定者**: hide
- **対象**: `SI-FLW-051`
- **提示方法**: issue の推薦つき選択肢を提示したのち、裁定者の求めにより
  「機械強制層の採用経緯」を追跡し、**フックを持たない選択肢の成立性**を検討したうえで裁定した
- **前提**: `FLW-REV-013`（独立5観点レビュー・FAIL 2.31）。
  先行して `SI-FLW-047` / `048`、`049` / `055`、`050` を裁定済み
- **裁定方針（裁定者の明示）**: **v2 へ向けた設計段階であり、手戻りを許容して
  最善かつシンプルな構成を採る**（先行3裁定と同一方針）

## 裁定

**accept。** ただし **(a) は issue が提示した3案のいずれでもない第4案を採る。**

| 論点 | 裁定 |
|---|---|
| (a) 機械強制層 | **accept（案D — 新案）** — **機械強制層を bitz-flow の責務から外す**。フック実体を配布せず、permissions も変更しない。担保は承認 capability（in-band）と audit / quarantine（検出）へ寄せる |
| (a-2) permissions 緩和の投入時期 | **論点消滅** — bitz-flow が permissions を触らないため |
| (b) 実装区分の順序 | **accept** — **qualification を M2-2 から切り出し**、compatibility key を変える最後の区分（M2-4）の直後へ独立区分として置く |

## 1. (a) 機械強制層 — bitz-flow の責務から外す

### 採用の経緯（本裁定で追跡した事実）

機械強制層の起点は `FLW-REV-011:SYN-010`（P1 / major、出所 `OPS-007`）である。

> `AGENTS.md` はリポジトリ外への書き込みを事前確認必須とし、機械的ブロックを
> `settings.json` の permissions で強制すると定めるが、**worktree root に該当する規則が無い**。
> M2 は repo 外書き込みを常用化する最大の変更でありながら**機械層は無変更である**。

これが Gate 前提条件 `GP-010` となり、`FLW-DSN-016` §4（`:320-334`）で
「`.claude/settings.json` の permissions へ worktree root パターンを追加」
「承認 receipt を伴わない worktree write を **PreToolUse フック**でブロック」として設計へ落ちた。

**この起点は製品要求ではなく、BitzSkills 自身の開発環境ガードレール**
（`AGENTS.md` ⇔ `.claude/settings.json` ⇔ bitz-env 同梱フックの3層同期。`env-doctor` が検査）
**である。** 指摘そのものは正しいが、**それを製品の M2 出口条件へ昇格させる際に、
3プラットフォームで成立するかの検討が抜けた**。記述が Claude Code 固有の機構名でしか
書かれていないのはそのためである。

`FLW-REV-012`（自己レビュー 3.62）は `GP-010` を「充足」と判定した（`FLW-REV-012.md:52`）。
§4 に手順が書かれていることをもって充足としており、**フック実体の不在も、
他プラットフォームでの不成立も、後述の承認済み制約との矛盾も検査していない**。

### 決定的な事実1 — `FLW-CON-001` が platform 固有 hook を禁じている

`FLW-CON-001`（`status: verified`。凍結済み制約要件）の受入基準:

> WHEN source treeと設計optionを検査する THEN bitz-flowはGo、Rust、MCP、**platform固有hook**、
> 透過proxyの実装または**移行候補0件**を記録すること SHALL

**bitz-flow がフック実体を配布することは、検証済み制約への違反である。**
issue の案A（3プラットフォームへフック配布）は実務上の困難以前に、規約上採れない。
「移行**候補** 0件」まで要求しているため、選択肢として保持することも制約の対象である。

`FLW-DSN-016` §4 が `PreToolUse` フックを出口条件へ据えた時点で、この矛盾は既に発生していた。
`SI-FLW-051` も `FLW-REV-013` もこの矛盾を検出していない。

### 決定的な事実2 — 要件層では担保が既に閉じている

`FLW-NFR-007` 1.3（`SI-FLW-043` で改訂した当の条文）が定める repo 境界外への更新許可条件:

1. 承認済み worktree root 配下であること
2. canonicalize 後に root 外へ escape しないこと
3. `FLW-CON-005` の明示的人間承認を**単回 capability** として得ていること

**3条件すべてが in-band** であり、bitz-flow のコードが自分で照合できる。
**permissions もフックも要件に一切現れない。** 機械強制層は要件の充足に必要ではなく、
`FLW-DSN-016` §4 が設計判断として上乗せしたものである。

### 決定的な事実3 — 隣接ケースでは既に「防止しない」と決めている

`FLW-DSN-016` §9 の fixture:

| fixture | 期待 |
|---|---|
| `M2-FLT-013` | 外部からの手動削除（guard 外要因）→ audit が `ORPHAN` 検出 → 解除区分へ接続。**防止は主張しない** |
| `M2-FLT-014` | 外部からの registry 改変 → 同上 |
| `M2-FLT-015` | 承認 receipt を伴わない worktree write → permissions ＋ フックでブロック |

FLT-013 / 014 で「防止は主張しない・検出する」と決めながら、**FLT-015 だけが防止を主張している**。
フックを外せば3件が同じ方針で揃う。

さらに `SI-FLW-047` を証跡軸で裁定したことにより、**receipt を伴わない状態変化は
「証跡と観測の矛盾」として検出され quarantine へ接続される**。検出経路は裁定済みで既に存在する。

### 案D の内容

**機械強制層を bitz-flow の責務から外す。**

- フック実体を配布しない（`FLW-CON-001` 準拠）
- `.claude/settings.json` の permissions を bitz-flow が変更しない
- repo 外書き込みの担保は `FLW-NFR-007` 1.3 の3条件（承認 capability）へ寄せる
- operation を経由しない write は**防止せず検出する**（audit → `ORPHAN` / 証跡矛盾 → quarantine）
- 環境ガードレール（`AGENTS.md` ⇔ permissions ⇔ 環境系プラグインのフック）は
  **bitz-env および利用者の環境設定が単独で所有**する。bitz-flow は
  repo 外 worktree root を使う場合の推奨設定を**文書上の案内**として置くにとどめる

### 案D で失われるもの・得られるもの

| | 現設計（フックあり） | 案D（フックなし） |
|---|---|---|
| bitz-flow 経由の write | 承認 capability ＋ guard ＋ CAS | **同じ**（変化なし） |
| operation を経由しない write | ブロック（Claude Code のみ。Codex は Bash ツールのみ捕捉・Windows 無効） | **検出**（audit → `ORPHAN` / 証跡矛盾 → quarantine） |
| 環境ガードレールの所有 | bitz-flow と bitz-env の二重所有 | bitz-env / 利用者が単独所有 |
| M2 出口条件 | **3 platform で判定不能** | **3 platform すべてで判定可能** |
| `FLW-CON-001` | **違反** | 準拠 |

失われるのは「**事前の防止**」のみであり、それは Claude Code でしか成立せず
（`docs/調査報告/03.Codex/04_extensibility_architecture.md` の実測: Codex の Hooks は実験的機能、
Windows で無効、`PreToolUse` / `PostToolUse` が捕捉するのは Bash ツールのみ、
「完全な強制境界ではなくガードレールとして扱うのが適切」）、
かつ検証済み制約で禁じられていたものである。

### issue の案B / 案C を採らない理由

案B（capability 縮退で platform 別に表現）は、**bitz-flow が持てない機構**を
capability matrix へ残すことになる。案C（出口条件から外す）は方向として近いが、
issue が非推奨とした理由「縮退規則3 の前提が崩れる」は、
**担保を強制層から承認 capability（`FLW-NFR-007` 1.3）へ明示的に置き換えることで解消する** —
要件層では最初からそこに閉じていたためである。案D はその置き換えを明文化した案C である。

## 2. (b) 実装区分の順序 — qualification を切り出す

`compatibility key v1` の閉集合には **`skill` が含まれる**
（`FLW-DSN-015.md:326`、`FLW-DSN-014.md:598-599` の両方で確認）。
M2-4（着手前 reconnaissance ＋ entry protocol）は v2 SKILL.md の入口拘束を変更するため
compatibility key が変わり、**M2-6 の confirmation 時点で M2-2 の qualification は失効している**。

issue の主案（M2-4 を M2-2 より前へ移す）はそのままでは採れない。
`FLW-DSN-016.md:620` が「**M2-4 を M2-3 の直後に置くのは、reconnaissance が
audit の branch 列挙に依存するため**」と技術依存を明記しており、単純な前倒しは依存を壊す。

**確定する区分構成**:

- **M2-2 は「承認 capability」のみ**とする（機械強制層は本裁定 1. で消滅、qualification は切り出す）
- **qualification を独立区分とし、M2-4 の直後に置く** — compatibility key を変える変更が
  すべて済んだ後に1回だけ実行する。M2-6 の confirmation 時点で失効しない
- blocking の保護は **M2-5 以降**へ掛かる（M2-3 / M2-4 は qualification 前に進む）
- M2-3 → M2-4 の技術依存は維持される

session 配賦の再計算（M2-2 から機械強制層と qualification が抜け、独立区分が1つ増える）は
**`SI-FLW-053` の budget 論点と合わせて確定する**。

あわせて §14 の「本書は M2 実装前の設計であり、現行の M0 read-only dispatcher を変更しない」を
実態に合わせて訂正する（M2-4 が M0 Contract Kernel の構成物である SKILL.md を変更するため）。

## 波及と次の作業

改訂対象:

- `plugins/bitz-flow/.spec/design/FLW-DSN-016.md`
  — §4 機械強制層節（`:320-334`）の削除と環境側責務の明記、
  `M2-FLT-015` の in-band 検査への書き換え、
  §11 実装境界（区分構成と依存の書き直し）、§12 出口条件、§14 影響範囲の訂正
- `plugins/bitz-flow/.spec/design/FLW-DSN-014.md` — capability matrix・縮退規則3 の解除条件
- `plugins/bitz-flow/.spec/ROADMAP.md` — `:158` の出口条件から機械強制層を削除

**M2 出口条件の改訂後の形**（強制層の行を置換）:

- 承認 capability が全 worktree write に対して有効であること（`FLW-NFR-007` 1.3 の3条件）
- operation を経由しない変更が audit で検出され quarantine へ接続されること

`FLW-CON-001` との矛盾が解消したことを §14 の影響範囲へ記録する。

**順序制約**: `SI-FLW-052` が「検査の構築を文書修正より先に完了させる」ことを求めている。
本裁定の文書改訂は `SI-FLW-052` の機械検査を構築したのちに着手する。
**本裁定は改訂内容を確定するものであって、改訂の着手を意味しない。**

## 本裁定が明らかにした検証工程の欠陥

`FLW-REV-012`（自己レビュー 3.62）は `GP-010` を「充足」と判定したが、
実際には (1) フック実体が存在せず、(2) 3プラットフォームで成立せず、
(3) **検証済み制約 `FLW-CON-001` に違反していた**。
設計文書に手順が書かれていることを充足の根拠としており、
**要件層との突合も実ファイル確認も行われていない**。

これは `SI-FLW-052` が指摘する根本原因（「対応した」という宣言を検証せずに受け入れる工程）の
最も重い実例であり、同 issue の検査群に「**設計が verified 制約に違反していないかの照合**」を
含めるべきことを示している。**`SI-FLW-052` へ送る。**

## 未解決として次へ送る論点

| 論点 | 送り先 |
|---|---|
| 区分再構成後の session 配賦 | `SI-FLW-053` |
| 設計 ↔ verified 制約の違反照合（`FLW-CON-001` 型） | `SI-FLW-052` |
| M2 early quick win の定義（capability 縮退の枠組みが変わったため再検討） | `SI-FLW-053`(4) |
| repo 外 worktree root を使う場合の環境設定案内の記述場所 | `FLW-DSN-016` 改訂時 |
