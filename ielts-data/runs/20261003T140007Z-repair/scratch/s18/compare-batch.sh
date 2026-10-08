#!/bin/bash
# S18 compare batch: PDF-extracted official answers vs index answers, strict mode.
# Run from api root. Writes per-cell compare JSON + log to scratch/s18/compare/.
cd /c/Users/weo/Desktop/api || exit 1
R=ielts-data/runs/20261003T140007Z-repair
PY=examdata/.venv/Scripts/python.exe
OUT=$R/scratch/s18/compare
mkdir -p "$OUT"
for b in 1 2 3 4 5 6 7 8 10 11 12 13 14 15 17; do
  if [ "$b" = "12" ]; then tests="5 6 7 8"; else tests="1 2 3 4"; fi
  for t in $tests; do
    for s in listening reading; do
      PDF=$R/official-keys/book_$b/test_${t}_${s}.json
      if [ "$s" = "listening" ]; then
        ANS=$R/scratch/s18/answers/book_$b/test_${t}_${s}_shared.json
      else
        ANS=$R/scratch/s18/answers/book_$b/test_${t}_${s}_academic.json
      fi
      OUTF=$OUT/book${b}-test${t}-${s}.json
      if [ ! -f "$PDF" ]; then echo "book$b t$t $s: NO-PDF skip"; continue; fi
      if [ ! -f "$ANS" ]; then echo "book$b t$t $s: NO-ANS skip"; continue; fi
      N=$(PYTHONIOENCODING=utf-8 $PY -c "
import json
nums=set()
for f in [r'$PDF', r'$ANS']:
    d=json.load(open(f,encoding='utf-8'))
    for e in d.get('entries',[]):
        n=e.get('number')
        if isinstance(n,int): nums.add(n)
print(max(nums) if nums else 0)
")
      if [ -z "$N" ] || [ "$N" -le 0 ] 2>/dev/null; then echo "book$b t$t $s: N=0 skip"; continue; fi
      node ielts-api/tools/compare-official.mjs --identity book=$b,test=$t,skill=$s \
        --pdf "$PDF" --answers "$ANS" --expected 1-$N \
        --pdf-file tmp_audit_ielts/downloads/book_$b.pdf \
        --out "$OUTF" > "$OUT/book${b}-test${t}-${s}.log" 2>&1
      EC=$?
      if [ -f "$OUTF" ]; then
        S=$(PYTHONIOENCODING=utf-8 $PY -c "
import json
d=json.load(open(r'$OUTF',encoding='utf-8'))
s=d.get('summary',{})
print('match=%s conflict=%s pdf_only=%s answer_only=%s missing=%s unverified=%s' % (s.get('match'),s.get('conflict'),s.get('pdf_only'),s.get('answer_only'),s.get('missing'),s.get('unverified')))
")
        echo "book$b t$t $s N=$N EXIT=$EC $S"
      else
        echo "book$b t$t $s N=$N EXIT=$EC NO-OUTPUT (see log)"
      fi
    done
  done
done
echo COMPARE-ALL-DONE
