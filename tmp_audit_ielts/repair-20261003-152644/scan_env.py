import ctypes, sys
PID = int(sys.argv[1])
class PBI(ctypes.Structure):
    _fields_ = [("R1", ctypes.c_void_p), ("Peb", ctypes.c_void_p), ("R2", ctypes.c_void_p * 2), ("Pid", ctypes.c_void_p), ("R3", ctypes.c_void_p)]
k32 = ctypes.WinDLL("kernel32", use_last_error=True); ntdll = ctypes.WinDLL("ntdll")
h = k32.OpenProcess(0x0400 | 0x0010, False, PID)
if not h:
    print(f"PID {PID}: OpenProcess failed"); sys.exit(0)
pbi = PBI(); ntdll.NtQueryInformationProcess(h, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None)
pp = ctypes.c_void_p(); k32.ReadProcessMemory(h, ctypes.c_void_p(pbi.Peb + 0x20), ctypes.byref(pp), ctypes.sizeof(pp), None)
ep = ctypes.c_void_p(); k32.ReadProcessMemory(h, ctypes.c_void_p(pp.value + 0x80), ctypes.byref(ep), ctypes.sizeof(ep), None)
chunks, addr = [], ep.value
while True:
    buf = ctypes.create_string_buffer(0x10000); nr = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, 0x10000, ctypes.byref(nr))
    if not ok or nr.value == 0: break
    d = buf.raw[:nr.value]; chunks.append(d)
    if b"\x00\x00\x00\x00" in d: break
    addr += nr.value
text = b"".join(chunks).decode("utf-16-le", errors="replace")
hits = [e for e in text.split("\x00") if "=" in e and "EXAMDATA" in e.upper()]
print(f"PID {PID}: {len(hits)} EXAMDATA vars")
for e in hits: print("   ", repr(e))
