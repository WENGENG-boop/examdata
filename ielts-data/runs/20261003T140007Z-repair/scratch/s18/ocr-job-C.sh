#!/usr/bin/env bash
# S18 batch OCR job C: books 6,7,8
cd /c/Users/weo/Desktop/api
PY=ielts-data/tools/ocr-venv/Scripts/python.exe
OCR=ielts-data/runs/20261003T140007Z-repair/scratch/s06/s06_ocr.py
OUT=ielts-data/runs/20261003T140007Z-repair/official-keys/ocr
LOG=ielts-data/runs/20261003T140007Z-repair/scratch/s18/ocr-job-C.log
: > "$LOG"
run(){ b=$1; pages=$2; echo "=== book $b pages $pages start $(date +%H:%M:%S) ===" >> "$LOG"; PYTHONIOENCODING=utf-8 "$PY" "$OCR" --book "$b" --pages "$pages" --dpi 400 --out "$OUT/book_$b.json" >> "$LOG" 2>&1; echo "book $b exit=$? $(date +%H:%M:%S)" >> "$LOG"; }
run 6 "$(seq -s, 152 161)"
run 7 "$(seq -s, 157 166)"
run 8 "$(seq -s, 151 160)"
echo "JOB C DONE $(date +%H:%M:%S)" >> "$LOG"
