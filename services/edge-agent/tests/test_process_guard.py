"""Actual Windows child cleanup after an abruptly killed verifier-owned parent."""

import ctypes
import json
import subprocess
import sys
import time
from ctypes import wintypes

import pytest

from restaurant_edge.video_sources import synthetic_mp4


@pytest.mark.skipif(sys.platform!='win32',reason='Windows Job Object containment requires Windows')
def test_windows_reader_dies_when_its_parent_is_killed(tmp_path):
    video=synthetic_mp4(tmp_path/'synthetic.mp4',seconds=1)
    receipt=tmp_path/'reader.json'
    script=tmp_path/'parent.py'
    script.write_text('''import json,sys,time
from pathlib import Path
from uuid import uuid4
from restaurant_edge.capture import Capture
from restaurant_edge.source_config import SourceDefinition
if __name__ == '__main__':
    source=SourceDefinition(reference='synthetic',organization_id=uuid4(),location_id=uuid4(),camera_id=uuid4(),kind='mp4',file=sys.argv[1],authorized=True,synthetic=True)
    capture=Capture(source,loop=True)
    capture.start()
    for _ in range(100):
        if capture.health()['status']=='ONLINE':break
        time.sleep(.1)
    else:raise RuntimeError('Synthetic child did not start')
    Path(sys.argv[2]).write_text(json.dumps({'reader':capture.process.pid}))
    time.sleep(60)
''',encoding='utf-8')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT]
    child=None
    process=subprocess.Popen([sys.executable,str(script),str(video),str(receipt)],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        for _ in range(120):
            if receipt.exists():break
            time.sleep(.1)
        assert receipt.exists()
        pid=json.loads(receipt.read_text())['reader']
        child=kernel.OpenProcess(0x100001,False,pid)  # SYNCHRONIZE | TERMINATE
        assert child
        process.terminate()
        process.wait(timeout=5)
        assert kernel.WaitForSingleObject(child,3000)==0
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        if child:
            if kernel.WaitForSingleObject(child,0)!=0:kernel.TerminateProcess(child,1)
            kernel.CloseHandle(child)
