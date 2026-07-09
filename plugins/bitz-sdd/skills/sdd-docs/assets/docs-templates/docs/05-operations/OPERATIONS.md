---
id: DOC-operations-overview
title: Operations & Release
status: active
version: 0.1.0
changeImpact: low
project_type: app            # app | library
updated: 2026-07-07
owner: <担当ハンドル>
superseded_by: null
---

<!--
  運用・リリースの「恒久手順とポリシー」。
  ドリフト境界: リリース回ごとのチェックリスト・実行状態は .spec/（STATE）。
                ここは再現可能な手順・方針（毎回同じもの）を持つ。
  分割時: app は runbooks/・slo.md・incident-response.md、
          library は release-process.md・support-matrix.md・deprecation-calendar.md を兄弟に。
-->

# Operations & Release

## app 固有（project_type: app）
- **デプロイ手順**: <環境・順序・ロールバック>
- **SLO / アラート方針**: <指標・閾値の考え方（実値は slo.md）>
- **インシデント対応**: <重大度定義・エスカレーション・ポストモーテム起票（→ 08）>
- **オンコール / ランブック**: <runbooks/ へ>

## library 固有（project_type: library）
- **リリースプロセス**: バージョン決定（changeImpact→SemVer）→ CHANGELOG → タグ →
  公開（NuGet / npm / crates.io）→ 公開後検証。
  - C#: `dotnet pack` / シンボル・ソースリンク / TFM 確認
  - TS: `npm publish` / `exports`・型出力確認 / provenance
  - Rust: `cargo publish` / `cargo semver-checks` / feature 確認
- **サポートマトリクス**: 対象ランタイム/言語バージョンと保守期間（support-matrix.md）
- **非推奨カレンダー**: 非推奨→削除の予定表（deprecation-calendar.md、public-api.md と整合）
- **CHANGELOG 方針**: changeImpact:medium 以上で必ず記載
