import ctypes, sys
PID = int(sys.argv[1])
class PBI(ctypes.Structure):
    _fields_ = [("R1", ctypes.c_void_p), ("Peb", ctypes.c_void_p), ("R2", ctypes.c_void_p * 2), ("Pid", ctypes.c_void_p), ("R3", ctypes.c_void_p)]
k32 = ctypes.WinDLL("kernel32", use_last_error=True); ntdll = ctypes.WinDLL("ntdll")
h = k32.OpenProcess(0x0400 | 0x0010, False, PID)
pbi = PBI(); ntdll.NtQueryInformationProcess(h, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None)
pp = ctypes.c_void_p(); k32.ReadProcessMemory(h, ctypes.c_void_p(pbi.Peb + 0x20), ctypes.byref(pp), ctypes.sizeof(pp), None)
ep = ctypes.c_void_p(); k32.ReadProcessMemory(h, ctypes.c_void_p(pp.value + 0x80), ctypes.byref(ep), ctypes.sizeof(ep), None)
# read 256KB in one go from env pointer
buf = ctypes.create_string_buffer(0x40000)
nr = ctypes.c_size_t(0)
ok = k32.ReadProcessMemory(h, ctypes.c_void_p(ep.value), buf, 0x40000, ctypes.byref(nr))
text = buf.raw[:nr.value].decode("utf-16-le", errors="replace")
print(f"PID {PID}: read {nr.value} bytes from env ptr")
for needle in ["EXAMDATA_DATA_DIR", "EXAMDATA_DATABASE_URL", "TMP=", "TEMP="]:
    print(f"  substring {needle!r}: {'FOUND' if needle in text else 'NOT FOUND'}")
# first 25 entries
entries = [e for e in text.split("\x00") if "=" in e][:25]
print("  first entries:")
for e in entries: print("    ", repr(e[:110]))
