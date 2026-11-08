"""Approved RF-DETR Nano -> private CPU ONNX export. No training/downloads.

Run only in the separately approved hash-locked export environment. Numerical
parity on generated arrays is not positive person/restaurant accuracy evidence.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
import socket
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE_SHA256 = 'd8d6b9ee57d4d0ed2b1f305163624712a0532cb7bce0c747317984fc5457440d'
VERSIONS = {'rfdetr': '1.12.0', 'torch': '2.15.0', 'torchvision': '0.29.2',
            'transformers': '5.22.2', 'onnx': '1.23.2', 'onnxruntime': '1.31.1'}


def private_path(value):
    path = Path(value).resolve()
    if not any(path.is_relative_to(ROOT / d) for d in ('.secrets', '.cache')):
        raise ValueError('Use a private project .secrets or .cache path')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    checkpoint, output = private_path(args.checkpoint), private_path(args.output_dir)
    if output.exists():
        raise ValueError('Choose a new output directory; existing files are preserved')
    if checkpoint.stat().st_size != 366_287_238 or hashlib.sha256(checkpoint.read_bytes()).hexdigest() != NATIVE_SHA256:
        raise ValueError('Approved checkpoint integrity failed')
    if any(importlib.metadata.version(name) != version for name, version in VERSIONS.items()):
        raise ValueError('Use the reviewed exact export toolchain')
    for name in ['HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_TELEMETRY', 'DO_NOT_TRACK']:
        os.environ[name] = '1'
    output.mkdir(parents=True)
    os.environ['RF_HOME'] = str(output / 'private-cache')
    os.environ['HF_HOME'] = str(output / 'private-cache')
    attempts = []

    def reject_network(*_args, **_kwargs):
        attempts.append('BLOCKED_OUTBOUND_ATTEMPT')
        raise RuntimeError('Export is offline; additional acquisition is not approved')

    # Defense in depth, not an OS sandbox. No input accepts a video URL/path.
    socket.socket.connect = reject_network
    socket.socket.connect_ex = reject_network
    socket.create_connection = reject_network
    socket.getaddrinfo = reject_network
    import numpy as np
    import onnx
    import onnxruntime as ort
    import torch
    from PIL import Image
    from rfdetr import RFDETRNano
    from rfdetr.export._runtime.preprocess import preprocess_to_nchw

    sys.path.insert(0, str(ROOT / 'services/edge-agent/src'))
    from restaurant_edge.detectors.rfdetr import preprocess

    ort.disable_telemetry_events()
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    started = time.perf_counter()
    model = RFDETRNano(pretrain_weights=str(checkpoint), device='cpu', trust_checkpoint=False)
    model.model.model.eval()
    path = Path(model.export(format='onnx', output_dir=str(output), batch_size=1,
                            dynamic_batch=False, opset_version=17, verbose=False))
    graph = onnx.load(path, load_external_data=False)
    onnx.checker.check_model(graph, full_check=True)
    if any(t.data_location == onnx.TensorProto.EXTERNAL for t in graph.graph.initializer):
        raise ValueError('External tensor files are not accepted')
    if any(n.domain not in ('', 'ai.onnx') for n in graph.graph.node):
        raise ValueError('Custom operator domain rejected')
    if any(o.version != 17 or o.domain not in ('', 'ai.onnx') for o in graph.opset_import):
        raise ValueError('Unexpected graph opset')
    options = ort.SessionOptions()
    options.intra_op_num_threads, options.inter_op_num_threads = 2, 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    session = ort.InferenceSession(path.read_bytes(), sess_options=options, providers=['CPUExecutionProvider'])
    rng = np.random.default_rng(5105)
    parity = []
    for height, width in [(360, 640), (97, 53), (384, 384)]:
        pixels = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
        tensor = preprocess(pixels)
        expected = preprocess_to_nchw(Image.fromarray(pixels[:, :, ::-1]), 384, 384)
        pre_error = float(np.abs(tensor - expected).max())
        if pre_error > 2e-4:
            raise ValueError('Preprocessing differs from pinned publisher implementation')
        with torch.inference_mode():
            native = model.model.model(torch.from_numpy(tensor))
        boxes, logits = session.run(['dets', 'labels'], {session.get_inputs()[0].name: tensor})
        native_boxes, native_logits = native['pred_boxes'].cpu().numpy(), native['pred_logits'].cpu().numpy()
        box_error = float(np.abs(boxes - native_boxes).max())
        score_error = float(np.abs(logits - native_logits).max())
        if not np.allclose(boxes, native_boxes, rtol=1e-3, atol=1e-4) or not np.allclose(logits, native_logits, rtol=1e-3, atol=1e-3):
            with (output / 'parity-failure.json').open('x', encoding='utf-8') as handle:
                json.dump({'generated_shape': [height, width], 'boxes_max_abs': box_error,
                           'logits_max_abs': score_error,
                           'boxes_p99_abs': float(np.quantile(np.abs(boxes - native_boxes), .99)),
                           'logits_p99_abs': float(np.quantile(np.abs(logits - native_logits), .99))}, handle, indent=2)
            raise ValueError('PyTorch/ONNX numerical parity failed')
        parity.append({'generated_shape': [height, width, 3], 'preprocess_max_abs': pre_error,
                       'boxes_max_abs': box_error, 'logits_max_abs': score_error})
    if attempts:
        raise ValueError('Unapproved outbound fetch attempted during export')
    record = {'recorded_at_utc': datetime.now(UTC).isoformat(), 'model_id': 'rfdetr_nano',
              'native_sha256': NATIVE_SHA256, 'onnx_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'onnx_filename': path.name, 'onnx_bytes': path.stat().st_size, 'opset': 17,
              'versions': VERSIONS, 'provider': session.get_providers(), 'threads': [2, 1],
              'graph_optimization': 'ORT_DISABLE_ALL',
              'inputs': [{'name': x.name, 'shape': x.shape, 'type': x.type} for x in session.get_inputs()],
              'outputs': [{'name': x.name, 'shape': x.shape, 'type': x.type} for x in session.get_outputs()],
              'parity': parity, 'blocked_outbound_attempts': len(attempts),
              'export_and_parity_seconds': time.perf_counter() - started,
              'evidence_kind': 'real_pretrained_model_generated_arrays_not_accuracy'}
    with (output / 'export-provenance.json').open('x', encoding='utf-8') as handle:
        json.dump(record, handle, indent=2)
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
