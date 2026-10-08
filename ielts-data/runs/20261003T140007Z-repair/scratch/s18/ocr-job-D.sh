#!/usr/bin/env bash
# S18 batch OCR job D: books 11,12,13,14,15,17
cd /c/Users/weo/Desktop/api
PY=ielts-data/tools/ocr-venv/Scripts/python.exe
OCR=ielts-data/runs/20261003T140007Z-repair/scratch/s06/s06_ocr.py
OUT=ielts-data/runs/20261003T140007Z-repair/official-keys/ocr
LOG=ielts-data/runs/20261003T140007Z-repair/scratch/s18/ocr-job-D.log
: > "$LOG"
run(){ b=$1; pages=$2; echo "=== book $b pages $pages start $(date +%H:%M:%S) ===" >> "$LOG"; PYTHONIOENCODING=utf-8 "$PY" "$OCR" --book "$b" --pages "$pages" --dpi 400 --out "$OUT/book_$b.json" >> "$LOG" 2>&1; echo "book $b exit=$? $(date +%H:%M:%S)" >> "$LOG"; }
run 11 "$(seq -s, 117 124)"
run 12 "$(seq -s, 117 124)"
run 13 "$(seq -s, 119 126)"
run 14 "$(seq -s, 120 127)"
run 15 "$(seq -s, 120 127)"
run 17 "$(seq -s, 119 126)"
echo "JOB D DONE $(date +%H:%M:%S)" >> "$LOG"
