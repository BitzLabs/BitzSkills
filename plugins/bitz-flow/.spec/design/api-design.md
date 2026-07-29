---
id: FLW-DSN-003
title: "bitz-flow v2 公開CLI・結果契約"
status: active
version: 1.1
updated: 2026-07-29
owner: hide
implements: FLW-FR-003, FLW-FR-004, FLW-FR-005, FLW-FR-006, FLW-FR-007, FLW-FR-008, FLW-FR-009, FLW-FR-010, FLW-FR-011, FLW-NFR-002
origin: FLW-DSC-001
---

# FLW-DSN-003 bitz-flow v2 公開CLI・結果契約

## 公開入口

```text
python3 <flow-core>/scripts/flow.py
  [--repo PATH] [--format compact|json] [--timeout-seconds N]
  <domain> <action> [operation options] [--apply] [--confirm OPERATION_ID]
  [--approval-ref REF]
```

- `--repo` は省略時にcurrent directoryからrepo rootを解決する。
- `--format compact` が既定。JSONはテスト・他ツール連携用。
- timeoutはread 1〜300秒、write 10〜300秒、既定30秒。
- 状態変更actionは既定plan。applyにはplanが返した`operation_id`の完全一致を要求する。
- `--confirm`は対象・鮮度・effectsの一致確認であり、人間本人の承認を証明しない。
- `approval: explicit-human`の操作はSKILL.mdが人間の明示応答まで停止する。応答参照を残せる
  実行環境だけ任意の`--approval-ref`を渡すが、CLIは真正性を主張しない。

## domain

| domain | actions |
|---|---|
| `repo` | `inspect`, `capabilities` |
| `git` | `status`, `diff-summary`, `diff-detail`, `log`, `branches`, `conflicts`, `fetch`, `stage`, `commit`, `sync`, `publish-branch`, `delete-remote-branch` |
| `worktree` | `plan`, `create`, `list`, `resume`, `audit`, `finish`, `discard` |
| `issue` | `list`, `view`, `search`, `prepare`, `publish`, `edit`, `comment`, `close`, `verify-link`, `reconcile-link` |
| `pr` | `prepare`, `publish`, `checks`, `ready`, `merge-plan`, `merge`, `post-merge` |
| `release` | `plan`, `changelog`, `changelog-apply`, `notes`, `tag-create`, `tag-push`, `draft`, `publish` |

未対応操作は `UNSUPPORTED` を返して停止し、生コマンドfallbackを案内しない。頻出する
未対応操作はspec-issueとして操作カタログへ追加する。

## 内部result object

```json
{
  "schema": "bitz-flow/result/v1",
  "result_digest": "sha256:...",
  "operation": "git.status",
  "ok": true,
  "code": "OK",
  "exit_code": 0,
  "repo": "/canonical/repo",
  "snapshot": "sha256:...",
  "operation_id": null,
  "idempotency_id": null,
  "approval": {"required": "none", "source": null, "reference": null},
  "summary": "2 files changed",
  "data": {
    "target": {},
    "preconditions": [],
    "effects": [],
    "postconditions": [],
    "evidence": [],
    "completed_steps": [],
    "remaining_steps": [],
    "cause": null,
    "items": [],
    "page": {"shown": 0, "total": 0, "cursor": null}
  },
  "audit": {"tool_version": "2.0.0", "started_at": "...", "finished_at": "..."},
  "invocation": {"id": "uuid:...", "parent_id": null, "attempt": 1, "stage": "inspect"},
  "warnings": [],
  "truncated": false,
  "next_actions": []
}
```

- key集合は加算のみ。意味変更はschema majorを上げる。
- `data`はoperation別JSON Schemaを持ち、未知fieldを許容する。
- `audit`はactor本人性を主張せず、秘密値を含まないtool version、時刻、canonical targetを保持する。
- `invocation.id`は試行ごとのランダム識別子でoperation IDと分離する。reconcileは`parent_id`で
  元試行へ結び、attemptとstageで順序を復元できる。
- `result_digest`は自身を除くresult objectを、UTF-8・key辞書順・余分な空白なし・JSON schemaで
  許可した整数表現へ正規化したbyte列のSHA-256とする。呼出側は1 invocationの完全なJSON resultを
  1保存単位とし、利用前にdigestを再計算する。部分抜粋は監査原本として扱わない。
- digestは保存・転送時の破損と不一致を検出するもので、resultとdigestを同時変更できる主体への
  耐改ざん性は保証しない。耐改ざん監査が必要な呼出側は署名または追記専用storageを別途用意する。
- result自体は内部永続保存しない。呼出側が監査証跡として保存する場合も、schemaで除外した
  credential、environment、raw stdout/stderrを追加してはならない。
- pathはrepo相対表示を既定とし、repo外targetだけcanonical absolute pathを返す。
- `summary`は事実だけを記述し、推奨判断は`next_actions`へ分離する。
- raw command、stdout、stderr、environment、credentialは出力しない。

## compact renderer

```text
OK git.status snapshot=sha256:ab12 branch=feat/x changed=2 ahead=1 behind=0
 M src/a.py
?? tests/test_a.py
NEXT git.diff-summary snapshot=sha256:ab12
```

固定token、固定順序、1項目1行を守る。0件fieldやnullは省略する。blocking/errorを最優先し、
次に変更対象、通常項目の順で表示する。上限超過時は`TRUNCATED shown=50 total=213
cursor=<snapshot-bound>`と絞込みactionを必ず返す。mutationに全件確認が必要ならapplyを`BLOCKED`。

## 終了コード

| exit | code | 意味 |
|---:|---|---|
| 0 | `OK` / `READY` / `DONE` | 正常 |
| 2 | `INVALID_INPUT` | 引数・schema・ref・path不正 |
| 3 | `BLOCKED` | 前提、policy、CI、依存で続行不可 |
| 4 | `APPROVAL_REQUIRED` | plan済みで必要な外部裁定待ち |
| 5 | `UNAVAILABLE` | Git/gh/auth/network/timeout等が利用不能 |
| 6 | `STALE` | snapshot/head/remoteがplan時点から変化 |
| 7 | `PARTIAL` | 一部副作用完了。外部状態から再開可能 |
| 8 | `UNSUPPORTED` | capabilityまたは操作未対応 |
| 9 | `INDETERMINATE` | 副作用の成否を一意に判定できずreconcileが必要 |

下位Git / ghの終了コードは`data.cause`の許可語彙へ正規化し、そのまま公開しない。

## operation ID

`operation_id = sha256(schema + operation + canonical target + expected snapshot + planned effects)`
とする。秘密値と時刻は含めない。同じ前提・同じplanは同じIDを返す。applyは直前に全前提を
再照会し、IDを再計算して一致した場合だけ実行する。

operation IDは承認tokenではない。重複副作用の照合にはoperation別`idempotency_id`と
postconditionを使う。照合規則はFLW-DSN-012/013を正とする。

## 代替案

- JSONだけを既定: key overheadが常時発生するためcompactを既定にする。
- 短い独自keyだけのJSON: tokenは減るが意味と保守性を損なうため不採用。
- 下位exit code透過: Git / gh更新で公開契約が揺れるため不採用。

## 影響とロールバック

全scriptが本契約へ移行する破壊的変更。公開actionの正はFLW-DSN-012、移行はFLW-DSN-011に従う。
v1 script互換shimは作らず、plugin major versionで移行を明示する。
