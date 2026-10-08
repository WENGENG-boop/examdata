# -*- coding: utf-8 -*-
# 独立审查：MP3 帧解析（MPEG1 Layer III）
import sys, json

BITRATES = [0,32,40,48,56,64,80,96,112,128,160,192,224,256,320]
SRATES = [44100,48000,32000]

def parse_mp3(path):
    data = open(path,"rb").read()
    size = len(data)
    has_id3 = data[:3]==b"ID3"
    id3_ver = data[3] if has_id3 else None
    off = 0
    if has_id3:
        sz = (data[6]<<21)|(data[7]<<14)|(data[8]<<7)|data[9]
        off = 10+sz
    i = off; frames=0; dur=0.0; brs={}; bad=0
    while i < len(data)-4:
        if data[i]==0xFF and (data[i+1]&0xE0)==0xE0:
            h=data[i:i+4]
            ver=(h[1]>>3)&3; layer=(h[1]>>1)&3; bri=(h[2]>>4)&0xF; sri=(h[2]>>2)&3; pad=(h[2]>>1)&1
            if ver==3 and layer==1 and 0<bri<15 and sri!=3:
                br=BITRATES[bri]*1000; sr=SRATES[sri]
                flen=144*br//sr+pad
                frames+=1; dur+=1152/sr; brs[br]=brs.get(br,0)+1
                i+=flen; continue
        i+=1; bad+=1
    return {"file":path.split("/")[-1],"bytes":size,"id3":has_id3,"id3_version":id3_ver,
            "frames":frames,"duration_s":round(dur,2),"duration_hms":f"{int(dur//60)}m{int(dur%60)}s",
            "avg_bitrate_kbps":round(size*8/dur/1000,1) if dur else None,
            "dominant_bitrate_kbps":max(brs,key=brs.get)//1000 if brs else None,
            "bitrate_hist":{k//1000:v for k,v in sorted(brs.items())}}

for p in sys.argv[1:]:
    print(json.dumps(parse_mp3(p), ensure_ascii=False))
