"""REAL pretrained model benchmark using ONLY a newly generated geometric MP4.

No people or real recordings; no accuracy metric. Reports timed-loop throughput
separately from a paced synthetic video/association/shadow-engine soak.
"""

import argparse
import json
import socket
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from restaurant_edge.analysis_config import AnalysisConfig
from restaurant_edge.analysis_metrics import process_metrics
from restaurant_edge.association import associate
from restaurant_edge.detectors.factory import detector_for
from restaurant_edge.detectors.onnx_detector import ModelCatalog
from restaurant_edge.state_engine import StateEngine
from restaurant_edge.video_sources import synthetic_mp4

ROOT = Path(__file__).resolve().parents[1]


def distribution(values):
    return {'mean': float(np.mean(values)), 'p50': float(np.quantile(values, .5)),
            'p95': float(np.quantile(values, .95)), 'max': float(np.max(values))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--seconds', type=float, default=600)
    parser.add_argument('--sampling-fps', type=float, default=2)
    args = parser.parse_args()
    if not 30 <= args.seconds <= 3600 or not .5 <= args.sampling_fps <= 3:
        parser.error('Use 30–3600 seconds and 0.5–3 sampled FPS')
    folder = Path(args.output_dir).resolve()
    if not any(folder.is_relative_to(ROOT / d) for d in ('.secrets', '.cache')) or folder.exists():
        parser.error('Choose a NEW private project .secrets/.cache output directory')
    folder.mkdir(parents=True)
    video = synthetic_mp4(folder / 'generated-geometric-only.mp4', seconds=8)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError('Generated MP4 did not open')
    attempts = []

    def deny(*_args, **_kwargs):
        attempts.append('BLOCKED_NETWORK_ATTEMPT')
        raise RuntimeError('Synthetic benchmark must remain offline')

    socket.socket.connect = deny
    socket.create_connection = deny
    socket.getaddrinfo = deny
    artifact = ModelCatalog.load(args.catalog).get('rfdetr_nano')
    before_load = process_metrics()
    loading = time.perf_counter()
    detector = detector_for(artifact)
    load_seconds = time.perf_counter() - loading
    profiles = []
    for polygon in [[(.1, .25), (.45, .25), (.45, .8), (.1, .8)],
                    [(.55, .25), (.9, .25), (.9, .8), (.55, .8)]]:
        profiles.append({'table_id': str(uuid4()), 'zone_id': str(uuid4()), 'zone_revision': 1,
                         'seating': polygon, 'visibility_reviewed': True})
    config = AnalysisConfig(organization_id=uuid4(), location_id=uuid4(), camera_id=uuid4(),
                            source_width=640, source_height=360, model='rfdetr_nano', regions=profiles)
    engine = StateEngine(config)
    engine.model_sha256 = artifact.sha256
    engine.manual([{'id': str(config.regions[0].table_id), 'operational_revision': 1,
                    'state_source': 'manual', 'current_state': 'CLEANING',
                    'state_since': datetime.now(UTC).isoformat()}], time.monotonic(), datetime.now(UTC).isoformat())

    def frame():
        ok, image = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, image = cap.read()
        if not ok:
            raise RuntimeError('Generated MP4 read failed')
        return image

    try:
        for _ in range(10):
            detector.detect(frame())
        batch = []
        started = time.perf_counter()
        for _ in range(50):
            detector.detect(frame())
            batch.append(detector.last_metrics.copy())
        saturated_seconds = time.perf_counter() - started
        samples, dropped = [], 0
        cpu_started = time.process_time()
        started = time.monotonic()
        next_due, sequence = started, 0
        interval = 1 / args.sampling_fps
        while time.monotonic() - started < args.seconds:
            now = time.monotonic()
            if next_due > now:
                time.sleep(min(next_due - now, .5))
                continue
            pixels = frame()
            received = time.monotonic()
            people = detector.detect(pixels)
            inferred = time.monotonic()
            utc = datetime.now(UTC).isoformat()
            sequence += 1
            observations = associate(people, config)
            if inferred - received <= config.settings.result_max_age:
                engine.step(observations, received, utc, 'generated-geometric', sequence)
            else:
                engine.invalidate('BENCHMARK_RESULT_STALE', inferred, utc)
            samples.append({**detector.last_metrics, 'person_candidates_above_005': len(people),
                            'result_age_ms': (inferred - received) * 1000})
            next_due += interval
            if next_due < inferred:
                missed = int((inferred - next_due) // interval) + 1
                dropped += missed
                next_due += missed * interval
        elapsed = time.monotonic() - started
        cpu_used = time.process_time() - cpu_started
        final = process_metrics()
        snapshot = engine.snapshot(time.monotonic())
        if engine.tables[str(config.regions[0].table_id)].state != 'CLEANING' or attempts:
            raise RuntimeError('Protected manual state or offline boundary failed')
        report = {'recorded_at_utc': datetime.now(UTC).isoformat(), 'model_id': 'rfdetr_nano',
                  'model_sha256': artifact.sha256, 'evidence_kind': 'real_pretrained_model_synthetic_no_people',
                  'provider': 'CPUExecutionProvider', 'threads': [2, 1], 'precision': 'FP32',
                  'graph_optimization': 'ORT_DISABLE_ALL',
                  'original_dimensions': [640, 360], 'model_dimensions': [384, 384],
                  'source': 'newly generated geometric MP4; no private/person footage',
                  'model_load_seconds': load_seconds, 'warmup_frames': 10,
                  'saturated': {'frames': 50, 'elapsed_seconds': saturated_seconds,
                    'completed_fps_including_decode': 50 / saturated_seconds,
                    'latency_ms': {k: distribution([r[k] for r in batch]) for k in batch[0]}},
                  'paced': {'requested_seconds': args.seconds, 'elapsed_seconds': elapsed,
                    'sampling_fps_target': args.sampling_fps, 'completed_frames': len(samples),
                    'completed_fps': len(samples) / elapsed, 'missed_sampling_slots': dropped,
                    'process_cpu_seconds': cpu_used, 'logical_core_equivalents': cpu_used / elapsed,
                    'latency_ms': {k: distribution([r[k] for r in samples]) for k in detector.last_metrics},
                    'result_age_ms': distribution([r['result_age_ms'] for r in samples]),
                    'frames_with_person_candidates': sum(r['person_candidates_above_005'] > 0 for r in samples),
                    'maximum_person_candidates': max(r['person_candidates_above_005'] for r in samples)},
                  'memory_before_model': before_load, 'memory_after_soak': final,
                  'manual_cleaning_preserved': True, 'shadow_snapshot': snapshot,
                  'shadow_events': list(engine.events), 'cloud_mutations': 0,
                  'blocked_network_attempts': len(attempts), 'accuracy_measured': False,
                  'limits': ['No positive person examples or representative restaurant validation',
                    'Single synthetic source; not a full browser/cloud load or multi-camera capacity test',
                    'Own-process Windows working set; not total-system RAM or private committed bytes',
                    'No measured temperature/power/throttling data; ten-minute soak is not hardware certification']}
        with (folder / 'benchmark.json').open('x', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
        print(json.dumps({k: report[k] for k in ['model_id', 'model_load_seconds', 'saturated', 'paced',
                                                'memory_after_soak', 'manual_cleaning_preserved', 'accuracy_measured']}, indent=2))
    finally:
        detector.close()
        cap.release()


if __name__ == '__main__':
    main()
