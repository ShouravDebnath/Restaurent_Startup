"""RF-DETR Nano, static FP32 opset-17 export of the approved native checkpoint.

Contract follows Roboflow RF-DETR 1.12.0 (Apache-2.0), pinned source
639eac4555ceb89ef399ccda3fde716bbcfe34cb. See third_party/RFDETR.md.
Only NumPy and the existing CPU ONNX Runtime are used at runtime.
"""

import time

import numpy as np

from restaurant_edge.detectors.base import Person
from restaurant_edge.detectors.onnx_detector import ModelUnavailable

MEAN = np.array([.485, .456, .406], dtype=np.float32)
STD = np.array([.229, .224, .225], dtype=np.float32)


def preprocess(bgr):
    if bgr.dtype != np.uint8 or bgr.ndim != 3 or bgr.shape[2] != 3:
        raise ValueError('Expected original uint8 BGR image')
    height, width = bgr.shape[:2]
    if not 1 <= width <= 4096 or not 1 <= height <= 2160:
        raise ValueError('Frame dimensions rejected')
    rgb = bgr[:, :, ::-1].astype(np.float32) / np.float32(255)
    # Half-pixel bilinear on floats, no antialiasing or uint8 interpolation rounding.
    y = np.maximum((np.arange(384, dtype=np.float32) + .5) * (height / 384) - .5, 0)
    x = np.maximum((np.arange(384, dtype=np.float32) + .5) * (width / 384) - .5, 0)
    y0, x0 = y.astype(np.intp), x.astype(np.intp)
    y1, x1 = np.minimum(y0 + 1, height - 1), np.minimum(x0 + 1, width - 1)
    wy, wx = (y - y0).astype(np.float32)[:, None, None], (x - x0).astype(np.float32)[None, :, None]
    top = rgb[y0[:, None], x0] * (1 - wx) + rgb[y0[:, None], x1] * wx
    bottom = rgb[y1[:, None], x0] * (1 - wx) + rgb[y1[:, None], x1] * wx
    resized = top * (1 - wy) + bottom * wy
    return np.ascontiguousarray(((resized - MEAN) / STD).transpose(2, 0, 1)[None])


def decode(boxes, logits):
    if (boxes.shape != (1, 300, 4) or logits.shape != (1, 300, 91)
        or boxes.dtype != np.float32 or logits.dtype != np.float32
        or not np.isfinite(boxes).all() or not np.isfinite(logits).all()
        or np.any(np.abs(boxes[:, :, :2]) > 4)
        or np.any(boxes[:, :, 2:] <= 0) or np.any(boxes[:, :, 2:] > 8)):
        raise ValueError('RF-DETR output contract mismatch')
    # Publisher bbox_reparam normalizes units, but centers/sizes can extend
    # beyond the picture. Bound gross values, then clip converted corners.
    scores = 1 / (1 + np.exp(-np.clip(logits[0], -88, 88)))
    # Publisher's global top-300 query/class pairs, then sparse COCO person slot 1.
    # Last slot is COCO category 90; do not treat it as generic background.
    flat = scores.ravel()
    selected = np.argsort(flat, kind='stable')[-300:][::-1]
    selected = selected[(selected % 91 == 1) & (flat[selected] >= .05)]
    result = []
    for index in selected:
        cx, cy, width, height = boxes[0, index // 91]
        box = np.clip([cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2], 0, 1)
        if box[2] > box[0] and box[3] > box[1]:
            result.append(Person(tuple(float(v) for v in box), float(flat[index])))
        if len(result) > 128:
            raise ValueError('Person output limit exceeded')
    # Set prediction: no YOLOX NMS, which could discard crowded people.
    return tuple(result)


class RfDetrNano:
    def __init__(self, artifact):
        import onnxruntime as ort
        if artifact.model_id != 'rfdetr_nano':
            raise ModelUnavailable('MODEL_CONTRACT_REJECTED')
        ort.disable_telemetry_events()
        options = ort.SessionOptions()
        options.intra_op_num_threads, options.inter_op_num_threads = 2, 1
        options.log_severity_level = 4
        # Validated against PyTorch on this host. Optimized fusion changed
        # query selection on one generated input; keep the original tolerance.
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        self.session = ort.InferenceSession(artifact.bytes(), sess_options=options,
                                           providers=['CPUExecutionProvider'])
        inputs, outputs = self.session.get_inputs(), self.session.get_outputs()
        contracts = {'dets': [1, 300, 4], 'labels': [1, 300, 91]}
        if (len(inputs) != 1 or inputs[0].shape != [1, 3, 384, 384]
            or inputs[0].type != 'tensor(float)' or len(outputs) != 2
            or {o.name: o.shape for o in outputs} != contracts
            or any(o.type != 'tensor(float)' for o in outputs)):
            raise ModelUnavailable('MODEL_CONTRACT_REJECTED')
        self.input_name = inputs[0].name
        self.last_metrics = {}

    def detect(self, bgr):
        started = time.perf_counter()
        tensor = preprocess(bgr)
        prepared = time.perf_counter()
        boxes, logits = self.session.run(['dets', 'labels'], {self.input_name: tensor})
        inferred = time.perf_counter()
        result = decode(boxes, logits)
        finished = time.perf_counter()
        self.last_metrics = {'pre_ms': (prepared - started) * 1000,
                             'inference_ms': (inferred - prepared) * 1000,
                             'post_ms': (finished - inferred) * 1000,
                             'total_ms': (finished - started) * 1000}
        return result

    def close(self):
        self.session = None
