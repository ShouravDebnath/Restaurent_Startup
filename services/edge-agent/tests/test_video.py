"""Synthetic decoded MP4s and explicitly simulated device/network failures; no hardware."""

import io
import multiprocessing
import time
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from restaurant_edge.capture import Capture
from restaurant_edge.rtsp_gateway import packet, rewrite_response
from restaurant_edge.source_config import SourceDefinition, SourceRegistry
from restaurant_edge.video_sources import OpenCVSource, SourceFailure, synthetic_mp4


def definition(path=None, **overrides):
    return SourceDefinition(reference="synthetic", organization_id=uuid4(), location_id=uuid4(),
        camera_id=uuid4(), kind="mp4" if path else "webcam", authorized=True, synthetic=True,
        file=str(path) if path else None, **overrides)


def wait_for(test, timeout=12):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if test():
            return
        time.sleep(0.05)
    raise AssertionError("Expected synthetic reader condition was not reached")


def blocked_reader(*args):
    time.sleep(60)


def failing_reader(source, mailbox, cancel, fps, loop):
    mailbox.put({"status":"ERROR", "reason":"READ_FAILED"})
    mailbox.close()
    mailbox.join_thread()


def recovering_reader(source, mailbox, cancel, fps, loop):
    marker=Path(source.file)
    if not marker.exists():
        marker.write_text('synthetic first connection failure')
        mailbox.put({'status':'ERROR','reason':'READ_FAILED'})
    else:
        while not cancel.wait(.1):
            mailbox.put({'status':'ONLINE','reason':None,'jpeg':b'\xff\xd8synthetic',
                'received_monotonic':time.monotonic(),'received_at':datetime.now(UTC).isoformat(),
                'generation':'reconnected','sequence':1,'width':20,'height':20},timeout=1)
    mailbox.close()
    mailbox.join_thread()


def test_real_synthetic_mp4_decode_timestamps_eof_and_release(tmp_path):
    path = synthetic_mp4(tmp_path / "sample.mp4", seconds=0.4, fps=10)
    source = OpenCVSource(definition(path))
    source.open()
    frames = []
    try:
        while (frame := source.read()) is not None:
            frames.append(frame)
    finally:
        source.close()
    assert len(frames) == 4
    assert all(f.pixels.shape[:2] == (360,640) and f.received_at.utcoffset().total_seconds()==0 for f in frames)
    assert [f.sequence for f in frames] == [1,2,3,4]
    assert frames[-1].media_seconds >= frames[0].media_seconds
    assert source.capture is None
    with pytest.raises(ValueError):
        synthetic_mp4(path)


def test_supervised_mp4_sampling_completion_and_repeatable_stop(tmp_path):
    path = synthetic_mp4(tmp_path / "sample.mp4", seconds=1)
    capture = Capture(definition(path), fps=2)
    try:
        capture.start()
        wait_for(lambda: capture.health()["status"] == "ONLINE")
        assert capture.frame().startswith(b"\xff\xd8")
        assert capture.health()["sampling_fps"] == 2
        wait_for(lambda: capture.health()["status"] == "FILE_ENDED")
        assert capture.frame() is None and capture.process is None
    finally:
        capture.stop()
        capture.stop()
    assert capture.health()["status"] == "STOPPED"


def test_hung_simulated_webcam_is_terminated_without_hanging_server():
    capture = Capture(definition(), worker=blocked_reader, watchdog=0.5, retries=0)
    capture.start()
    wait_for(lambda: capture.health()["status"] == "STALE")
    capture.stop()
    assert capture.process is None and capture.frame() is None


def test_simulated_device_failure_has_bounded_reconnect():
    capture = Capture(definition(), worker=failing_reader, retries=1)
    capture.start()
    try:
        wait_for(lambda: capture.health()["reconnect_attempts"]==1 and capture.health()["status"]=="ERROR")
        assert capture.process is None and capture.frame() is None
    finally:
        capture.stop()


@pytest.mark.parametrize("host", ["127.0.0.1","169.254.169.254","8.8.8.8","::1","::ffff:127.0.0.1","224.0.0.1","0.0.0.0","camera.invalid"])
def test_unapproved_network_destinations_are_rejected(host):
    with pytest.raises(ValueError):
        SourceDefinition(reference="camera",organization_id=uuid4(),location_id=uuid4(),camera_id=uuid4(),
                         authorized=True,kind="rtsp",host=host)


def test_mp4_root_container_and_scope_protection(tmp_path):
    path = synthetic_mp4(tmp_path / "sample.mp4", seconds=0.2)
    source = definition(path)
    registry = SourceRegistry([source],[tmp_path])
    assert registry.get(source.organization_id,source.location_id,source.camera_id,"synthetic") is source
    assert registry.get(uuid4(),source.location_id,source.camera_id,"synthetic") is None
    outside = tmp_path / "other"
    outside.mkdir()
    with pytest.raises(ValueError):
        SourceRegistry([source],[outside])
    bad = tmp_path / "playlist.mp4"
    bad.write_text("#EXTM3U\nhttp://not-authorized.invalid/video")
    with pytest.raises(ValueError):
        SourceRegistry([definition(bad)],[tmp_path])


@pytest.mark.parametrize("body", [
    b"RTSP/1.0 302 Moved\r\nLocation: rtsp://169.254.169.254/x\r\n\r\n",
    b"RTSP/1.0 200 OK\r\nContent-Base: rtsp://10.0.0.2/x\r\n\r\n",
    b"RTSP/1.0 200 OK\r\nTransport: RTP/AVP;unicast\r\n\r\n",
    b"RTSP/1.0 200 OK\r\n\r\na=control:http://169.254.169.254/x",
])
def test_rtsp_control_redirects_udp_and_foreign_sdp_are_rejected(body):
    with pytest.raises(SourceFailure):
        rewrite_response(body,"rtsp://10.0.0.1:554","rtsp://127.0.0.1:40000")


def test_rtsp_interleaved_packet_and_safe_authority_rewrite():
    data=b"$\x00\x00\x03abc"
    assert packet(io.BytesIO(data)) == data
    source=b"RTSP/1.0 200 OK\r\nContent-Base: rtsp://10.0.0.1:554/video\r\n\r\n"
    result=rewrite_response(source,"rtsp://10.0.0.1:554","rtsp://127.0.0.1:40000")
    assert b"rtsp://127.0.0.1:40000/video" in result and b"10.0.0.1" not in result


def test_rtsp_default_port_rewrite_and_audio_removal():
    body = (b"v=0\r\na=control:rtsp://10.0.0.1/session\r\n"
            b"m=audio 0 RTP/AVP 0\r\na=control:audio\r\n"
            b"m=video 0 RTP/AVP 96\r\na=control:rtsp://10.0.0.1:554/video\r\n")
    response = (b"RTSP/1.0 200 OK\r\nContent-Type: application/sdp\r\n"
                b"Content-Base: rtsp://10.0.0.1/\r\nContent-Length: " + str(len(body)).encode()
                + b"\r\n\r\n" + body)
    rewritten = rewrite_response(response, "rtsp://10.0.0.1:554", "rtsp://127.0.0.1:40000")
    header, filtered = rewritten.split(b"\r\n\r\n", 1)
    assert b"audio" not in filtered and b"m=video" in filtered
    assert b"10.0.0.1" not in rewritten and b"rtsp://127.0.0.1:40000/session" in filtered
    assert b"Content-Length: " + str(len(filtered)).encode() in header


def test_rtsp_audio_only_is_rejected():
    with pytest.raises(SourceFailure, match="VIDEO_TRACK_UNAVAILABLE"):
        rewrite_response(b"RTSP/1.0 200 OK\r\nContent-Type: application/sdp\r\n\r\nv=0\r\nm=audio 0 RTP/AVP 0\r\n",
                         "rtsp://10.0.0.1:554", "rtsp://127.0.0.1:40000")


def test_simulated_rtsp_reconnect_recovers_and_stop_releases_process(tmp_path):
    source=SourceDefinition(reference='synthetic',organization_id=uuid4(),location_id=uuid4(),
        camera_id=uuid4(),kind='rtsp',host='10.0.0.1',authorized=True,synthetic=True,
        file=str(tmp_path/'reconnect-marker'))
    capture=Capture(source,worker=recovering_reader,retries=1)
    try:
        capture.start()
        wait_for(lambda:capture.health()['status']=='ONLINE')
        assert capture.health()['reconnect_attempts']==1
        assert capture.frame().startswith(b'\xff\xd8')
    finally:capture.stop()
    assert capture.process is None


def test_real_mp4_loop_generations_and_repeated_reader_cleanup(tmp_path):
    path=synthetic_mp4(tmp_path/'sample.mp4',seconds=.6)
    before={p.pid for p in multiprocessing.active_children()}
    for _ in range(3):
        capture=Capture(definition(path),fps=5,loop=True)
        try:
            capture.start()
            wait_for(lambda reader=capture:reader.health()['status']=='ONLINE')
            generation=capture.health()['generation']
            wait_for(lambda reader=capture, previous=generation:reader.health().get('generation')!=previous)
            assert capture.health()['loop'] is True
        finally:capture.stop()
        assert capture.process is None and not capture.monitor.is_alive()
    assert {p.pid for p in multiprocessing.active_children()}==before


@pytest.mark.parametrize('fps',[5,20])
def test_real_mp4_different_frame_rates_and_monotonic_pacing(tmp_path,fps):
    path=synthetic_mp4(tmp_path/'timing.mp4',seconds=.4,fps=fps)
    reader=OpenCVSource(definition(path))
    reader.open()
    frames=[]
    try:
        while (frame:=reader.read()) is not None:frames.append(frame)
    finally:reader.close()
    assert len(frames)==int(.4*fps)
    assert frames[-1].received_monotonic>=frames[0].received_monotonic+(len(frames)-1)/fps-.05
    assert all(b.received_monotonic>=a.received_monotonic for a,b in pairwise(frames))


def test_corrupt_mp4_fails_without_leaking_private_filename(tmp_path):
    path=tmp_path/('private-'+uuid4().hex+'.mp4')
    path.write_bytes(b'\x00\x00\x00\x18ftypmp42'+b'\x00'*100)
    source=definition(path)
    SourceRegistry([source],[tmp_path])
    capture=Capture(source)
    try:
        capture.start()
        wait_for(lambda:capture.health()['status']=='ERROR')
        assert capture.frame() is None
        assert str(path) not in str(capture.health())
        assert capture.health()['reason'] in {'OPEN_FAILED','READER_FAILED'}
    finally:capture.stop()


def test_wall_clock_jump_does_not_change_media_pacing(monkeypatch,tmp_path):
    import cv2
    import numpy as np

    from restaurant_edge import video_sources
    class Video:
        sequence=0
        def open(self,*args):return True
        def release(self):pass
        def get(self,key):
            return {cv2.CAP_PROP_FRAME_WIDTH:20,cv2.CAP_PROP_FRAME_HEIGHT:20,
                cv2.CAP_PROP_FPS:10,cv2.CAP_PROP_FRAME_COUNT:2,
                cv2.CAP_PROP_POS_MSEC:max(0,self.sequence-1)*100}[key]
        def read(self):
            self.sequence+=1
            return True,np.zeros((20,20,3),dtype=np.uint8)
    ticks=iter([10.,10.,10.,10.1,10.1])
    dates=iter([datetime(2099,1,1,tzinfo=UTC),datetime(1999,1,1,tzinfo=UTC)])
    monkeypatch.setattr(cv2,'VideoCapture',Video)
    monkeypatch.setattr(video_sources,'time',SimpleNamespace(monotonic=lambda:next(ticks),sleep=lambda _:None))
    monkeypatch.setattr(video_sources,'datetime',SimpleNamespace(now=lambda _:next(dates)))
    reader=OpenCVSource(definition(tmp_path/'synthetic.mp4'))
    reader.open()
    first,second=reader.read(),reader.read()
    reader.close()
    assert second.received_at<first.received_at
    assert second.received_monotonic>first.received_monotonic
    assert second.media_seconds>first.media_seconds
