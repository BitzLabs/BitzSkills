---
id: FLW-REV-003
title: "bitz-flow v2 システムエンジニアリングレビュー"
status: active
version: 2.0
updated: 2026-07-29
owner: hide
decision: PASS
---

# FLW-REV-003 システムエンジニアリングレビュー

## 結論

bitz-flow v2の設計はDesign Gateへ提出できる。単一dispatcher、Operation Contract、
Forward Recovery、段階releaseが一つのシステム境界として閉じ、M0から実装可能な粒度になった。
ただし、本判定は設計品質へのPASSであり、要件承認や実装開始を代替しない。

## システムとして成立した点

1. **SKILLとscriptの責務が明確**
   - SKILLは意図判定、手順選択、人間との対話を担う。
   - `flow.py`は入力、policy、副作用、結果を決定論的に扱う。
   - モデル差を長い手順文ではなく、Mandatory entry protocolと共通resultで吸収する。
2. **操作の正が一本化された**
   - FLW-DSN-012のOperation ContractからCLI、policy、schema、test、next actionを導出する。
   - Git/ghの任意コマンド実行機ではなく、目的別の固定operation catalogとして境界を保つ。
3. **失敗を通常系として扱える**
   - 全writeが安定Recovery IDを持ち、応答喪失後も外部状態からDONE、PARTIAL、
     INDETERMINATEを判定する。
   - 自動補償で削除・上書きせず、確認済み副作用を保全して前進再開する。
4. **安全性と可搬性が両立している**
   - process tree収束、bounded output、秘密値除外、atomic file I/Oを3platform別に規定した。
   - 安全性を証明できないplatform/filesystem/並行条件ではUNSUPPORTEDへ縮退する。
5. **GitHub差異を制御可能**
   - 高水準`gh`を優先し、Must不足分だけsource allowlist固定adapterを使う。
   - 利用者入力のendpointやGraphQLを受けず、透過proxyにはしない。
6. **v1→v2の規範競合を解消した**
   - Promotion Gateまでv1-currentを維持し、v2をprerelease canaryで検証する。
   - 失敗時はv1をpinしてread-only smoke testを行い、v2の外部成果物は保全する。

## 重要な設計判断

### 明示的人間承認

hookや承認serviceを実装しないため、CLIは人間本人を認証しない。CLIが保証するのはplan鮮度、
operation ID、preconditions、effects上限であり、`explicit-human`はSKILL／
オーケストレーション層の前提統制である。この境界は制約の隠蔽ではなく、実装可能性に即した判断である。
3platform evalで「人間応答前apply 0件」を出荷条件にし、規律外callerはthreat modelへ残す。

### Python継続の条件

初期実装はPython標準ライブラリでよい。ただし「Pythonだから採用」ではなく、次を満たす間だけ継続する。

- M0でplatform別Dispatcher Invocation Rate 95%以上、SFCR 90%以上。
- 必須field・golden schema・decision parity 100%。
- timeout後のprocess tree収束とatomic replaceを各platformのfixtureで証明。
- 1条件でも満たせなければ後続機能を増やさず、入口、契約、実装方式を再評価。

Goは現時点で導入しない。Pythonでprocess tree、locking、atomic I/O、配布一貫性のいずれかを
3platformで安定して満たせず、その失敗が局所修正では解決しない場合だけ、Contract Kernelの
実装言語候補として比較する。MCP、Rust、hook、透過proxyは選択肢へ戻さない。

## 残余リスク

| リスク | 影響 | 統制 |
|---|---|---|
| 別hostの同一WorkUnit競合 | 重複Issue/PR | single coordinator、marker重複検出、canary即時停止 |
| flow-doctorのschema drift | モデル間結果差 | 共通golden fixtureをM1 release gate化 |
| 「200UE」の原意未確定 | M3の運用期待ずれ | M3要件承認前に人間裁定 |
| M1〜M5の膨張 | 投資超過・完了遅延 | 要件・task分解時にtimeboxと縮退出荷境界を設定 |
| explicit-humanの規律外caller | 無承認apply | CLI保証外と明記、SKILL eval、host権限管理 |

## 推奨する次工程

1. 人間がSI-FLW-002〜005を個別にaccept/rejectする。
2. 人間がDesign Gateを承認し、v2設計をactive化する。
3. PASSした設計からv2 FR/NFR/CONをEARSでdraft起票する。
4. 人間が要件をapprovedにした後、M0だけをtask分解・実装する。
5. M0出口未達ならM1へ進まずpivotを裁定する。

## 最終判定

**PASS — Design Gateへ提出可。**
