f="$TMPDIR/bitz-order"
n=$(cat "$f" 2>/dev/null)
n=$((${n:-0} + 1))
printf '%s %s\n' "$1" "$n"
if [ "$n" = "$2" ]; then rm -f "$f"; else printf '%s\n' "$n" > "$f"; fi
