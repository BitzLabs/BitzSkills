---
id: SI-FLW-022
raised_by: ユーザー要望（2026-08-07 セッション）
target: discovery/scope.md（MoSCoW）・FLW-FR-011（flow-doctor v2環境診断）・新規 settings audit operation
proposed_change_type: new
status: open
---
- **目的**: Organization / repository の**設定そのもの**を bitz-flow から読み取り、
  セキュリティ観点の逸脱を検出できるようにする（read-only の設定 audit）。
  設定の**変更**は安全境界が全く異なるため本 issue に含めず、`SI-FLW-023` へ分離する
  （分割原則「動作変更と構造変更を混ぜない」／read が先、write が後）。

- **現状（なぜ未対応か）**:
  - `discovery/scope.md` の Should にあるのは「branch protection / merge queue の
    **capability 読取**と merge 待機」だけである。これは *merge できるか* を判定するための
    能力検出であり、*設定が望ましい状態か* を点検する audit ではない。
  - `FLW-FR-011`（flow-doctor v2）が診断するのは Git / GitHub CLI / Python /
    remote・default branch / 認証 scope であり、repository・organization の**設定内容**は対象外。
  - したがって「secret scanning が有効か」「default branch が保護されているか」
    「force push が禁止されているか」「Dependabot alert が有効か」等を答える要件は
    v2 に**1件も存在しない**。

- **提案する修正**:
  1. `discovery/scope.md` に read-only の **settings audit** を位置づける
     （推薦は Should — M0〜M5 の出荷順序を崩さず、M1 の doctor 系と同じ read-only 境界に載る）。
  2. 新規 operation `settings audit`（仮）を FR として起票する。返すのは
     「観測値 + 期待値 + 逸脱一覧」であり、修正は行わない。
  3. 期待値（ベースライン）はハードコードせず、リポジトリ側の宣言ファイル
     （例: `.spec/` 外の設定ポリシー file）または引数で与える。bitz-flow は
     「ポリシーの正」を持たない。
  4. 高水準 `gh` で取れない項目は、`FLW-DSN-007` と同じく **method / path / field を
     source code へ固定した内部 adapter** で扱う（`scope.md` の Won't「任意 `gh api`
     passthrough」に抵触させない）。
  5. 権限不足（admin scope なし）・organization 側 API が 403 の場合は失敗ではなく
     `UNAVAILABLE` / 部分結果 + 省略の可視化として返す（`FLW-FR-003` の結果契約に従う）。

- **対象ファイル**: `plugins/bitz-flow/.spec/discovery/scope.md`、
  新規 `requirements/FLW-FR-0xx`、新規または `FLW-DSN-014`（capability contract）への追記、
  `plugins/bitz-flow/skills/flow-doctor/SKILL.md`（診断の役割分界の明記）。

- **確認観点**:
  - **認証情報を読まない制約を守れるか**: `scope.md` の制約「GitHub 認証情報は `gh` に委ね、
    bitz-flow は token・credential を読み取らない」。設定 audit の出力に token・secret 値・
    Actions secret の中身を含めない（**名前と有無だけ**）。
  - organization 単位の照会は権限が repository 単位と異なる。scope 不足時の縮退が
    決定論的か。
  - GitHub Free / Team / Enterprise で存在する設定項目が異なる。capability 検出で
    「非対応」と「無効」を区別できるか（区別せずに逸脱と報告してはならない）。
  - flow-doctor（環境診断）との責務分界。**環境が使えるか**と**設定が望ましいか**を
    同一 operation に混ぜない。
  - 出力 byte 予算（`FLW-NFR-008`）。設定は項目数が多く compact 出力が膨らみやすい。

- **影響推定・ロールバック**: read-only の新規 operation 追加であり、既存の M0〜M5 の
  契約を変更しない。scope 追加のため要件起票 → 人間 approve の通常フローが必要
  （契約に触れるので軽量レーン不可）。単独 revert 可能。

- **依存**: なし。`SI-FLW-023`（設定変更）が本 issue に依存する。
  M0 出口未達のため、accept されても着手順序は M1 以降。

- **予備判定（推薦・裁定ではない）**: **accept 推薦**。
  | 判定軸 | 結果 |
  |---|---|
  | 既存要件との矛盾 | なし（`FLW-FR-011` とは責務分界を明記すれば共存。supersedes 不要） |
  | ガードレール抵触 | なし（read-only。認証情報を出力しない制約を要件本文で明示すること） |
  | 影響範囲 | `spec_inspect.py --impact FLW-FR-011` = 依存成果物 0 件 |
  | 軽量レーン適否 | **不可**（公開 CLI 契約と scope に触れる。要件化 + Design Gate 相当の裁定が要る） |
