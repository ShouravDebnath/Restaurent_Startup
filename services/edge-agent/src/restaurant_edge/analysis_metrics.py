"""Own-process measurements only; no new monitoring dependency or data upload."""

import os
import sys
import time


def memory_metrics():
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD),
                        *[(name, ctypes.c_size_t) for name in (
                            'peak_working', 'working', 'peak_paged', 'paged',
                            'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile')]]

        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return {'working_set_bytes': counters.working, 'peak_working_set_bytes': counters.peak_working}
    return {'working_set_bytes': None, 'peak_working_set_bytes': None}


def process_metrics():
    return {'process_id': os.getpid(), 'process_cpu_seconds': time.process_time(), **memory_metrics()}
