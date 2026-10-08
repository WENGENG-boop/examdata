"""Offline reconstruction from all 16 QP / 7 MS rendered pages actually inspected.

Pixel boundaries refer to the 796 x 1030 full-page renders. This script writes
local JSON and crops only; it neither logs visual approval nor mutates service.
"""
import json, sys
from pathlib import Path
import fitz
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import batchlib as B

root = Path(__file__).resolve().parents[1]
target = root / 'indexes/9713/2017-Nov-11/cie-index.json'
tmp = root / 'tmp/9713/2017-Nov-11'
old = json.loads(target.read_text(encoding='utf-8'))
backup = root / 'work/9713-before-visual-repair.json'
if not backup.exists():
    B.atomic_write_json(backup, old)
docs = {role: fitz.open(tmp / f'9713_w17_{role}_11.pdf') for role in ('qp', 'ms')}

def region(role, page, top, bottom):
    p = docs[role][page-1]
    return {'page': page, 'bbox': [round(v, 3) for v in
            (90*p.rect.width/796, top*p.rect.height/1030,
             705*p.rect.width/796, bottom*p.rect.height/1030)]}

scenarios = {
1: 'WIMBA manufactures cars. It makes its own paint in a separate department so that the cars can be painted before they come off the production line. Robot arms are used to carry out many of the manufacturing processes. In order that they perform at maximum efficiency, the temperature must not rise above or fall below 17°C. A Programmable Logic Controller (PLC) using a Proportional Integral Derivative (PID) algorithm keeps the temperature at 17°C.',
2: 'Louisa is the chief car salesperson with GoodCars Sales in Christchurch. Part of her job is to go on training courses which usually take place in Wellington, some distance away. This involves her being out of the salesroom quite often. She keeps a spreadsheet of training courses she attends and the cost of each session. While she is out of the salesroom, Louisa uses email to remain in contact with her sales people. Paul, Louisa’s deputy, has suggested that Louisa could set up a phone conference to stay in touch with her colleagues instead. Most of GoodCars’ customers live locally. The company is in competition with a number of other local car sales companies. At the moment it advertises its cars using locally distributed flyers. It is considering using slide show presentations situated in a local shopping mall. The directors of GoodCars are considering having a website which customers could use to buy cars, which may cause some sales people to be made unemployed.',
3: 'Shanghai Garments (SG) operates a phone shopping system whereby customers phone in orders and have the garments delivered to their homes. Each customer has an account and pays at the end of the month what they owe on their account. During the course of a normal day, a transaction file (order file) is created which has the garments ordered and some details of the customer as well as the amount of the transaction. This file contains the absolute minimum of information. There is a master file which contains all the customer details including how much money they owe. The master file (customer file) is updated at the end of each day. There is a separate file which contains the details of each garment in stock. SG have decided that they want to update the current system of record keeping. They have employed Ho, a systems analyst, to organise the creation of this new system.'}
ctx = {1:(2,75,310), 2:(5,75,410), 3:(12,75,400)}
table = 'Spreadsheet: E2 Course Code; F2 Course title; G2 Course cost per day. E3 A, F3 Automotive Studies, G3 $250; E4 B, F4 Customer Care, G4 $325; E5 C, F5 Financial Competence, G5 $225. A7 Date of course; B7 Duration (days); C7 Course Code; D7 Cost. Rows 8–13: 12-01-17,2,B,$650; 25-01-17,1,C,$225; 08-02-17,3,A,$750; 15-03-17,2,C,$450; 18-04-17,3,B,$975; 28-04-17,2,A,$500.'
texts = {
'1': 'Tick the four most accurate statements about the use of end effectors when attached to robot arms.\nCameras are used to inspect/check work.\nSanders are used to produce a shiny finish.\nGrippers are used to pick up parts.\nRiveters are used to place and tighten nuts.\nScrewdrivers are used to place/screw in and tighten screws.\nPolishers are used to prepare the car body for painting.\nSpanners are used to paint the car body.\nVacuum cups are used to pick up parts.\nSprayers are used to weld parts of the car body together.\nAll end effectors have to be changed by a human.',
'2': 'Tick the four most accurate statements about the use of PLCs and PIDs.\nA PID algorithm is a type of computer/microprocessor used for a single purpose.\nA PLC has analogue and digital inputs.\nA PLC is not used in processes which are continuous.\nThere is rarely any input to a PLC from the user once it has been programmed.\nThe PLC causes the PID algorithm to make proportional changes to the temperature.\nA PLC is used in this process as the pre-set value is constant.\nA PLC is a type of computer used for many different purposes.\nThe PID algorithm calculates the difference between the input value and the pre-set value.\nThe PID algorithm causes the PLC to switch the heating element on for long periods of time.\nThe PLC does not make use of any sensors.',
'3': 'Using examples from the scenario, describe what is meant by: batch process control [2]; continuous process control [2]; discrete process control [2].',
'4(a)': 'Write down the formula which should go in cell D8 which involves the use of the VLOOKUP function.',
'4(b)': 'Give three reasons why Louisa only wants to type in the course code in column C rather than the full title.',
'5(a)': 'Describe how Louisa would set up a phone conference.',
'5(b)': 'Discuss the advantages and disadvantages to sales people of using email compared to a phone conference.',
'6(a)': 'There are three types of advertising: Service, Product and Business. Identify and describe the type that GoodCars use, explaining why.',
'6(b)': 'Compare and contrast the use of flyers with the use of a slide show.',
'7(a)': 'Apart from having a good visual appearance, describe the features of a website designed specifically for buying cars online.',
'7(b)': 'To prevent unemployment of sales people, describe the two working patterns they will need to adopt.',
'8': 'Discuss the advantages and disadvantages to customers of buying cars online.',
'9(a)': 'Apart from the value of the transaction, identify two items which would be in the transaction file.',
'9(b)': 'Describe the computer processing involved in the daily updating of the master file.',
'10(a)': 'Ho has decided that the existing files should be combined into a relational database system. Describe how he would do this.',
'10(b)': 'Explain why a relational database would be better than two separate flat files.',
'11': 'When Ho has implemented the new system he will provide technical documentation. For each of the following types of technical documentation, describe three items which would be present in each. Systems: 1, 2, 3. Program: 1, 2, 3.'}
# Exact visible row boundaries, with a few pixels of whitespace. No footer or
# neighbouring answer included; table headings are contextual, not answer rows.
spec = {
'1':(4,[(3,75,435)],[(2,75,478)]),
'2':(4,[(3,460,835)],[(2,495,915)]),
'3':(6,[(4,75,672)],[(3,75,582)]),
'4(a)':(5,[(6,75,398),(6,411,510)],[(3,630,754)]),
'4(b)':(3,[(6,75,398),(6,525,845)],[(3,754,863)]),
'5(a)':(4,[(7,75,430)],[(4,106,291)]),
'5(b)':(8,[(8,75,752)],[(4,291,632)]),
'6(a)':(3,[(9,75,352)],[(4,680,744)]),
'6(b)':(4,[(9,356,740)],[(5,75,292)]),
'7(a)':(6,[(10,75,503)],[(5,341,619)]),
'7(b)':(2,[(10,510,740)],[(5,619,681)]),
'8':(8,[(11,75,752)],[(6,75,587)]),
'9(a)':(2,[(13,75,173)],[(6,636,696)]),
'9(b)':(6,[(13,187,683)],[(6,696,913)]),
'10(a)':(5,[(14,75,508)],[(7,75,322)]),
'10(b)':(4,[(14,520,827)],[(7,322,477)]),
'11':(6,[(15,75,776)],[(7,495,915)])}
rows = {}
for qid,(marks,qps,mss) in spec.items():
    number=int(qid.split('(')[0]); sc=1 if number<=3 else 2 if number<=8 else 3
    text=scenarios[sc]+'\n\n'+(table+'\n\n' if number==4 else '')+texts[qid]
    rows[qid]={'question':qid,'parent':qid.split('(')[0] if '(' in qid else None,
      'text':text,'marks':marks,'qp':[region('qp',*ctx[sc])]+[region('qp',*r) for r in qps],
      'ms':[region('ms',*r) for r in mss], 'uncertain':False,
      'notes':'按原件逐页目视转录；QP包含对应共享Scenario。MS原文以裁图为准。'+
      (' 第3题分值为三个明示[2]相加，不虚构子题编号。' if qid=='3' else '')+
      (' MS题1第七选项与QP措辞不同（Sanders/Spanners），保留原件。' if qid=='1' else '')}
for number in (4,5,6,7,9,10):
    a,b=rows[f'{number}(a)'],rows[f'{number}(b)']
    def unique(items):
        return list({json.dumps(r,sort_keys=True):r for r in items}.values())
    rows[str(number)]={'question':str(number),'parent':None,
      'text':a['text']+'\n\n(b) '+texts[f'{number}(b)'],
      'marks':a['marks']+b['marks'], 'qp':unique(a['qp']+b['qp']),
      'ms':unique(a['ms']+b['ms']), 'uncertain':False,
      'notes':'共享Scenario与全部子题区域的并集；父题分值为原页明示子题分值之和。'}
order=[q['question'] for q in old['questions']]
old['questions']=[rows[qid] for qid in order]
B.atomic_write_json(target,old)
cropdir=tmp/'crops'; cropdir.mkdir(exist_ok=True)
manifest=[]; unique={}
for q in old['questions']:
    for role in ('qp','ms'):
        for r in q[role]:
            key=(role,r['page'],tuple(r['bbox']))
            if key not in unique:
                name=f'visual-repair-{len(unique)+1:02d}-{role}-p{r["page"]}.png'
                docs[role][r['page']-1].get_pixmap(matrix=fitz.Matrix(1.3,1.3),clip=fitz.Rect(r['bbox'])).save(cropdir/name)
                unique[key]=name
            manifest.append({'question':q['question'],'role':role,**r,'crop':unique[key]})
B.atomic_write_json(root/'work/9713-visual-crop-manifest.json',manifest)
print(json.dumps({'questions':len(rows),'regions':len(manifest),'unique_crops':len(unique),'top_marks':sum(q['marks'] for q in rows.values() if q['parent'] is None)}))
