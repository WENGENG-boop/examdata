"""只读诊断：读取 PID 22612 的进程 CWD（通过 PEB），不修改任何状态。"""
import ctypes
from ctypes import wintypes

class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Reserved1", ctypes.c_void_p),
        ("PebBaseAddress", ctypes.c_void_p),
        ("Reserved2", ctypes.c_void_p * 2),
        ("UniqueProcessId", ctypes.c_void_p),
        ("Reserved3", ctypes.c_void_p),
    ]

class UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", ctypes.c_ushort),
        ("MaximumLength", ctypes.c_ushort),
        ("Buffer", ctypes.c_void_p),
    ]

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
import sys
PID = int(sys.argv[1]) if len(sys.argv) > 1 else 22612

h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, PID)
if not h:
    raise SystemExit(f"OpenProcess failed: {ctypes.get_last_error()}")

pbi = PROCESS_BASIC_INFORMATION()
status = ntdll.NtQueryInformationProcess(h, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None)
if status != 0:
    raise SystemExit(f"NtQueryInformationProcess status={status:#x}")

peb = pbi.PebBaseAddress
params_ptr = ctypes.c_void_p()
ok = k32.ReadProcessMemory(h, ctypes.c_void_p(peb + 0x20), ctypes.byref(params_ptr), ctypes.sizeof(params_ptr), None)
if not ok:
    raise SystemExit(f"ReadProcessMemory(ProcessParameters) failed: {ctypes.get_last_error()}")
params = params_ptr.value

us = UNICODE_STRING()
ok = k32.ReadProcessMemory(h, ctypes.c_void_p(params + 0x38), ctypes.byref(us), ctypes.sizeof(us), None)
if not ok:
    raise SystemExit(f"ReadProcessMemory(CurrentDirectory) failed: {ctypes.get_last_error()}")

buf = ctypes.create_unicode_buffer(us.Length // 2 + 1)
ok = k32.ReadProcessMemory(h, ctypes.c_void_p(us.Buffer), buf, us.Length, None)
if not ok:
    raise SystemExit(f"ReadProcessMemory(DosPath) failed: {ctypes.get_last_error()}")

print("PID", PID, "CWD:", buf.value)
