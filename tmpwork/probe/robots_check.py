import httpx
UA = "ExamDataBot/0.1 (+https://example.invalid/examdata; contact=ops@example.invalid)"
for host, paths in [
    ("https://cie.fraft.cn", ["/obj/Common/Subject/combo", "/obj/Common/Fetch/renum", "/obj/Common/Fetch/redir/9709_m26_qp_12.pdf"]),
    ("https://qualifications.pearson.com", [
        "/services/pearson/algolia/GET.servlet?fq=x&hitsPerPage=1",
        "/content/dam/pdf/International-Advanced-Level/Economics/2018/Exam-materials/wec11-01-que-20240510.pdf",
        "/content/dam/secure/silver/all-uk-and-international/a-level/economics-b/2015/exam-materials/w75094a.pdf",
    ]),
]:
    print("="*70)
    print(host)
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": UA}) as c:
            r = c.get(host + "/robots.txt")
        print("robots status", r.status_code, "len", len(r.text))
        print(r.text[:1200] if r.status_code == 200 else "(no robots)")
        import urllib.robotparser
        rp = urllib.robotparser.RobotFileParser()
        rp.parse((r.text if r.status_code==200 else "").splitlines())
        for p in paths:
            print(f"   can_fetch({p[:70]}) = {rp.can_fetch(UA, host + p)}")
    except Exception as e:
        print("ERR", type(e).__name__, e)
