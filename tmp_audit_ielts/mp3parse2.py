# -*- coding: utf-8 -*-
# 独立审查 v2：MP3 帧解析，支持 MPEG1 / MPEG2 / MPEG2.5 Layer III
import sys, json

# MPEG1 Layer III 码率表
BR1 = [0,32,40,48,56,64,80,96,112,128,160,192,224,256,320]
# MPEG2/2.5 Layer III 码率表
BR2 = [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160]
SR1 = [44100,48000,32000]
SR2 = [22050,24000,16000]
SR25 = [11025,12000,8000]

def parse_mp3(path):
    data = open(path,"rb").read()
    size = len(data)
    has_id3 = data[:3]==b"ID3"
    id3_ver = data[3] if has_id3 else None
    off = 0
    if has_id3:
        sz = (data[6]<<21)|(data[7]<<14)|(data[8]<<7)|data[9]
        off = 10+sz
    i = off; frames=0; dur=0.0; brs={}; srs={}; bad=0; first_hdr=None
    while i < len(data)-4:
        if data[i]==0xFF and (data[i+1]&0xE0)==0xE0:
            h=data[i:i+4]
            ver=(h[1]>>3)&3   # 3=MPEG1, 2=MPEG2, 0=MPEG2.5
            layer=(h[1]>>1)&3 # 1=Layer III
            bri=(h[2]>>4)&0xF; sri=(h[2]>>2)&3; pad=(h[2]>>1)&1
            if ver in (0,2,3) and layer==1 and 0<bri<15 and sri!=3:
                if ver==3:
                    br=BR1[bri]*1000; sr=SR1[sri]; spf=1152; coef=144
                else:
                    br=BR2[bri]*1000
                    sr=(SR2 if ver==2 else SR25)[sri]
                    spf=576; coef=72
                flen=coef*br//sr+pad
                if first_hdr is None: first_hdr={"ver":{3:"MPEG1",2:"MPEG2",0:"MPEG2.5"}[ver],"sr":sr,"br":br}
                frames+=1; dur+=spf/sr; brs[br]=brs.get(br,0)+1; srs[sr]=srs.get(sr,0)+1
                i+=flen; continue
        i+=1; bad+=1
    return {"file":path.split("/")[-1],"bytes":size,"id3":has_id3,"id3_version":id3_ver,
            "first_hdr":first_hdr,
            "frames":frames,"duration_s":round(dur,2),"duration_hms":f"{int(dur//60)}m{int(dur%60)}s",
            "avg_bitrate_kbps":round(size*8/dur/1000,1) if dur else None,
            "dominant_bitrate_kbps":max(brs,key=brs.get)//1000 if brs else None,
            "dominant_srate":max(srs,key=srs.get) if srs else None,
            "bitrate_hist":{k//1000:v for k,v in sorted(brs.items())},
            "bad_bytes":bad}

for p in sys.argv[1:]:
    print(json.dumps(parse_mp3(p), ensure_ascii=False))
