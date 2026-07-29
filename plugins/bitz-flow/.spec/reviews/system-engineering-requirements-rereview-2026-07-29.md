---
id: FLW-REV-005
title: "bitz-flow v2 draft要件 システムエンジニアリング再レビュー"
status: active
version: 1.0
updated: 2026-07-29
owner: hide
decision: PASS
---

# FLW-REV-005 システムエンジニアリング再レビュー

## 最終判定

**PASS — 要件承認ゲートへ提示可能。**

これは人間によるdraft→approved裁定や実装開始承認ではない。更新後のactive設計とdraft要件を
一つのシステムとして実装可能・検証可能と判断する技術判定である。

## システム成立性

1. **目的と手段が閉じている**
   - モデル差をMandatory entry protocol、単一dispatcher、Operation Contractで吸収する。
   - compact/JSONは同じ決定論的resultから派生し、raw fallbackを通常経路から除外する。
2. **責務境界が実装単位になった**
   - Forward Recovery、GitHub冪等性、同一host排他、cross-host統制、process可搬性、
     atomic file I/O、人間承認、cleanupを独立要件へ分けた。
   - v2 draft要件23件すべてに1件以上のactive設計が`implements`を持つ。
3. **不可逆操作がfail-closedである**
   - plan/apply、expected SHA、外部再照会、effects上限、明示的人間承認を要求する。
   - remote削除の応答喪失でexpected SHAが残る場合も旧planを再利用しない。
4. **crash契約が実装可能である**
   - atomic replaceをpublication point、directory同期と最終検証完了をdurability commit pointとする。
   - commit前は完全な旧版または新版、commit後は完全な新版、その他は`INDETERMINATE`で停止する。
5. **段階出荷が安全境界と一致する**
   - M2未完了ならM1 Git writeを公開せずM0 read-onlyへ縮退する。
   - M3/M4は独立canaryを持ち、各境界自身がgreenの場合だけ縮退出荷できる。

## 要件品質

- EARS: event/stateに対するsystem responseと停止条件が明示されている。
- 検証可能性: unit、fault injection、benchmark、3platform canaryへ割当済み。
- Traceability: originは起票根拠、design implementsは実現対応として分離されている。
- Lifecycle: draft後継のsupersedesは空欄で、Promotion後のdeprecated裁定時だけ発効する。
- Governance: M1〜M5は初期budget、実績再校正、上限時の人間再裁定を持つ。

## 残余リスクと受容条件

| リスク | 受容条件 |
|---|---|
| cross-host coordinator誤割当 | M3/M4で重複0件。1件でPromotion停止 |
| explicit-humanをCLIが認証しない | SKILL/host境界、人間応答前apply 0件のeval |
| 初期budgetの見積誤差 | milestone開始時に実績と人間confirmation referenceで再校正 |
| platform/filesystem差 | 安全性を証明できなければwriteを`UNSUPPORTED` |

## 推奨する次工程

1. 人間へFLW-REV-004/005とdraft要件一覧を提示する。
2. 要件を個別または明示した集合としてapprovedへ裁定する。
3. approved後、M0対象だけを1 PRのtaskへ分解する。
4. M0の3platform evalが全条件greenになるまでM1を開始しない。

## 再レビュー条件

Operation Catalog、Python 3固定、明示的人間承認、cross-host統制、M0成功指標、
milestone縮退出荷境界のいずれかを変更する場合は、本判定を再訪する。
