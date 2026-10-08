"""只读诊断：读取 PID 22612 进程环境块中的指定变量（从 PEB 读取）。

只输出白名单变量（TMP/TEMP/TMPDIR/EXAMDATA_* 等），不打印整个环境，避免泄露秘密。
"""
import ctypes

class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Reserved1", ctypes.c_void_p),
        ("PebBaseAddress", ctypes.c_void_p),
        ("Reserved2", ctypes.c_void_p * 2),
        ("UniqueProcessId", ctypes.c_void_p),
        ("Reserved3", ctypes.c_void_p),
    ]

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PID = 22612

WANTED = {
    "tmp", "temp", "tmpdir", "sqlite_tmpdir",
    "examdata_database_url", "examdata_data_dir", "examdata_max_retries",
    "pwd", "userprofile", "home", "windir", "systemroot", "comspec",
}

h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, PID)
if not h:
    raise SystemExit(f"OpenProcess failed: {ctypes.get_last_error()}")

pbi = PROCESS_BASIC_INFORMATION()
status = ntdll.NtQueryInformationProcess(h, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None)
if status != 0:
    raise SystemExit(f"NtQueryInformationProcess status={status:#x}")

peb = pbi.PebBaseAddress
params_ptr = ctypes.c_void_p()
k32.ReadProcessMemory(h, ctypes.c_void_p(peb + 0x20), ctypes.byref(params_ptr), ctypes.sizeof(params_ptr), None)
params = params_ptr.value

env_ptr = ctypes.c_void_p()
ok = k32.ReadProcessMemory(h, ctypes.c_void_p(params + 0x80), ctypes.byref(env_ptr), ctypes.sizeof(env_ptr), None)
if not ok:
    raise SystemExit(f"ReadProcessMemory(Environment) failed: {ctypes.get_last_error()}")

# 分块读取环境块（UTF-16LE，双空结尾）
CHUNK = 0x10000
chunks = []
addr = env_ptr.value
while True:
    buf = ctypes.create_string_buffer(CHUNK)
    nread = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, CHUNK, ctypes.byref(nread))
    if not ok or nread.value == 0:
        break
    data = buf.raw[: nread.value]
    chunks.append(data)
    if b"\x00\x00\x00\x00" in data:
        break
    addr += nread.value

raw = b"".join(chunks)
text = raw.decode("utf-16-le", errors="replace")
entries = text.split("\x00")
print(f"env block entries: {len(entries)}")
for e in entries:
    if "=" not in e:
        continue
    name = e.split("=", 1)[0].strip()
    if name.lower() in WANTED:
        print(f"  {name}={e.split('=', 1)[1]}")
