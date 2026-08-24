# 裁定記録 — M2の対象platformを当面Linux専用へ限定する

- **日付**: 2026-08-24
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `FLW-DSN-017` §1.1 の3 OS保証、`FLW-REV-028:GP-003`
- **裁定原文**: 「当面 Linux 専用で進めましょう。GP-005 から着手して」
- **提示済み提案**: `FLW-REV-028` v2.0 が、macOSは既定APFSがcase-insensitiveのため
  `plan()`が未捕捉例外になり、WindowsはSID取得手段が無く常に不支持であると判定した。
  §1.1 は3 OSで同じlogical resultへ収束すると保証するが、実際に動作するのは
  case-sensitiveなLinuxのみである。選択肢は「当面Linux専用と認める」か
  「macOS/Windowsを作り込む」かであると提示した。
- **記録者**: claude（裁定者の明示指示に基づく代行記録・実行者未検証）

## 裁定

M2 Local Safety Profileの**保証対象を当面Linuxのみへ限定する**。
macOSとWindowsは実装を残すが保証対象から外し、probeは理由付きで不支持へ閉じる。

## `GP-003` への応答

`response: accepted`。§1.1 の保証を実装能力へ揃える2案のうち、
**「保証をLinuxへ限定する」**を採る。

## この裁定が `GP-005` の実装方針を変える点

`GP-005`（case-insensitive volumeでの未捕捉例外）の是正には2つの道があった。

- **案A**: probeがfolded_componentを導出し、case-insensitive volumeでもplanを成立させる。
- **案B**: case-insensitive volumeを`UNSUPPORTED_FILESYSTEM`へ閉じる。

**案Bを採る。** 理由は次のとおり。

1. Linux専用スコープでは案文の主対象（macOSのAPFS）が保証対象外になる。
   Linuxのcase-insensitive mount（ext4 casefold、vfat／exfat、ciopfs等）は例外的である。
2. 案Aはfolding規則を新たに定義することになるが、**実物のcase-insensitive volumeで
   観測できない環境で規則を作れば、また「検証していない性質の主張」になる**。
   §3.1 は「Unicode normalizationで別directory entryを同一scopeへ畳み込まない」と
   規定しており、誤った折り畳みはcollision排除を壊す。
3. §3.1 は既に「case-insensitiveかどうかを安全に判定できない不在targetは
   `UNSUPPORTED_FILESYSTEM`とする」と定めている。案Bはその延長であり新規の概念を要さない。

案Aは、実物のcase-insensitive volumeを観測できる環境が用意できた時点で再検討する。

## `GP-005` で必須とする範囲

case-insensitiveの扱いに関わらず、**未捕捉例外を公開経路へ出さないこと**は必須である。
`ContractError`が`ValueError`派生でCLIの捕捉対象外だった事実は、
特定の1経路の問題ではなく**公開result契約の穴**である。dispatcher単位の網を置き、
「公開経路の未捕捉例外0件」を機械検査する。

## 適用範囲

- `FLW-DSN-017` §1.1／§3.2／§13.5 の保証範囲をLinuxへ限定する。
- `worktree_platform.py` に保証scopeを明示し、対象外platformは理由付きで閉じる。
- macOS／Windowsのprobe実装は**削除しない**（将来の再開のため残す）。
- ROADMAPの3 platform出口条件は`agent platform`軸（claude／codex／antigravity）で
  あり本裁定の影響を受けない（`SI-FLW-092` の用語分離に従う）。

## 再開条件

macOS／Windowsを保証対象へ戻すには、当該OS上で実環境probeを実走し、
`SUPPORTED`判定と全crash境界の証跡をmachine evidenceへ残すこと。
Windowsは加えてSID取得の実装を要する。
