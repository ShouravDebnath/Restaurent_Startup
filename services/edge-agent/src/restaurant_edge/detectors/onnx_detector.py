"""YOLOX-Tiny adapter. No download, arbitrary browser path or implicit approval.

Contract follows the official YOLOX ONNX demo; exact weights remain unverified
until their separate licensing/acquisition gate is satisfied.
"""

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from restaurant_edge.detectors.base import Person


class ModelUnavailable(RuntimeError):
    pass


MODEL_LIMITS = {'yolox_tiny': 30_000_000, 'rfdetr_nano': 160_000_000}


@dataclass(frozen=True)
class ApprovedArtifact:
    path: Path
    sha256: str
    model_id: str = 'yolox_tiny'

    def bytes(self):
        limit = MODEL_LIMITS.get(self.model_id)
        if limit is None or not isinstance(self.sha256, str) or not re.fullmatch('[a-f0-9]{64}', self.sha256):
            raise ModelUnavailable('MODEL_APPROVAL_REQUIRED')
        if self.path.stat().st_size > limit:
            raise ModelUnavailable('MODEL_SIZE_REJECTED')
        with self.path.open('rb') as handle:
            data = handle.read(limit + 1)
        if len(data) > limit:
            raise ModelUnavailable('MODEL_SIZE_REJECTED')
        if len(data) < 1024 or hashlib.sha256(data).hexdigest() != self.sha256:
            raise ModelUnavailable('MODEL_INTEGRITY_FAILED')
        return data


class ModelCatalog:
    """Operator-provisioned approval manifest. Empty unless explicitly supplied."""
    def __init__(self, entries=None):
        self.entries = entries or {}

    @classmethod
    def load(cls, manifest):
        manifest = Path(manifest).resolve(strict=True)
        data = json.loads(manifest.read_text(encoding='utf-8'))
        if data.get('format_version') != 1 or set(data) != {'format_version', 'models'}:
            raise ValueError('Invalid model approval manifest')
        entries = {}
        if not isinstance(data['models'], list) or len(data['models']) > len(MODEL_LIMITS):
            raise ModelUnavailable('MODEL_APPROVAL_REQUIRED')
        for model in data['models']:
            if (not isinstance(model, dict) or model.get('id') not in MODEL_LIMITS
                or model['id'] in entries or model.get('license_status') != 'cleared'
                or not model.get('license_evidence') or model.get('artifact_verified') is not True):
                raise ModelUnavailable('MODEL_APPROVAL_REQUIRED')
            path = (manifest.parent / model['filename']).resolve(strict=True)
            if not path.is_relative_to(manifest.parent) or path.suffix != '.onnx':
                raise ModelUnavailable('MODEL_PATH_REJECTED')
            artifact = ApprovedArtifact(path, model['sha256'], model['id'])
            artifact.bytes()
            entries[model['id']] = artifact
        return cls(entries)

    def get(self, model_id):
        if model_id not in self.entries:
            raise ModelUnavailable('MODEL_APPROVAL_REQUIRED')
        return self.entries[model_id]


def preprocess(bgr):
    if bgr.dtype != np.uint8 or bgr.ndim != 3 or bgr.shape[2] != 3:
        raise ValueError('Expected original uint8 BGR image')
    height, width = bgr.shape[:2]
    if not 1 <= width <= 4096 or not 1 <= height <= 2160:
        raise ValueError('Frame dimensions rejected')
    ratio = min(416 / width, 416 / height)
    resized = cv2.resize(bgr, (max(1, int(width * ratio)), max(1, int(height * ratio))))
    padded = np.full((416, 416, 3), 114, dtype=np.uint8)
    padded[:resized.shape[0], :resized.shape[1]] = resized
    return np.ascontiguousarray(padded.transpose(2, 0, 1)[None], dtype=np.float32), ratio


def decode(output, ratio, width, height):
    if output.shape != (1, 3549, 85) or not np.isfinite(output).all():
        raise ValueError('YOLOX output contract mismatch')
    raw = output[0]
    if np.any(raw[:, 4:] < 0) or np.any(raw[:, 4:] > 1) or np.any(np.abs(raw[:, 2:4]) > 20):
        raise ValueError('YOLOX scores/box contract mismatch')
    scores = raw[:, 4] * raw[:, 5]  # COCO person class 0 for this exact adapter.
    indices = np.flatnonzero(scores >= .05)
    if not len(indices):
        return ()
    grids, strides = [], []
    for stride in (8, 16, 32):
        y, x = np.mgrid[:416 // stride, :416 // stride]
        grids.append(np.stack((x, y), axis=-1).reshape(-1, 2))
        strides.append(np.full((len(grids[-1]), 1), stride))
    grid, stride = np.concatenate(grids)[indices], np.concatenate(strides)[indices]
    center = (raw[indices, :2] + grid) * stride
    size = np.exp(raw[indices, 2:4]) * stride
    boxes = np.concatenate((center - size / 2, center + size / 2), axis=1) / ratio
    boxes[:, (0, 2)] = np.clip(boxes[:, (0, 2)] / width, 0, 1)
    boxes[:, (1, 3)] = np.clip(boxes[:, (1, 3)] / height, 0, 1)
    order = np.argsort(scores[indices])[::-1]
    result = []
    while len(order):
        current = order[0]
        box = boxes[current]
        if box[2] > box[0] and box[3] > box[1]:
            result.append(Person(tuple(float(v) for v in box), float(scores[indices[current]])))
        if len(result) > 128:
            raise ValueError('Person output limit exceeded')
        remaining = order[1:]
        others = boxes[remaining]
        overlap = np.maximum(0, np.minimum(box[2:], others[:, 2:]) - np.maximum(box[:2], others[:, :2])).prod(axis=1)
        area = max(0, box[2] - box[0]) * max(0, box[3] - box[1])
        areas = np.maximum(0, others[:, 2:] - others[:, :2]).prod(axis=1)
        order = remaining[overlap / np.maximum(area + areas - overlap, 1e-12) <= .45]
    return tuple(result)


class OnnxDetector:
    def __init__(self, artifact):
        import onnxruntime as ort
        ort.disable_telemetry_events()
        options = ort.SessionOptions()
        options.intra_op_num_threads, options.inter_op_num_threads = 2, 1
        options.log_severity_level = 4
        # Bytes + pinned approved hash: no model-relative external-data file access.
        self.session = ort.InferenceSession(artifact.bytes(), sess_options=options,
                                           providers=['CPUExecutionProvider'])
        inputs, outputs = self.session.get_inputs(), self.session.get_outputs()
        if (len(inputs) != 1 or inputs[0].shape != [1, 3, 416, 416]
            or inputs[0].type != 'tensor(float)' or len(outputs) != 1
            or outputs[0].shape != [1, 3549, 85]):
            raise ModelUnavailable('MODEL_CONTRACT_REJECTED')
        self.input_name = inputs[0].name
        self.last_metrics = {}

    def detect(self, bgr):
        started = time.perf_counter()
        tensor, ratio = preprocess(bgr)
        prepared = time.perf_counter()
        output = self.session.run(None, {self.input_name: tensor})[0]
        inferred = time.perf_counter()
        people = decode(output, ratio, bgr.shape[1], bgr.shape[0])
        finished = time.perf_counter()
        self.last_metrics = {'pre_ms': (prepared - started) * 1000,
                             'inference_ms': (inferred - prepared) * 1000,
                             'post_ms': (finished - inferred) * 1000,
                             'total_ms': (finished - started) * 1000}
        return people

    def close(self):
        self.session = None
