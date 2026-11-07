"""Windows reader lifetime containment, not a native-code security sandbox."""

import ctypes
import os
import sys
import threading
import time
from ctypes import wintypes


def watch_parent():
    """Fallback also covers the short interval before the parent assigns its job."""
    import multiprocessing
    parent = multiprocessing.parent_process()
    if parent is None:
        return
    def monitor():
        while parent.is_alive():
            time.sleep(.2)
        os._exit(0)  # Parent died: do not retain a native reader or gateway thread.
    threading.Thread(target=monitor, daemon=True, name='reader-parent-watch').start()


class ReaderJob:
    def __init__(self):
        self.handle = None
        if sys.platform != 'win32':
            return

        class Basic(ctypes.Structure):
            _fields_ = [('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),
                ('flags',wintypes.DWORD),('minimum',ctypes.c_size_t),('maximum',ctypes.c_size_t),
                ('active',wintypes.DWORD),('affinity',ctypes.c_size_t),
                ('priority',wintypes.DWORD),('scheduling',wintypes.DWORD)]

        class Extended(ctypes.Structure):
            _fields_ = [('basic',Basic),('io',ctypes.c_ulonglong*6),
                ('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),
                ('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]

        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p,wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
        self.kernel.SetInformationJobObject.restype = wintypes.BOOL
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE,wintypes.HANDLE]
        self.kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.CreateJobObjectW(None,None)
        info = Extended()
        info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle or not self.kernel.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):
            self.close()
            raise RuntimeError('Reader lifetime containment unavailable')

    def attach(self,pid):
        if self.handle is None:
            return
        process = self.kernel.OpenProcess(0x0101,False,pid)  # SET_QUOTA | TERMINATE
        try:
            if not process or not self.kernel.AssignProcessToJobObject(self.handle,process):
                raise RuntimeError('Reader lifetime containment unavailable')
        finally:
            if process:
                self.kernel.CloseHandle(process)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
