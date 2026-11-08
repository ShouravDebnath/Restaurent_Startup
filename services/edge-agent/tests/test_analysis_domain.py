"""SIMULATED boxes/clocks, not measured detector or restaurant accuracy."""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import numpy as np
import pytest
from pydantic import ValidationError

from restaurant_edge.analysis_config import AnalysisConfig, ConfigStore, Conflict
from restaurant_edge.association import Observation, associate, inside, valid_polygon
from restaurant_edge.detectors.base import Person
from restaurant_edge.detectors.onnx_detector import (
    ModelCatalog,
    ModelUnavailable,
    decode,
    preprocess,
)
from restaurant_edge.state_engine import StateEngine

SQUARE = [(.1, .1), (.8, .1), (.8, .8), (.1, .8)]
UTC = '2026-11-08T00:00:00+00:00'


def configuration(**kwargs):
    data = {'organization_id': str(uuid4()), 'location_id': str(uuid4()), 'camera_id': str(uuid4()),
            'source_width': 640, 'source_height': 360, 'regions': [
                {'table_id': str(uuid4()), 'zone_id': str(uuid4()), 'zone_revision': 7,
                 'seating': SQUARE, 'visibility_reviewed': True}]}
    data.update(kwargs)
    return AnalysisConfig.model_validate(data)


def observation(kind):
    return Observation(kind, 1 if kind == 'POSITIVE' else None, .9 if kind == 'POSITIVE' else None,
                       'HIGH' if kind == 'POSITIVE' else 'LOW', 'SIMULATED')


def feed(engine, kind, start, end, step=.5, generation='g'):
    for index in range(round((end - start) / step) + 1):
        now = start + index * step
        engine.step({key: observation(kind) for key in engine.tables}, now, UTC, generation, round(now * 100))


def table(engine):
    return next(iter(engine.tables.values()))


def manual(engine, state, revision=1, now=0):
    engine.manual([{'id': next(iter(engine.tables)), 'operational_revision': revision,
                    'current_state': state, 'state_source': 'manual', 'state_since': UTC}], now, UTC)


def test_arrival_departure_exact_boundaries_and_no_automatic_ready():
    e = StateEngine(configuration())
    feed(e, 'POSITIVE', 0, 9.5)
    assert table(e).state == 'UNKNOWN'
    feed(e, 'POSITIVE', 10, 10)
    assert table(e).state == 'OCCUPIED'
    feed(e, 'VACANT', 10.5, 35)
    assert table(e).state == 'OCCUPIED'
    feed(e, 'VACANT', 35.5, 60)
    assert table(e).state == 'RESET_PENDING'
    assert sum(r['reason'] == 'POSSIBLE_DEPARTURE' for r in e.events) == 1
    assert all(r['new_state'] != 'AVAILABLE' for r in e.events)


@pytest.mark.parametrize('kind', ['VACANT', 'UNCERTAIN'])
def test_initial_empty_or_uncertain_never_becomes_ready(kind):
    e = StateEngine(configuration())
    feed(e, kind, 0, 40)
    assert table(e).state == 'UNKNOWN'


@pytest.mark.parametrize('state', ['CLEANING', 'OUT_OF_SERVICE'])
@pytest.mark.parametrize('kind', ['POSITIVE', 'VACANT', 'UNCERTAIN'])
def test_manual_cleaning_and_blocks_survive_any_observation_and_failure(state, kind):
    e = StateEngine(configuration())
    manual(e, state)
    feed(e, kind, 0, 45)
    e.invalidate('SIMULATED_OUTAGE', 46, UTC)
    assert table(e).state == state and table(e).manual_since == UTC
    assert not table(e).verified


def test_ready_survives_outage_but_future_stable_arrival_is_allowed():
    e = StateEngine(configuration())
    manual(e, 'AVAILABLE')
    e.invalidate('OUTAGE', 0, UTC)
    assert table(e).state == 'AVAILABLE' and not table(e).verified
    feed(e, 'POSITIVE', 0, 10)
    assert table(e).state == 'OCCUPIED'


def test_brief_occlusion_holds_then_unknown_without_departure():
    e = StateEngine(configuration())
    feed(e, 'POSITIVE', 0, 10)
    feed(e, 'UNCERTAIN', 10.5, 12)
    assert table(e).state == 'OCCUPIED' and not table(e).verified
    feed(e, 'UNCERTAIN', 12.5, 15)
    assert table(e).state == 'UNKNOWN'
    assert not any(r['new_state'] == 'RESET_PENDING' for r in e.events)


def test_staff_crossing_and_missing_intervals_cannot_satisfy_arrival():
    e = StateEngine(configuration())
    feed(e, 'POSITIVE', 0, 3)
    feed(e, 'VACANT', 3.5, 20)
    assert table(e).state == 'UNKNOWN'
    feed(e, 'POSITIVE', 40, 40)
    feed(e, 'POSITIVE', 60, 60)
    assert table(e).state == 'UNKNOWN'


def test_outage_resume_reuses_context_without_duplicate_departure():
    e = StateEngine(configuration())
    feed(e, 'POSITIVE', 0, 10)
    session = table(e).session_id
    e.invalidate('OUTAGE', 11, UTC)
    feed(e, 'VACANT', 20, 45)
    assert table(e).state == 'RESET_PENDING' and table(e).session_id == session
    e.invalidate('OUTAGE', 46, UTC)
    feed(e, 'VACANT', 50, 75, generation='new')
    assert sum(r['reason'] == 'POSSIBLE_DEPARTURE' for r in e.events) == 1
    feed(e, 'POSITIVE', 75.5, 85.5, generation='new')
    assert table(e).state == 'OCCUPIED' and table(e).session_id != session


def test_duplicate_out_of_order_frames_do_not_advance_candidate():
    e = StateEngine(configuration())
    feed(e, 'POSITIVE', 0, 1)
    assert not e.step({k: observation('POSITIVE') for k in e.tables}, 20, UTC, 'g', 1)
    assert table(e).state == 'UNKNOWN'
    with pytest.raises(ValueError):
        e.step({}, -.5, UTC, 'g', 400)


def test_newer_manual_revision_wins_reopen_requires_fresh_evidence():
    e = StateEngine(configuration())
    manual(e, 'OUT_OF_SERVICE', 5)
    manual(e, 'AVAILABLE', 4)
    assert table(e).state == 'OUT_OF_SERVICE'
    manual(e, 'UNKNOWN', 6)
    feed(e, 'VACANT', 0, 40)
    assert table(e).state == 'UNKNOWN'


def test_restart_does_not_replay_inferred_readiness_or_old_timers():
    config = configuration()
    e = StateEngine(config)
    feed(e, 'POSITIVE', 0, 10)
    assert table(StateEngine(config)).state == 'UNKNOWN'
    assert table(StateEngine(config)).session_id is None


@pytest.mark.parametrize('score,expected', [(.9, 'POSITIVE'), (.5, 'UNCERTAIN'), (.1, 'UNCERTAIN')])
def test_scores_and_seating_association(score, expected):
    c = configuration()
    result = associate([Person((.2, .2, .4, .6), score)], c)
    assert next(iter(result.values())).kind == expected


def test_hysteresis_and_visibility_review_required():
    c = configuration()
    key = str(c.regions[0].table_id)
    person = Person((.2, .2, .4, .6), .5)
    assert associate([person], c, [key])[key].kind == 'POSITIVE'
    c.regions[0].visibility_reviewed = False
    assert associate([], c)[key].kind == 'UNCERTAIN'


def test_shared_polygons_and_near_boundaries_abstain_without_double_counting():
    c = configuration()
    other = c.regions[0].model_copy(update={'table_id': uuid4(), 'zone_id': uuid4()})
    c.regions.append(other)
    result = associate([Person((.2, .2, .4, .6), .9)], c)
    assert all(o.kind == 'UNCERTAIN' and o.count is None for o in result.values())
    c.regions.pop()
    result = associate([Person((.79, .2, .83, .6), .9)], c)
    assert next(iter(result.values())).kind == 'UNCERTAIN'


def test_exclusions_multiple_people_and_anchor_selection():
    c = configuration()
    people = [Person((.2, .2, .3, .4), .9), Person((.5, .2, .6, .4), .85)]
    assert next(iter(associate(people, c).values())).count == 2
    c.regions[0].exclusions = [SQUARE]
    assert next(iter(associate(people, c).values())).kind == 'UNCERTAIN'
    c.regions[0].exclusions = []
    c.regions[0].anchor = 'feet'
    assert next(iter(associate([Person((.2, .4, .3, .95), .9)], c).values())).kind == 'UNCERTAIN'


@pytest.mark.parametrize('polygon', [[], [(0, 0)] * 3, [(0, 0), (1, 1), (0, 1), (1, 0)],
                                     [(-.1, 0), (1, 0), (0, 1)], [(0, 0), (1, 0), (float('nan'), 1)]])
def test_invalid_geometry_is_rejected(polygon):
    assert not valid_polygon(polygon)


def test_concave_polygon_and_boundary_are_consistent():
    shape = [(0, 0), (1, 0), (1, .4), (.4, .4), (.4, 1), (0, 1)]
    assert valid_polygon(shape) and inside((.2, .8), shape)
    assert not inside((.8, .8), shape)
    assert inside((.4, .5), shape)


def test_config_history_idempotency_restart_and_scope(tmp_path):
    c, store, key = configuration(), ConfigStore(tmp_path), uuid4()
    scope = (c.organization_id, c.location_id, c.camera_id)
    record = store.save(c, 0, key, 'synthetic-actor')
    assert store.save(c, 0, key, 'synthetic-actor') == record
    assert ConfigStore(tmp_path).load(scope) == record
    assert store.load((uuid4(), c.location_id, c.camera_id)) is None
    original = next(tmp_path.rglob('000001.json')).read_bytes()
    c.regions[0].anchor = 'feet'
    with pytest.raises(Conflict):
        store.save(c, 0, key, 'synthetic-actor')
    store.save(c, 1, uuid4(), 'synthetic-actor')
    assert next(tmp_path.rglob('000001.json')).read_bytes() == original
    with pytest.raises(ValueError):
        store.load(('../escape', c.location_id, c.camera_id))


def test_concurrent_edit_has_one_winner(tmp_path):
    c, store = configuration(), ConfigStore(tmp_path)
    def save(_):
        try:
            store.save(c, 0, uuid4(), 'synthetic-actor')
            return 'saved'
        except Conflict:
            return 'conflict'
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(save, range(2))) == ['conflict', 'saved']


@pytest.mark.parametrize('field,value', [('settings', {'entry_score': .2, 'retention_score': .8}),
                                      ('source_width', 5000), ('model', 'https://unapproved.invalid/model')])
def test_strict_configuration_limits(field, value):
    with pytest.raises(ValidationError):
        configuration(**{field: value})


def test_preprocessing_preserves_bgr_range_upper_left_padding_and_scale():
    image = np.full((100, 200, 3), (10, 20, 30), dtype=np.uint8)
    tensor, ratio = preprocess(image)
    assert tensor.shape == (1, 3, 416, 416) and ratio == 2.08
    assert tensor[0, :, 0, 0].tolist() == [10, 20, 30]
    assert tensor[0, :, 415, 415].tolist() == [114] * 3


def test_decode_fake_tensor_geometry_score_product_and_nms():
    raw = np.zeros((1, 3549, 85), dtype=np.float32)
    raw[0, 0, :6] = [10, 10, np.log(10), np.log(10), .9, .8]
    people = decode(raw, 1, 416, 416)
    assert len(people) == 1 and people[0].score == pytest.approx(.72)
    assert people[0].box == pytest.approx((40 / 416, 40 / 416, 120 / 416, 120 / 416))
    raw[0, 1, :6] = [9, 10, np.log(10), np.log(10), .9, .8]
    assert len(decode(raw, 1, 416, 416)) == 1


@pytest.mark.parametrize('shape', [(1, 85, 3549), (1, 1, 85), (3549, 85)])
def test_wrong_output_contract_rejected(shape):
    with pytest.raises(ValueError):
        decode(np.zeros(shape), 1, 640, 360)


def test_empty_valid_result_and_nan_failure_are_different():
    raw = np.zeros((1, 3549, 85))
    assert decode(raw, 1, 640, 360) == ()
    raw[0, 1, 1] = np.nan
    with pytest.raises(ValueError):
        decode(raw, 1, 640, 360)


def test_unapproved_model_manifest_and_empty_catalog_fail_closed(tmp_path):
    with pytest.raises(ModelUnavailable):
        ModelCatalog().get('yolox_tiny')
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps({'format_version': 1, 'models': [{'id': 'yolox_tiny', 'license_status': 'pending'}]}))
    with pytest.raises(ModelUnavailable):
        ModelCatalog.load(path)


def test_installed_cpu_runtime_import_does_not_download_a_model():
    onnxruntime = pytest.importorskip('onnxruntime', reason='Optional AI runtime absent; required on the approved Phase 5 host')
    assert onnxruntime.__version__ == '1.31.1'
    assert 'CPUExecutionProvider' in onnxruntime.get_available_providers()


def test_sparse_samples_cannot_count_unobserved_time_as_stability():
    e = StateEngine(configuration())
    feed(e, 'POSITIVE', 0, 30, step=2)
    assert table(e).state == 'UNKNOWN'


def test_frame_captured_before_a_new_manual_command_is_ignored():
    e = StateEngine(configuration())
    manual(e, 'CLEANING', now=100)
    feed(e, 'POSITIVE', 0, 20)
    assert table(e).state == 'CLEANING' and table(e).count is None


def test_local_events_are_bounded_metadata_not_an_operational_outbox():
    e = StateEngine(configuration())
    key = next(iter(e.tables))
    for index in range(1100):
        e.change(key, 'UNKNOWN' if index % 2 else 'OCCUPIED', index, UTC, 'SIMULATED')
    assert len(e.events) == 1000
    assert all(row['source'] == 'ai_local_shadow' and not row['authoritative'] for row in e.events)
    assert all('pixels' not in row and 'box' not in row for row in e.events)
    assert all(row['camera_id'] == str(e.config.camera_id) and row['zone_revision'] == 7
               and row['config_fingerprint'] for row in e.events)
