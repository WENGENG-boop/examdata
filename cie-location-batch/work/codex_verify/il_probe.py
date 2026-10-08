import subprocess, sys
out = sys.argv[1]
r = subprocess.run([r'C:\Windows\System32\whoami.exe', '/groups'],
                   capture_output=True)
txt = r.stdout.decode('gbk', 'replace')
lines = [l.strip() for l in txt.splitlines() if 'S-1-16' in l]
open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print('probe wrote', out, '->', lines[:1])
