# G14c: sha256 verification of all G14b artifacts + associated inputs (2026-10-05)
import glob
import hashlib
import os


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


R = r"C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair"
S = R + "/scratch/s18"
A = r"C:/Users/weo/Desktop/api"

g14b = {
    "g14b-book11-crop-recheck.py": "195f5fb17274702ab6567184348f17e1502df4ac7fa82bbbf3ad02430dbc9452",
    "g14b-book11-keys-p123-124.json": "863e70755684d5634af36f3afdb0814d35ca5dd7b05922759edfca2da64e191b",
    "g14b-book11-p124-crops.json": "4cd934c160094614fa5ed2b2d6b930f1f0014eadb7df5aaefcf0a5d4aa92559d",
    "g14b-book11-p84-88-text.txt": "d8716b7f6c568c10fdb67b31a8f56fc2958d4681be70ec59541596c3c7a2cf81",
    "g14b-dump-and-search.py": "9f7422543303454d4e5dc3f1437ef6210bf6be9a47760d6c05c7449e8288ca5d",
    "g14b-dump-pte-meta.py": "c8a5912f3becd70406734c634ca5ceeb15f5112b0243721f2beabffe1e6aa7f6",
    "g14b-feature-hits-all-sources.txt": "d0bc399334c38dc7540ea0b49bb1d432648b0c40f2bd72a6ea6cc464816d31e4",
    "g14b-hash-match.py": "61d3d58a756bdb75bfebe874eb262547de68860bacfd2efeeb554cc2ada09204",
    "g14b-hash-match.txt": "6179adb2635cb0c5d0c54ad91e1a62c4d9bdce194eb6f2a19438cab5bec74de2",
    "g14b-identify-pdfs.py": "36c73d2f2fd3d92a64e2a65888eaf9362f323ca73fc27b3bb273ef68f7f77b66",
    "g14b-index-feature-check.py": "e6263ee32884390c5d4afd5b2eb75ec58d3b5518794da8c5430f74d3c07a94b7",
    "g14b-inspect-hits.py": "7bd02efc06366911f9f352ed298e936629f1649f5dd21cd12f7c4807ab9820c8",
    "g14b-layout-map.py": "6ed1d4e23ed139e3f77891d81c5e50d1e514208803758b177772d78d6ed71817",
    "g14b-layout-map.txt": "de840e0c9e94c3de9ee418705b2a90eee5388bb86be40efcf5c7f34a42accef7",
    "g14b-ocr-batch.py": "37d822bbdbca28ee70c7dfacadfe13cc598b27d7498ffb68120bd73149996f35",
    "g14b-ocr-sweep-book20.py": "7bb2df2a54ca2840376dca02b756aac9a70d9cc033a1c1709990294f80ab47ed",
    "g14b-ocr-sweep.py": "e353a160ec385e57c5889d72efd858cc5fdaf6a92d210586a58d789dc1b1148f",
    "g14b-ocr20-crops-recheck.txt": "5312de7ef925ae9975e14d10fd4d9300f1ea5501e3cad2be470c79ffd42f177d",
    "g14b-ocr20-dump.txt": "6cace9e80f5cce35880a8e77fffe67ba44d8c68403b0c92625219bd2f6cd9722",
    "g14b-ocr20-test1-p234.json": "e63845a5c63de170e3f5ed29a00e54ffe439b5c9634e07e1987cd29f0128ef84",
    "g14b-ocr20-test2-p34.json": "f765e5205ec975dee6d41755cf3b78085b6996c949e9c7e6b378c50112e806a1",
    "g14b-ocr20-test3-p34.json": "ed8a0b8b87e9357e41abdc7b566898d5b4cb700988bd019e6d72c184e0f918da",
    "g14b-ocr20-test4-p34.json": "30f9b10d915078096c611095e664dce9944d510c46054205bfb72567bbf4630e",
    "g14b-pdf-identify.txt": "4be59d72268b91d311a0963462d9b46b41d314ffacaced44462be1bdaf241a38",
    "g14b-pte-meta.tsv": "2893a17c00ee6beda5e67fb99970ca51c421c938641f17f6f5a2d6893359260b",
    "g14b-pte-sources.txt": "2b6cf02deaa321e6ccffe462fad83a2e0b5ff20f3b3c22bed858a4bdeb87a932",
    "g14b-recheck-ocr20-crops.py": "6ca4dba1651e2d952a44dd70a17e2f0777b241fdc68c972560a2347e96160be0",
    "g14b-scan-book16.json": "cfbf89504f9b7e92d91e3a875f936c06a21d70e626d269f336b72e9fc20aeead",
    "g14b-scan-book18.json": "6e0c06e761224d81651e00af43169fc1c4a91bd5f94aabb55b9b4250443db75c",
    "g14b-scan-book19.json": "ed056a7345c4b6be3e1e8f0b8cacd84975ce37215dd41693a367b2e46881ccec",
    "g14b-scan-book20-test1.json": "c858ca9ddcbc1e24941961ac40a70eb904caf2120409a9b5d988962184e20900",
    "g14b-scan-book20-test2.json": "a3f6859018c36b207bab3075127ca393d162789dd8e05967c36ca569372c8260",
    "g14b-scan-book20-test3.json": "0d7a86404c9868860fbbd607183b2f5a402d295be15d97faa1703ec933943189",
    "g14b-scan-book20-test4.json": "a1f29377ef61696dc3e3134fd4969ad7134b2dba9d1041d467f80fb6a195c06b",
    "g14b-scan-book9.json": "da8bc734ec5df8af6f97d1c90f655f2cdbaf1fcadd05e0067e013f9c0cd71152",
    "g14b-search-sweep-results.txt": "95eb011e1c2db9e736e3b9ecb5b900c964649dd24cb4ead08146e4ef3c7e425f",
    "g14b-search-sweep.py": "723fdfea7da66f9fb9ce5638cb4f9d02fba7e5efa47f2ce2d6508cecb9aba0ab",
    "g14b-textlayer-hits.json": "ce80ec99a7af68700a3473e2bc24a8830d48070375d5bedd9f8866b5dba4d902",
    "g14b-textlayer-scan.py": "e5beb0a249eb728c7a1ecbbf5cbccc4f091e84628148851288acb442fd4d1385",
    "g14b-toc-book16.json": "a8668b480813262fd70175a36c4056e7e0da5db914ef8811783d09a8fc9e3cbb",
    "g14b-toc-book18.json": "51cf0427910107199e15b9340c0a4d4936c3b2bb8aca78791d21fe3c734dd970",
    "g14b-toc-book19.json": "500bfd9fcee0431dcc943252b715d354ed27a8c57f1135f5d84e0e63b8f0cd04",
    "g14b-toc-book9.json": "4df950b18bbdfcea04465e3a6f83146a12285295f929a87be04134656cc8c92e",
    "g14b2-book11-textlayer-p121-124.txt": "a203f93d24f973aee90bc81244a94c3f05c04391b39e4f41a71f395d4e3746bf",
    "g14b2-textlayer-p121-124.py": "59dc4aa725b6efedc0a207e68e056bfa4d8cc3474e2a00395b79a94990c6ed9a",
}

assoc = [
    (A + "/tmp_audit_ielts/downloads/book_11.pdf",
     "c9672f9f8dc9fbd4ca7f965a50a3a599bf86a144efbe5e777010b5958baaf9db"),
    (A + "/tmp_audit_ielts/completeness_20261003/pte-11-4-listening.json",
     "793e5d42040c9494a52b6372bd77f6db9b075d00b2267c08e51968e7d7634634"),
    (A + "/tmp_audit_ielts/completeness_20261003/pte-11-1-reading.json",
     "cbc738eaa6f525cae36b5003d338f05ae7629ce2c98305567982a7538ba643af"),
    (A + "/tmp_audit_ielts/completeness_20261003/pte-1-4-reading.json", None),
    (A + "/tmp_audit_ielts/completeness_20261003/raw-172.txt", None),
    (A + "/tmp_audit_ielts/completeness_20261003/raw-13.txt", None),
    (A + "/ielts-data/raw/practicepteonline/66356be4b242646e81f6ddb96584a70a995617fc8f6eaf603ca1a198e817f8df.body",
     "66356be4b242646e81f6ddb96584a70a995617fc8f6eaf603ca1a198e817f8df"),
    (A + "/ielts-data/raw/practicepteonline/940cf483089a7527a239f9cfb3749a85af2229ff279d74b82c622c0629775980.body",
     "940cf483089a7527a239f9cfb3749a85af2229ff279d74b82c622c0629775980"),
    (R + "/official-keys/book_11/test_4_reading.json",
     "d57e978cb2871da22c205d8ba63f2cdfe38ce1e9040420d3f91f8b45ecd81c60"),
    (R + "/scratch/s18/answers/book_11/test_1_reading_academic.json",
     "642d4c17d86a6b38b37d9bd424467197496d1cf1d433d1aad9961423915d4f4f"),
    (R + "/evidence/S18-book11-remap.md",
     "1e58248cd19b986175a3c9f00268aa969b5486cc4b138efb9771629cedd9e6aa"),
]

ok = bad = 0
files = sorted(os.path.basename(p) for p in glob.glob(S + "/g14b*"))
extra = sorted(set(files) - set(g14b))
missing = sorted(set(g14b) - set(files))
print("g14b files on disk:", len(files), "| expected:", len(g14b))
if extra:
    print("EXTRA:", extra)
    bad += len(extra)
if missing:
    print("MISSING:", missing)
    bad += len(missing)

for name in sorted(g14b):
    p = os.path.join(S, name)
    if not os.path.exists(p):
        continue
    got = sha(p)
    if got == g14b[name]:
        ok += 1
    else:
        bad += 1
        print("DIFF", name, got)

print("g14b verified", ok, "ok /", bad, "bad")

for p, exp in assoc:
    rel = os.path.relpath(p, A).replace("\\", "/")
    if not os.path.exists(p):
        print("ASSOC-MISSING", rel)
        bad += 1
        continue
    got = sha(p)
    if exp is None:
        print("ASSOC-COMPUTED", rel, got)
    elif got == exp:
        print("ASSOC-OK", rel)
    else:
        print("ASSOC-DIFF", rel, got, "!=", exp)
        bad += 1

print("DONE bad =", bad)
