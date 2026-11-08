"""Constructed tensors/arrays and simulated authorization; no accuracy evidence."""

import hashlib
import json
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pytest
from test_analysis_api import (
    lab as lab,  # noqa: PLC0414 - explicit pytest fixture re-export
)
from test_analysis_api import (
    save,
)

from restaurant_edge.detectors.factory import detector_for
from restaurant_edge.detectors.onnx_detector import ApprovedArtifact, ModelCatalog, ModelUnavailable
from restaurant_edge.detectors.rfdetr import MEAN, STD, RfDetrNano, decode, preprocess


def outputs():
    boxes = np.full((1, 300, 4), .5, dtype=np.float32)
    logits = np.full((1, 300, 91), -20, dtype=np.float32)
    return boxes, logits


def test_rgb_float_normalization_and_no_uint8_rounding():
    image = np.zeros((768, 768, 3), dtype=np.uint8)
    image[::2, :, :] = 255
    tensor = preprocess(image)
    expected = (.5 - MEAN) / STD
    assert tensor.shape == (1, 3, 384, 384) and tensor.dtype == np.float32
    assert np.allclose(tensor[0], expected[:, None, None], atol=1e-6)
    pixel = np.array([[[0, 128, 255]]], dtype=np.uint8)
    assert np.allclose(preprocess(pixel)[0, :, 0, 0], (np.array([1, 128 / 255, 0]) - MEAN) / STD)


@pytest.mark.parametrize('image', [np.zeros((0, 20, 3), dtype=np.uint8),
    np.zeros((20, 4097, 3), dtype=np.uint8), np.zeros((20, 20), dtype=np.uint8),
    np.zeros((20, 20, 4), dtype=np.uint8), np.zeros((20, 20, 3), dtype=np.float32)])
def test_invalid_frames_are_rejected(image):
    with pytest.raises(ValueError):
        preprocess(image)


def test_sparse_coco_person_is_one_and_transformer_boxes_are_not_nms_filtered():
    boxes, logits = outputs()
    logits[0, 0, 0], logits[0, 1, 90] = 10, 10
    logits[0, 2:4, 1] = 5
    people = decode(boxes, logits)
    assert len(people) == 2 and people[0].box == (.25, .25, .75, .75)
    assert .99 < people[0].score < 1  # Two overlapping query boxes are retained.


def test_global_query_class_topk_precedes_person_filtering():
    boxes, logits = outputs()
    logits[0, :, 2:4] = 10
    logits[0, 0, 1] = 5
    assert decode(boxes, logits) == ()


def test_empty_generated_logits_and_clipped_boxes():
    boxes, logits = outputs()
    assert decode(boxes, logits) == ()
    boxes[0, 0], logits[0, 0, 1] = [0, 0, 1, 1], 5
    assert decode(boxes, logits)[0].box == (0, 0, .5, .5)


@pytest.mark.parametrize('bad', ['nan_box', 'infinite_logit', 'negative_box', 'extreme_box', 'shape', 'dtype'])
def test_invalid_tensor_contracts_fail_closed(bad):
    boxes, logits = outputs()
    if bad == 'nan_box':
        boxes[0, 0, 0] = np.nan
    elif bad == 'infinite_logit':
        logits[0, 0, 1] = np.inf
    elif bad == 'negative_box':
        boxes[0, 0, 2] = -.1
    elif bad == 'extreme_box':
        boxes[0, 0, 2] = 9
    elif bad == 'shape':
        logits = logits[:, :, :80]
    else:
        boxes = boxes.astype(np.float64)
    with pytest.raises(ValueError):
        decode(boxes, logits)


def test_reparameterized_normalized_boxes_can_extend_beyond_image():
    boxes, logits = outputs()
    boxes[0, 0], logits[0, 0, 1] = [-.01, 1.01, 1.08, 1.03], 5
    result = decode(boxes, logits)
    assert len(result) == 1
    assert result[0].box[0] == 0 and result[0].box[3] == 1


def test_output_limit_reports_failure_instead_of_silently_trimming_a_crowd():
    boxes, logits = outputs()
    logits[0, :129, 1] = 5
    with pytest.raises(ValueError, match='limit'):
        decode(boxes, logits)


def manifest(tmp_path):
    file = tmp_path / 'generated-placeholder.onnx'
    file.write_bytes(b'not-model-weights' * 100)
    return {'format_version': 1, 'models': [{'id': 'rfdetr_nano', 'filename': file.name,
        'sha256': hashlib.sha256(file.read_bytes()).hexdigest(), 'license_status': 'cleared',
        'license_evidence': 'SIMULATED test approval; no actual graph', 'artifact_verified': True}]}


@pytest.mark.parametrize('change', ['wrong_hash', 'unknown_id', 'duplicate', 'unapproved', 'native', 'traversal'])
def test_catalog_rejects_integrity_approval_and_path_violations(tmp_path, change):
    data = manifest(tmp_path)
    entry = data['models'][0]
    if change == 'wrong_hash':
        entry['sha256'] = '0' * 64
    elif change == 'unknown_id':
        entry['id'] = 'arbitrary.module'
    elif change == 'duplicate':
        data['models'].append(entry.copy())
    elif change == 'unapproved':
        entry['artifact_verified'] = False
    elif change == 'native':
        file = tmp_path / 'generated.pth'
        file.write_bytes(b'placeholder')
        entry['filename'] = file.name
    else:
        file = tmp_path.parent / (uuid4().hex + '.onnx')
        file.write_bytes(b'placeholder')
        entry['filename'] = '../' + file.name
    path = tmp_path / 'catalog.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ModelUnavailable):
        ModelCatalog.load(path)


def test_catalog_preserves_explicit_model_identity(tmp_path):
    path = tmp_path / 'catalog.json'
    path.write_text(json.dumps(manifest(tmp_path)))
    artifact = ModelCatalog.load(path).get('rfdetr_nano')
    assert artifact.model_id == 'rfdetr_nano'


def test_artifact_has_model_specific_bounds_and_validated_digest(tmp_path):
    file = tmp_path / 'oversize.onnx'
    with file.open('wb') as handle:
        handle.seek(30_000_001)
        handle.write(b'!')
    with pytest.raises(ModelUnavailable, match='SIZE'):
        ApprovedArtifact(file, 'a' * 64, 'yolox_tiny').bytes()
    with pytest.raises(ModelUnavailable, match='INTEGRITY'):
        ApprovedArtifact(file, 'a' * 64, 'rfdetr_nano').bytes()
    with pytest.raises(ModelUnavailable, match='APPROVAL'):
        ApprovedArtifact(file, 'invalid', 'rfdetr_nano').bytes()


def test_adapter_uses_approved_bytes_cpu_provider_and_named_outputs(monkeypatch):
    import onnxruntime as ort
    boxes, logits = outputs()
    calls = []
    class Session:
        def __init__(self, data, **kwargs):
            calls.append((data, kwargs))
        def get_inputs(self):
            return [SimpleNamespace(name='input', shape=[1, 3, 384, 384], type='tensor(float)')]
        def get_outputs(self):
            return [SimpleNamespace(name='labels', shape=[1, 300, 91], type='tensor(float)'),
                    SimpleNamespace(name='dets', shape=[1, 300, 4], type='tensor(float)')]
        def run(self, names, feeds):
            assert names == ['dets', 'labels'] and feeds['input'].shape == (1, 3, 384, 384)
            return boxes, logits
    monkeypatch.setattr(ort, 'InferenceSession', Session)
    artifact = SimpleNamespace(model_id='rfdetr_nano', bytes=lambda: b'SIMULATED-GRAPH')
    model = RfDetrNano(artifact)
    assert model.detect(np.zeros((20, 30, 3), dtype=np.uint8)) == ()
    assert calls[0][1]['providers'] == ['CPUExecutionProvider']
    assert calls[0][1]['sess_options'].graph_optimization_level == ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    assert model.last_metrics['total_ms'] >= 0
    model.close()
    assert model.session is None


def test_unknown_factory_id_cannot_load_an_arbitrary_plugin():
    with pytest.raises(ModelUnavailable):
        detector_for(SimpleNamespace(model_id='arbitrary.module'))


def test_only_manager_can_switch_detector_without_changing_thresholds(lab):
    client, _, _, authority, headers, body, _ = lab
    assert save(client, headers, body).status_code == 200
    body['config']['model'] = 'rfdetr_nano'
    body['expected_revision'], body['request_key'] = 1, str(uuid4())
    authority.role = 'installer'
    assert save(client, headers, body).status_code == 403
    authority.role = 'manager'
    response = save(client, headers, body)
    assert response.status_code == 200 and response.json()['config']['model'] == 'rfdetr_nano'
    assert all(method == 'GET' for method, _ in authority.paths)
