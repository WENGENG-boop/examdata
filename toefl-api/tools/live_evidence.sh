#!/usr/bin/env bash
# live_evidence.sh — 实跑服务的公证采集：每个端点存 body + HTTP 状态码/耗时。
# 用法：tools/live_evidence.sh <base_url> <out_dir>
# 例：  tools/live_evidence.sh http://127.0.0.1:8123 probe/live_evidence
set -u
BASE="${1:-http://127.0.0.1:8123}"
OUT="${2:-$(dirname "$0")/../probe/live_evidence}"
mkdir -p "$OUT"

fetch() {
  local name="$1" path="$2" tmo="${3:-240}" code time
  read -r code time < <(curl -sS -m "$tmo" -o "$OUT/$name.body.json" -w '%{http_code} %{time_total}' "$BASE$path")
  if [ -z "${code:-}" ]; then code=000; time=0; fi
  printf '%s %s %s\n' "$name" "$code" "$time" > "$OUT/$name.meta.txt"
  echo "$name http=$code t=$time"
}

fetch info                 "/api/v1/toefl/info"                                30
fetch coverage             "/api/v1/toefl/coverage"                            120
fetch sets_era             "/api/v1/toefl/sets?era=tpo-51-54&page-size=4"      60
fetch sets_single          "/api/v1/toefl/sets?tpo=54&page-size=1"             60
fetch get_tpo30            "/api/v1/toefl/get?set=tpo-30"                      60
fetch questions_reading    "/api/v1/toefl/questions?set=tpo-30&section=reading&item=1"  240
fetch questions_listening  "/api/v1/toefl/questions?set=tpo-54&section=listening&item=1" 240
fetch search_punctuated    "/api/v1/toefl/search?q=punctuated&limit=8"         240
fetch ctrl_health          "/health"                                           30
fetch ctrl_papers          "/papers?limit=1"                                   60
fetch ctrl_taxonomy        "/taxonomy"                                         60
fetch ctrl_ielts_info      "/api/v1/ielts/info"                                60
echo "saved to $OUT"
