# 裁定記録 — M1開始前4 spec-issueのレビュー結果

- **日付**: 2026-08-11
- **対象**: SI-FLW-006、SI-FLW-029、SI-FLW-037、SI-FLW-038
- **ユーザー指示**: 「進めましょう」
- **実行方針**: 4件をacceptする前提で多観点レビューを行い、重大な矛盾がある場合は遷移を停止する。
- **レビュー証跡**: FLW-REV-008（FAIL、集計2.50、P0 4件、P1 4件）

## 裁定

4件の`open → accepted`遷移は**保留**する。M1 Design Gateは通過させず、Git writeの実装へ進まない。
理由は、write出力打切り後のblind retry、失敗時NEXTからの危険な再apply、commit成功の因果誤帰属、
platform証跡のTOCTOU・結果選択バイアスが、現案では閉じていないためである。

## 再提示条件

1. SI-FLW-006へwrite時のreconcile優先とINDETERMINATE閉鎖を取り込む。
2. SI-FLW-029へ安全なrecovery class表と、停止時の空NEXT・human guidanceを取り込む。
3. SI-FLW-037をM1横断要件へ昇格し、隔離、秘密値、定量qualificationを固定する。
4. SI-FLW-038でcompatibility keyとevidence IDを分離し、append-only attempt台帳を固定する。
5. REC-COMMITへ今回のapplyを識別する因果証跡を追加する。
6. M1の6 PR・20 session予算を公開契約、qualification、evidence合成、confirmationへ再配分する。

上記を仕様案へ反映し再レビューがPASSまたは条件を消化可能なCONDITIONAL_PASSとなった時点で、
4件のacceptとM1 Design Gateを改めて人間へ提示する。

## 再レビュー後の裁定

- **追加ユーザー裁定**: 「提案で進めましょう」
- **補強結果**: FLW-FR-013、FLW-NFR-011、FLW-NFR-012をdraft起票し、FLW-DSN-010/013/014、
  ROADMAP、4 spec-issueへFLW-REV-008のP0/P1を反映した。
- **再レビュー**: FLW-REV-009はPASS（4.20、P0/P1 0件）。

ユーザー裁定と再レビューPASSに基づき、SI-FLW-006、SI-FLW-029、SI-FLW-037、SI-FLW-038を
acceptedとし、FLW-FR-013、FLW-NFR-011、FLW-NFR-012をapprovedとする。補強済み設計差分を
M1再Design Gateの承認対象とし、実装はqualificationを最初のblocking taskとして分解する。
