---
id: REV-002
version: 1.0
status: active
domain: governance
decision: PASS
owner: hide
updated: 2026-07-22
origin: sdd-review 多観点並列レビュー 第2ラウンド（bitz-env v0.8.1、REV-001 の再訪）
---

# REV-002 bitz-env 設計・要件レビュー統合報告（第2ラウンド）

**判定: PASS**（aggregate 3.76 / critical 0 / major 1 / minor 6 / info 6）

対象: ENV-DSN-001, ENV-DSN-002 + ENV-FR-001〜013 + ENV-CON-001〜004 + ENV-NFR-001〜002
（実装済み v0.8.1）。REV-001（v0.2.0時点・CONDITIONAL_PASS）の再レビュー。

観点: consistency 3.65 / data-integrity 3.65 / operations 3.50 / risk 4.00 / business 4.00。

> data-integrity は本ラウンドから対象化した（v0.7.0〜0.8.1 で `.claude/bitz-env.local.md` への
> `bitz-env-version` stamp と CORE-CON-009 準拠の累積マイグレーション機構
> [ENV-FR-011/012/013] が追加され、永続データの版数状態管理を持つに至ったため）。
> risk は非分散のため分散・Saga 次元は引き続き N/A 縮退。

## REV-001 からの解消状況

| 元ID | 解消根拠 |
|---|---|
| RSK-201 | ENV-CON-004（env-init 未実行時の env-doctor WARN を要件化） |
| RSK-202 | ENV-CON-004 / ENV-DSN-001:ADR-2（誤操作抑止であることを明記） |
| RSK-401 | ENV-FR-007（診断スコープにレジストリ⇔CLAUDE.mdマトリクスの不一致検出を明示） |
| RVC-201 | evals/env-init, env-doctor, env-register, env-orchestration, env-update の実体作成 |
| OPS-201 | ENV-FR-009（バックアップ）/ ENV-FR-013（git管理状態の実確認強化） |
| BIZ-201 | ENV-NFR-001（応答時間200ms）/ ENV-NFR-002（rules注入サイズ） |
| BIZ-301 | ENV-DSN-001:ADR-1/ADR-2 / ENV-DSN-002:設計判断節（ADR形式のトレードオフ記録） |

REV-001 の P1(major) 5件（RSK-201/202, RVC-201, OPS-201, BIZ-201）と P3 で指摘のあった
BIZ-301、P2 の RSK-401 を含め、計7件が解消済み。

## P1（major・要対応）

| ID | 場所 | 指摘 | 是正の方向 |
|---|---|---|---|
| RVC-203 | ENV-FR-008（verified）/ hooks/hooks.json:SessionStart / tests/test_env_guard.py | verified 済み ENV-FR-008 の「rules/ が空または読めない場合にエラーでセッションを妨げない」受入基準に対応する実装・テストが無い。`cat "${CLAUDE_PLUGIN_ROOT}"/rules/*.md` は glob 不一致でエラー終了しうる | SessionStart コマンドを nullglob 相当に変更し、rules/ 空ケースを tests/test_env_guard.py に追加。対応しないなら要件を implementing へ差し戻す |

## P2（minor・修正推奨）

- **RVC-202**: ENV-FR-005 が2スキルにまたがるがタスク紐づけが粗い（boundary 明示 or タスク分割）
- **RVC-301**: 中核用語(中心/司令塔/advisor/worker/3パターン)の glossary が依然無い
- **OPS-101**: ガード発火・生成操作の恒久ログが依然無い（systemMessageのみで部分緩和）
- **OPS-401**: 展開先の既存フックとの共存(二重発火)が2ラウンド連続で未検証（要検証項目#3）
- **RSK-203**: フックのタイムアウト時に deny/fail-open どちらへ倒れるかが未定義（範囲を絞って継続）
- **DIN-201**（新規）: レジストリ `.claude/bitz-env.local.md` への同時書き込み（複数エージェント・
  worktree並列運用時）の競合制御が未設計。lost update の可能性

## P3（info・任意）

- **RVC-101**: 設計文書が1枚集約（現状妥当）
- **OPS-301**: シークレット read deny・資格情報ハードコード無しは妥当
- **BIZ-101**: 合議型はアダプタ2つ以上前提で先行実装気味（discovery文書のopenリストと整合済み）
- **BIZ-401**: quick win 明確・v0.8.1 まで継続的な verified 要件の積み上げで実現可能性は良好
- **DIN-101**（新規）: stamp書き込み順序とguard冪等性によりトランザクション面は堅牢
- **DIN-301**（新規）: スキーマ変更をプラグインversionと1軸に固定した設計は単純で堅牢

## 人間への裁定依頼

この判定は推奨です。PASS のため Design Gate 自体は通過可能と判断しますが、
P1（RVC-203）は「verified 表示の信頼性」に関わる指摘のため、次の小さな修正PRでの解消を推奨します。
P2 は蓄積のうえ SI-ENV-XXX として起票判断を検討してください（本レビューでは起票していません）。

---

# 履歴: REV-001（第1ラウンド、v0.2.0時点）

**判定: CONDITIONAL_PASS**（aggregate 2.87 / critical 0 / major 5 / minor 6 / info 4）

対象: ENV-DSN-001 + ENV-FR-001〜008 + ENV-CON-001〜003（実装済み v0.2.0）。
観点: risk 2.33 / consistency 3.65 / operations 2.70 / business 3.20。
data-integrity は永続データ無しのため N/A。risk は非分散のため分散・Saga 次元を N/A 縮退。

> CONDITIONAL_PASS のため、P1(major) を消化するまで Design Gate は通過しない。
> critical はゼロで、いずれも「文書化・要件化・検証接続」で解消できる設計レベルの穴。

## P1（major・要対応）

| ID | 場所 | 指摘 | 是正の方向 |
|---|---|---|---|
| RSK-201 | env_guard / DSN | 防御の二重化が「env-init 実行済み」に暗黙依存。フックだけの環境では fail-open が単独防御になり、故障時に破壊操作が素通し | 二重化の前提を要件化。env-init 未実行を env-doctor が警告 |
| RSK-202 | env_guard:DENY_PATTERNS | 正規表現ガードはバイパス可能で、セキュリティ境界と誤解される恐れ | 「誤操作抑止であり悪意ある回避の防止ではない」と位置づけ明記 |
| RVC-201 | ENV-FR-003〜007 | example-test の検証実体(evals/)が未作成で、approved なのに verified 到達不能。spec_inspect は実体不在を検出せず PASS に隠れている | skill-tester で evals/env-*/ を作成し検証を接続。未接続は明示 |
| OPS-201 | ENV-FR-003 / env-init | 生成物(settings.json/AGENTS.md/CLAUDE.md)のロールバック・バックアップ手段が無い。git 管理外の展開先で誤マージすると復旧不能 | 書き込み前バックアップを要件化、または「git 管理下」を前提条件に明示 |
| BIZ-201 | requirements/ | 非機能要件(NFR)が1件も無い。全 Bash に割り込むガードの性能目標が無く「遅い」の判定基準を持てない | ガード応答時間・注入サイズの最小 NFR を起票 |

## P2（minor・修正推奨）

- **RSK-203**: フック timeout 時・SessionStart の `cat rules/*.md` 空時の挙動が未定義（fail 方向の確定と空でも失敗しない実装）
- **RSK-401**: レジストリ⇔CLAUDE.md マトリクスの二重書き込みが部分失敗で不整合化（env-doctor 検査に明示追加・マーカー破損時の分岐）
- **RVC-202**: ENV-FR-005 が2スキルにまたがるがタスク紐づけが粗い（boundary 明示 or タスク分割）
- **RVC-301**: 中核用語(中心/司令塔/advisor/worker/3パターン)の glossary が無い（「中心=司令塔」の別名関係を宣言）
- **OPS-101**: ガード発火・生成操作のログが無くデバッグ困難（生成サマリの標準出力）
- **OPS-401**: 展開先の既存フックとの共存(二重発火)が未検証（要検証項目#3・実測して合成規則を記録）

## P3（info・任意）

- **RVC-101**: 設計文書が1枚集約（現状妥当・契約は分離済み）
- **OPS-301**: シークレット read deny・資格情報ハードコード無しは妥当
- **BIZ-101**: 合議型はアダプタ2つ以上前提で先行実装気味（将来スコープへ位置づけ、初期は委譲型・相談型主軸）
- **BIZ-401**: quick win 明確・v0.2.0 実証済みで実現可能性は良好

## 第2ラウンド: クロスモデルレビュー（agy / Gemini・実行済み）

REV-001（Claude 自己レビュー）を別モデル agy で再検証（`agy --print` を実際に実行、exit 0）。
結果は individual/cross-model-agy.json。7指摘中 CONFIRMED 5件・PLAUSIBLE 2件、false positive なし。
agy 総合判定は **REVISION_REQUIRED**。REV-001 が見落とした「LLM をコンポーネントとして
組み込む際の防御的設計」と「ライフサイクル管理」に集中している。

| ID | reconcile 後 | 場所 | 新規指摘 |
|---|---|---|---|
| **AGY-7** | major | env-init（新規） | **アンインストール時のクリーンアップ不在**。生成した恒久層(permissions/断片)が残留しサイレント・ロックイン。REV-001 完全見落とし・最重要 |
| **AGY-5** | major（agy: critical） | collab-contract | 標準スキル名(delegate 等)のグローバル名前空間衝突。複数アダプタ追加で純粋追加式が破綻 |
| AGY-3 | major（agy: critical） | ENV-FR-005 | 委譲の盲目的検収（DIGEST 自己申告のみ）。git diff 等の客観差分を Center 自ら取得すべき |
| AGY-4 | major | ENV-FR-005 | 委譲/相談の再帰にストッパー無し（ピンポンでコスト枯渇） |
| AGY-2 | major（agy: critical） | ENV-CON-004 | シェルスクリプト間接実行は完全バイパス。ENV-CON-004 に限界明記で対応 |
| AGY-1 | minor | ENV-FR-002 | fail-open の物理担保（python3 異常終了時）。ラッパー `|| echo {}` |
| AGY-6 | minor | collab-contract | DIGEST は紳士協定でコンテキスト破壊を防げない（Center 側で truncation） |

### 第2ラウンドで追加する P1（新規 spec-issue、proposed）

- **SI-ENV-005**（AGY-5）: 標準スキル名の名前空間衝突 → プレフィックス必須＋ルーティングテーブル化
- **SI-ENV-006**（AGY-7）: アンインストール/無効化時のクリーンアップ（env-destroy スキル）
- **SI-ENV-007**（AGY-3+AGY-4）: 委譲の客観的検収と再帰防止
- AGY-1/2/6 は既存要件への追記で対応（ENV-FR-002 / ENV-CON-004 / collab-contract）

（注: 上記 SI-ENV-005〜007 はいずれも本ワークスペースで既に accepted・実装済み。
ENV-FR-006 v1.1、ENV-FR-010、ENV-FR-005 v1.1 が対応する。AGY-1/2/6 も ENV-CON-004・
ENV-FR-002 に反映済み。）
