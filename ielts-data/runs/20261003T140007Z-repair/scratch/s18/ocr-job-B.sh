#!/usr/bin/env bash
# S18 batch OCR job B: books 3,4,5
cd /c/Users/weo/Desktop/api
PY=ielts-data/tools/ocr-venv/Scripts/python.exe
OCR=ielts-data/runs/20261003T140007Z-repair/scratch/s06/s06_ocr.py
OUT=ielts-data/runs/20261003T140007Z-repair/official-keys/ocr
LOG=ielts-data/runs/20261003T140007Z-repair/scratch/s18/ocr-job-B.log
: > "$LOG"
run(){ b=$1; pages=$2; echo "=== book $b pages $pages start $(date +%H:%M:%S) ===" >> "$LOG"; PYTHONIOENCODING=utf-8 "$PY" "$OCR" --book "$b" --pages "$pages" --dpi 400 --out "$OUT/book_$b.json" >> "$LOG" 2>&1; echo "book $b exit=$? $(date +%H:%M:%S)" >> "$LOG"; }
run 3 "$(seq -s, 153 162)"
run 4 "$(seq -s, 153 162)"
run 5 "$(seq -s, 153 162)"
echo "JOB B DONE $(date +%H:%M:%S)" >> "$LOG"
