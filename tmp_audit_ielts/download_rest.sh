#!/bin/bash
# 独立审查：补齐下载剩余 11 本 PDF 并校验 SHA256 vs LFS oid（3 并发）
cd /c/Users/weo/Desktop/api/tmp_audit_ielts
LOG=downloads/download_log_full.tsv
mkdir -p downloads

worker() {
  local line="$1"
  local book size oid url
  IFS=$'\t' read -r book size oid url <<< "$line"
  local out="downloads/book_${book}.pdf"
  local start=$(date +%s)
  local meta=$(curl -sS -L --retry 2 --retry-delay 3 -o "$out" -w "%{http_code}\t%{size_download}\t%{speed_download}\t%{time_total}" "$url" 2>>downloads/curl_err2.txt)
  local end=$(date +%s)
  local actual=$(stat -c %s "$out" 2>/dev/null || echo 0)
  local sha=$(sha256sum "$out" 2>/dev/null | cut -d' ' -f1)
  local magic=$(head -c 5 "$out" 2>/dev/null | tr -d '\0')
  local match="MISMATCH"; [ "$sha" = "$oid" ] && match="MATCH"
  printf "%s\tbook=%s\tcurl=%s\tsize_expected=%s\tsize_actual=%s\twall_s=%s\tsha256=%s\toid=%s\tmagic=%s\t%s\n" \
    "$(date -Iseconds)" "$book" "$meta" "$size" "$actual" "$((end-start))" "$sha" "$oid" "$magic" "$match" >> "$LOG"
  echo "book $book: curl=[$meta] actual=$actual wall=$((end-start))s magic=$magic $match"
}
export -f worker
cat dl_list_rest.tsv | xargs -d '\n' -P 4 -I{} bash -c 'worker "$@"' _ {}
echo "REST_DONE"
