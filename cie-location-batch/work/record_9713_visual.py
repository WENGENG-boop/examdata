"""Record the completed Codex image review, never an OCR-generated approval.

All 38 named crops were displayed and inspected before this record was written.
No import, upstream request, cleanup, or service replacement is performed here.
"""
import json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import batchlib as B
import validate_index as V
import cleanup_paper as C
key='9713/2017/Nov/11'
root=Path(__file__).resolve().parents[1]
path=root/'indexes/9713/2017-Nov-11/cie-index.json'
tmp=root/'tmp/9713/2017-Nov-11'
observations=[
'Scenario1含WIMBA造车、paint、机器人与17°C PLC/PID全文，末句完整。',
'Q1十行选项和[4]完整，无Q2；Vacuum cups、Spanners按QP原文。',
'MS1四个勾选为camera、gripper、screwdriver、vacuum；4分与全部十行完整；第七行Sanders与QP不同属原件差异。',
'Q2十行PLC/PID选项与[4]完整，无Q1或页脚。',
'MS2四勾选为analogue/digital、rarely user input、constant preset、difference calculation；4分完整；首行An algorithm与QP措辞不同保留原件。',
'Q3三个控制类别及三个[2]均完整，无下一Scenario。',
'MS3批量paint、连续17°C、离散组装/喷漆及各1+1评分完整。',
'Scenario2含Louisa课程、email/phone、flyers/slides、网站与失业四段全文。',
'Q4表格A–G、1–13行完整，课程代码A/B/C、250/325/225及六次培训数据完整。',
'Q4(a) D8 VLOOKUP题干及[5]完整，不含(b)。',
'Q4(b)三个理由题干、三个答题位置及[3]完整。',
'MS4(a) =B8*VLOOKUP(C8,$E$3:$G$5,3,FALSE)及五条1分分配完整。',
'MS4(b)时间、错误、验证、储存四个候选理由及3分完整。',
'Q5(a)建立电话会议题干和[4]完整。',
'Q5(b)email对比phone会议利弊题干和[8]完整，续页归属5(b)。',
'MS5(a)预约、两个PIN、通知、拨号与参与步骤及4分完整。',
'MS5(b)全部利弊、结论1分及至少两个优势两个劣势的满分要求完整，8分。',
'Q6(a)三类广告及判断GoodCars类型理由、[3]完整。',
'Q6(b)比较flyers与slide show及[4]完整。',
'MS6(a)Product advertising、specific product、individual cars及3分完整。',
'MS6(b)多媒体、效果、商城/丢弃、定向和本地范围及comparison AND contrast要求完整。',
'Q7(a)买车网站功能题干和[6]完整，不含(b)。',
'Q7(b)避免失业的两种working patterns题干和[2]完整。',
'MS7(a)域名、支付、车辆描述、账户、联系、订单、搜索、导航、wishlist、推荐、定制全部候选点及6分完整。',
'MS7(b)part-time与job sharing各1分，共2分完整。',
'Q8顾客网上买车利弊题干和[8]完整。',
'MS8安全、送货、标准、残疾、试驾等劣势与便利、价格、出行、选择等优势，结论和至少2+2要求完整。',
'Scenario3 SG电话购物、月末付款、transaction/master/stock三文件及Ho改系统全文完整。',
'Q9(a)交易金额之外两项数据及[2]完整。',
'Q9(b)daily master update处理题干和[6]完整。',
'MS9(a)Customer id、Stock id各1分，2分完整。',
'MS9(b)排序、读取、比较、不匹配、匹配后更新、写新文件及循环终止等全部评分点完整，6分。',
'Q10(a)合并relation database及操作描述题干和[5]完整。',
'Q10(b)关系库优于两个flat files题干和[4]完整。',
'MS10(a)三表、关系图、customer/stock keys、1-to-many关系与链接、5分完整。',
'MS10(b)重复、储存、安全、扩展、修改、跨表报表、完整性及4分完整。',
'Q11 Systems与Program各三个项目，技术文档题干与[6]完整。',
'MS11 Systems与Program两段全部评分候选、三项各组选取及6分完整。']
manifest=B.read_json(root/'work/9713-visual-crop-manifest.json',[])
validation=V.validate(path,qp=tmp/'9713_w17_qp_11.pdf',ms=tmp/'9713_w17_ms_11.pdf')
assert not validation['errors'],validation
stamp=B.now_iso()
for row in manifest:
    num=int(row['crop'].split('-')[2])
    B.append_jsonl(B.VERIFICATION,{'key':key,**{k:v for k,v in row.items() if k!='crop'},
      'method':'local_image_visual','checked_at':stamp,'issues':[],
      'image':str(tmp/'crops'/row['crop']), 'image_sha256':B.sha256_file(tmp/'crops'/row['crop']),
      'index_sha256':B.sha256_file(path),
      'checks':{'content_complete':True,'boundary_checked':True,'role_matches':True,
                'observed':observations[num-1]}})
problems,stats=C.verification_state(key,[q['question'] for q in B.read_json(path,{})['questions']])
report={'key':key,'at':stamp,'validation':validation,'visual_problems':problems,'visual_stats':stats,
 'unique_crops_inspected':38,'regions_reviewed':len(manifest),'full_pages_inspected':{'qp':16,'ms':7},
 'service_conflict_retained':True,'originals_retained':True,'reviewed':False,
 'scope':'完整本地目视完成；不同服务旧稿未覆盖，尚未完成导入与同内容回读。'}
B.atomic_write_json(root/'work/9713-visual-review-result.json',report)
B.append_jsonl(B.ERRORS,{'kind':'local_visual_repair','key':key,**report})
papers=B.read_json(B.PAPERS,{})
papers[key]['local_visual_verified']=not problems
papers[key]['local_visual_verified_at']=stamp
papers[key]['local_visual_report']='work/9713-visual-review-result.json'
papers[key]['question_count']=23
B.atomic_write_json(B.PAPERS,papers)
print(json.dumps(report,ensure_ascii=False))
