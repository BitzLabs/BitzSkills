---
id: FLW-REV-023
title: "FLW-DSN-017 v1.3 安全境界再レビュー"
status: active
version: 1.0
updated: 2026-08-22
owner: codex
decision: CONDITIONAL_PASS
---

# 設計レビュー統合レポート — FLW-DSN-017 v1.3

- **review_id**: FLW-REV-023
- **対象**: FLW-DSN-017 v1.3、FLW-NFR-014、FLW-TSK-106〜110、関連discovery
- **判定**: **CONDITIONAL_PASS**
- **集計スコア**: **2.91 / 5.00**（PASS ≥ 3.5 / CONDITIONAL_PASS ≥ 2.5）
- **Design Gate**: 条件未消化のため通過不可

## 観点別スコア

| 観点 | スコア | 重み | 主要所見 |
|---|---:|---:|---|
| consistency | 2.95 | 0.15 | identity型、activation所有権、解除契約が未接続 |
| data-integrity | 3.00 | 0.25 | 解除の原子性とuint64表現が不足 |
| operations | 3.30 | 0.20 | probe監督・隔離と運用task境界が不足 |
| risk | 2.67 | 0.25 | promotion差替え窓とnative path衝突 |
| business | 2.60 | 0.15 | 解除要件、信頼根、task実現性が不足 |

findings: 統合前18件 → 重複排除後11件（P0: 0 / P1: 4 / P2: 4 / P3: 3）

## 総括

v1.3で、NFDを暗黙変換せず拒否する公開境界、platform別file identity、active/reserved codec、
実processによるentrypoint確認という方向性は確立した。特に、後続lease実装を待たずにschema境界を
完了できるよう循環依存を分離した判断は妥当である。

一方、実際の安全境界として閉じるには、promotionの独立信頼根と線形化点、native filesystem pathの
可逆表現、quarantine解除の位置づけ、schema activationのtask所有権が不足している。P0はないが、
Design Gate前に修正すべきmajorが8件あるためPASSにはできない。

## P1 — Design Gate前に必須

### FLW-REV-023:SYN-002 — reserved schemaのactivation所有権

TSK-107〜109はcodecを実装する一方、schema inventoryを変更できるboundaryを持たない。
各recordのschema、inventory、codec、round-trip testを同じowner taskとrollback単位へ含める必要がある。

### FLW-REV-023:SYN-003 — quarantine解除契約

既存catalogは解除をreviewer裁定とし通常operationのNEXTを空にするが、v1.3は解除CLIを要求する。
裁定証拠を記録する管理経路か、新しいwrite operationかを人間が選び、後者ならEARS要件、capability、
target lease、最新token・chain head再照合、durable解除receiptを追加する必要がある。

### FLW-REV-023:SYN-005 — promotionの信頼根と線形化点

entrypoint自身の`runtime_version`や`sentinel_aware`自己申告だけでは証明にならない。配布側のversioned
baseline manifestを信頼根にし、親processが保持handleからartifact/import treeを測定する必要がある。
さらにprobe後からv2 stateのdurability commitまでregistry/cacheをleaseで固定するか、commit直前に
全identity・digest・registry generationを再照合し、その成功点をreceiptへ記録する必要がある。

### FLW-REV-023:SYN-006 — native pathとNFC

公開JSONの非NFC拒否は妥当だが、OS/Git由来pathをNFCへ変換してはならない。LinuxではNFC名とNFD名が
別directory entryとして共存でき、createの不在targetではfile identityも使えないため、承認scopeが衝突する。
native componentを可逆byte表現とplatform/path-encoding discriminatorで保持し、parent identityへ束縛する。

## P2 — 設計修正に含めるmajor

- **SYN-001**: regular file identityとdirectory identityを分離する。
- **SYN-004**: TSK-110へ運用CLI、receipt/SLI集計、通知adapterの実装boundaryを追加する。
- **SYN-007**: fencing tokenをcross-languageで精度喪失しない表現へ変更する。
- **SYN-008**: 未信頼probeのtimeout、process tree終了、出力上限、権限・環境・network・FS隔離を固定する。

## P3 — 併せて整える事項

- **SYN-009**: M2通常系のplatform別`UNSUPPORTED` 0件をdiscovery metricsへ反映する。
- **SYN-010**: SHA-256 digestのprefixを含むcanonical字句形式を共通化する。
- **SYN-011**: runtime versionのSemVer受理・比較規則を固定する。

## 実装チェック項目（設計findingとは分離）

TSK-106は`implementing`であり、v1.3をまだ実装していないこと自体は設計findingにしていない。
再設計後の実装完了判定では次を機械検証する。

- active schemaとruntime codecの双方向field・round-trip一致
- 非NFC key/value、surrogate、NULのdecode前拒否と副作用0件
- common-dirからのcomponent非追随sentinel I/Oとopen前後identity照合
- reserved schemaのproducer/consumer登録0件
- logical version mappingではなく、closed policy・実inventory・実process evidenceによるpromotion
- v1とv2型の混在、旧runtime、差替え、timeout、probe副作用の各陽性対照

## CONDITIONAL_PASSの通過条件

- [ ] SYN-001〜008を設計とtask boundaryへ反映する
- [ ] GP-001〜004を人間が裁定する
- [ ] 修正後に5観点の再レビューを行い、PASSを得る

## 人間裁定（2026-08-22）

userはP1〜P3をすべて推奨案で再設計する方針を承認した。GP-001はowner別activation manifest、GP-002は
通常operationではない裁定証拠記録用の管理経路、GP-003は配布baseline・親測定・commit直前再照合、
GP-004は可逆native path表現として受領した。P2/P3も同じv1.4改訂へ含め、独立再レビューまでは
本レビューのCONDITIONAL_PASSを維持する。

その後の正式再レビュー前自己検討で、userはシステム設計案と実運用設計案の統合を承認した。
v1.5ではSafety KernelとOperations Control Plane、不変operation journal、運用CLI、reviewer key lifecycle、
support/retention profile、4段階rolloutを追加し、実装を9責務へ再分割した。この追加設計も
本レビューの旧判定だけでは通過扱いにせず、v1.5を対象とする独立再レビューを必要とする。

FLW-REV-024でv1.5を独立再レビューし、本レビューのSYN-001〜011が対象とした元の根本原因は
解消済みと確認したため、各findingをresolvedへ更新した。v1.5で新たに見つかった問題は
FLW-REV-024へ分離し、本レビューの過去判定自体は変更しない。

## 持ち越し

本件外の過去レビュー由来で未解消のP0/P1は88件あり、`FLW-REV-023.json`の`carried_over`へ保持した。
この数には過去の監査台帳上`open`または`tracked`のまま残る項目が含まれ、本設計の新規finding数とは分離する。

## 人間への裁定依頼

この判定は推奨である。現状ではDesign Gateを通過させず、GP-001〜004の方針を裁定して設計を修正し、
再レビュー後にGateを判断することを推奨する。
