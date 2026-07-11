---
id: REV-001
version: 1.0
status: approved
domain: governance
decision: CONDITIONAL_PASS
origin: sdd-review 多観点並列レビュー（bitz-env v0.2.0）
---

# REV-001 bitz-env 設計・要件レビュー統合報告

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

## 推奨する次の反復

P1 の5件を spec-issue 4件（SI-ENV-001〜004）に束ねて起票し、人間裁定（要件化）を経て設計へ反映する。
critical が無いため急いで実装を止める必要はないが、Design Gate 通過には P1 消化が前提。
