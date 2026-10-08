import ctypes, sys
PID = int(sys.argv[1])
class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [("Reserved1", ctypes.c_void_p), ("PebBaseAddress", ctypes.c_void_p),
                ("Reserved2", ctypes.c_void_p * 2), ("UniqueProcessId", ctypes.c_void_p),
                ("Reserved3", ctypes.c_void_p)]
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")
h = k32.OpenProcess(0x0400 | 0x0010, False, PID)
if not h: raise SystemExit(f"OpenProcess failed {ctypes.get_last_error()}")
pbi = PROCESS_BASIC_INFORMATION()
st = ntdll.NtQueryInformationProcess(h, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None)
if st != 0: raise SystemExit(f"NtQuery status={st:#x}")
peb = pbi.PebBaseAddress
params_ptr = ctypes.c_void_p()
k32.ReadProcessMemory(h, ctypes.c_void_p(peb + 0x20), ctypes.byref(params_ptr), ctypes.sizeof(params_ptr), None)
env_ptr = ctypes.c_void_p()
k32.ReadProcessMemory(h, ctypes.c_void_p(params_ptr.value + 0x80), ctypes.byref(env_ptr), ctypes.sizeof(env_ptr), None)
CHUNK = 0x10000
chunks, addr = [], env_ptr.value
while True:
    buf = ctypes.create_string_buffer(CHUNK)
    nread = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, CHUNK, ctypes.byref(nread))
    if not ok or nread.value == 0: break
    data = buf.raw[:nread.value]
    chunks.append(data)
    if b"\x00\x00\x00\x00" in data: break
    addr += nread.value
text = b"".join(chunks).decode("utf-16-le", errors="replace")
for e in text.split("\x00"):
    if "=" in e and "exam" in e.split("=", 1)[0].lower():
        print(f"  {e}")
