"""テキスト出力向けの、文字列の無害化の処理。

結果・診断・終了コード §7に従い、C0（U+0000〜U+001F）、DEL（U+007F）、
C1（U+0080〜U+009F）を ``\\uXXXX`` （バックスラッシュ1文字と`u`と小文字の16進4桁）へ置換する。
この変換はテキストの表示だけに適用し、JSONの結果と並べ替えの順序を変えない。
"""

from __future__ import annotations


def sanitize_control_chars(value: str) -> str:
    out: list[str] = []
    for ch in value:
        code = ord(ch)
        if code <= 0x1F or code == 0x7F or 0x80 <= code <= 0x9F:
            out.append(f"\\u{code:04x}")
        else:
            out.append(ch)
    return "".join(out)
