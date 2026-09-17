# Core 1.0 実装前異常ケースレビューと修正提案

**状態**: **Closed（4件裁定・反映済み）**

**レビュー日**: 2026-09-01

**対象**: `docs/02.設計書`、`docs/03.詳細設計`

**目的**: 実装前に削除、取り止め、検証異常、入力障害の分岐を確定しつつ、小規模チーム向けCoreを過剰に拡張しない

## 1. 結論

正常系と既存のGit縮退、空対象、終端状態、レポート書込み失敗、path逸脱は実装可能な粒度に達していた。
残った4件は、新しい永続サービスや状態機械を追加せず、既存のGit基準版、状態遷移、Rationale、
Diagnostic、command結果Schemaを使って裁定した。

| ID | 優先度 | 指摘 | 裁定 |
|---|:--:|---|---|
| EDGE-001 | P1 | SPEC削除・rename・ID再利用・member削除の対応関係が不定 | 修正採用・反映済み |
| EDGE-002 | P1 | Stopped時の途中成果物とフェーズrollback単位が不定 | 縮小採用・反映済み |
| EDGE-003 | P1 | verify失敗後の継続、実行順、出力上限、timeout保証範囲が不定 | 縮小採用・反映済み |
| EDGE-004 | P2 | 不正UTF-8、I/O失敗、同時編集時の入力契約が不定 | 縮小採用・反映済み |

## 2. EDGE-001: SPEC同一性、削除、ID再利用

### 指摘

Git変更集合は削除とrenameを保持するが、削除pathを基準版の文書IDへ対応付ける規則がなかった。
現在版だけを索引すると、承認済み文書、`rejected`、`cancelled`などの履歴文書を物理削除でき、
memberをcatalogから外すことで配下のSPECを検査から隠せる。

ADR-032の「現在は削除されているIDが別の意味で再出現」は、1つの基準版と現在版だけでは、
同一文書のrename・改訂と削除後の再利用を区別できない。

### 裁定

- 基準版と現在版を`(workspaceId, documentId)`で対応付ける。
- 同じIDが現在版にもあれば同一文書とし、path変更はrenameとして扱う。
- 基準版にあるIDが現在版にない場合は削除とし、`SPEC-STATE-TRANSITION-001`／`failed`とする。
- 基準版catalogと現在版catalogの両方を読み、member削除やpath変更で基準版SPECを隠さない。
- 現在集合の重複検出を維持し、`EAI-CORE-ID-003`はCore 1.0から削除する。
- Core検査を迂回した過去の削除後におけるID再利用禁止はGitレビューの責務とする。

ADR-032は[ADR-037](../02.設計書/10_決定記録/ADR-037_Git基準版間のSPEC同一性と削除規則.md)で
文書全体を置き換えた。

### 採用しない案

| 案 | 不採用理由 |
|---|---|
| semanticHash差でID再利用を判定 | renameと同時の正当な改訂を誤検出する |
| Git全履歴走査 | shallow cloneで結果が変わり、決定論性を失う |
| tombstone索引 | 永続状態と保守負荷を増やす |
| 終端文書だけ削除禁止 | `draft`や`open`の削除で理由記録を迂回できる |

## 3. EDGE-002: Stoppedとフェーズcheckpoint

### 指摘

Implement後に取り止めた場合、途中のコード・テストを残すか破棄するか、StoppedのGit記録へ混在させるかが
未定義だった。またフローを取り消しやすいGit commit境界がなかった。

### 裁定

- 取り止める文書IDは人間が明示し、CoreとSkillは関連文書から推測しない。
- Skillは残存差分を提示し、人間が破棄、保持、別TASKへの引継ぎ、Spikeへの隔離を選ぶ。
- CoreとSkillは途中成果物を自動削除しない。
- Stoppedのcommitは原則として状態、理由、Revision Historyだけを含める。
- 処遇と引継ぎ先は既存の`Rejection Rationale`または`Cancellation Rationale`へ記録する。
- 変更を伴うフェーズは個別commitへ分け、変更のないフェーズは現在HEADをcheckpointとして空commitを作らない。
- commitをsquashせず、取り消す場合は新しい順に`git revert`する。pushは別操作とする。

### 採用しない案

| 案 | 不採用理由 |
|---|---|
| `Stopped`をCore statusへ追加 | 既存の文書statusと進行支援の結果で区別できる |
| 成果物処遇のFrontmatter追加 | 既存Rationaleで説明でき、Schema拡張が不要 |
| CoreまたはSkillによる自動rollback | 利用者の未コミット成果物を破壊する可能性がある |
| 全フェーズの空commit | rollback可能性を増やさずGit履歴だけを増やす |

## 4. EDGE-003: verify異常終了

### 指摘

command結果の分類は定義済みだったが、bindingの実行順、1件の失敗後の継続、複数command名の代表名、
大量出力、timeout時の子孫processの扱いが未定義だった。

### 裁定

- bindingを正規識別子のCanonical JSON辞書順で逐次実行する。
- 1件が`failed`または`error`でも、解決済みの独立bindingを継続する。
- 複数command名の代表名は辞書順最小とする。
- stdoutとstderrは終了までdrainし、それぞれ末尾64 KiBまで保持して、超過した古いbyte列を破棄する。
- timeout時の停止と回収はCoreが直接起動したprocessまでを保証する。
- Coreがtimeoutのため送ったsignalは`termination: timeout`として記録する。

### 採用しない案

| 案 | 不採用理由 |
|---|---|
| verifyの並列scheduler | Phase 2の正しさに不要で実装分岐が増える |
| fail-fast設定 | 結果の網羅性を下げ、設定項目を増やす |
| 出力上限の設定化 | 固定安全上限で足り、workspace間の差を増やす必要がない |
| OS横断のprocess-tree完全制御 | OS差と依存が大きく、信頼された検証commandを前提とするCore 1.0には過大 |

## 5. EDGE-004: 入力読取りと同時編集

### 指摘

UTF-8必須規則はあるが、不正byte列、権限不足、I/O障害、読取り中の消失をどのstatusにするかがなかった。
また複数ファイル読取り中の同時編集を完全に排除する契約もなかった。

### 裁定

- `SPEC-INPUT-READ-001`を共通Diagnosticとして追加する。
- 不正UTF-8は成果物不適合として`failed`とし、置換文字で解析を継続しない。
- 権限不足、I/O障害、読取り中の消失はツール実行障害として`error`とする。
- 各入力は1回読み込んだbyte列を操作内で再利用する。
- 複数ファイルを横断する原子的snapshotと読取り後の変更検出はCore 1.0の保証外とし、編集と検査を
  branchまたはworktreeで分離する。

### 採用しない案

| 案 | 不採用理由 |
|---|---|
| ファイルシステム全体の原子的snapshot | 小規模チーム向け読取り専用Coreとして実装負荷が大きい |
| 全入力の前後hash再検査 | verify command自身の副作用と競合し、再実行分岐が増える |
| 不正UTF-8の置換継続 | 行・ID・hashが原文と異なる状態で成功し得る |

## 6. 反映先

- EDGE-001: ADR-037、EARS-AI規格/01・06、SPECファイル規定/01・06・07・12
- EDGE-002: SDDプロセス設計、運用設計、ユースケース設計、ADR-036 Notes
- EDGE-003: 共通アーキテクチャ、セキュリティ設計、SPECファイル規定/06、ADR-026・030 Notes
- EDGE-004: SPECファイル規定/06・07・11
- 実装fixture: 実装ロードマップ Phase 1〜3

## 7. 実装前チェックリスト

- [x] 削除pathを基準版の文書IDへ対応付けられる
- [x] renameと削除の判定がworkspace IDと文書IDで一意になる
- [x] member削除で基準版SPECを検査から隠せない
- [x] Stopped時の途中成果物を自動削除しない
- [x] フェーズごとのrollback可能なcommit境界がある
- [x] verifyの順序、失敗後の継続、代表名が決定論的である
- [x] 大量出力とtimeoutのCore保証範囲が固定されている
- [x] 不正UTF-8とI/O障害のstatusが区別されている
- [x] 非採用案に理由または再評価条件がある

4件すべてを裁定・反映したため、本レビューをClosedとする。
