#!/bin/bash
# 独立审查：真实下载 9 本 PDF 并校验 SHA256 vs LFS oid
cd /c/Users/weo/Desktop/api/tmp_audit_ielts
LOG=downloads/download_log.tsv
: > "$LOG"
while IFS=$'\t' read -r book size oid url; do
  out="downloads/book_${book}.pdf"
  start=$(date +%s)
  meta=$(curl -sS -L --retry 2 --retry-delay 3 -o "$out" -w "%{http_code}\t%{size_download}\t%{speed_download}\t%{time_total}" "$url" 2>>downloads/curl_err.txt)
  end=$(date +%s)
  actual=$(stat -c %s "$out" 2>/dev/null || echo 0)
  sha=$(sha256sum "$out" 2>/dev/null | cut -d' ' -f1)
  magic=$(head -c 5 "$out" 2>/dev/null | tr -d '\0')
  match="MISMATCH"; [ "$sha" = "$oid" ] && match="MATCH"
  printf "%s\tbook=%s\tcurl=%s\tsize_expected=%s\tsize_actual=%s\twall_s=%s\tsha256=%s\toid=%s\tmagic=%s\t%s\n" \
    "$(date -Iseconds)" "$book" "$meta" "$size" "$actual" "$((end-start))" "$sha" "$oid" "$magic" "$match" >> "$LOG"
  echo "book $book: curl=[$meta] actual=$actual wall=$((end-start))s magic=$magic $match"
done < dl_list.tsv
echo "ALL_DONE"
