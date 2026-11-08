"""Arithmetic on fabricated labels, not an evaluated person-detection model."""

import pytest

from restaurant_edge.evaluation import evaluate_intervals


def interval(start, end, state, table='synthetic-table'):
    return {'table_id': table, 'start': start, 'end': end, 'state': state}


def test_duration_weighting_and_unknown_do_not_hide_errors():
    truth = [interval(0, 10, 'OCCUPIED'), interval(10, 20, 'RESET_PENDING')]
    predictions = [interval(0, 5, 'OCCUPIED'), interval(5, 15, 'UNKNOWN'), interval(15, 20, 'RESET_PENDING')]
    result = evaluate_intervals(truth, predictions)
    assert result['accuracy_all_labeled_time'] == .5
    assert result['accuracy_on_known_predictions'] == 1
    assert result['unknown_fraction'] == .5
    assert result['per_state']['OCCUPIED']['recall'] == .5


def test_missing_predictions_are_unknown_and_zero_denominators_are_null():
    result = evaluate_intervals([interval(0, 10, 'OCCUPIED')], [])
    assert result['unknown_fraction'] == 1 and result['accuracy_all_labeled_time'] == 0
    assert result['accuracy_on_known_predictions'] is None
    assert evaluate_intervals([], [])['accuracy_all_labeled_time'] is None


@pytest.mark.parametrize('rows', [[interval(0, 10, 'OCCUPIED'), interval(9, 11, 'AVAILABLE')],
                                 [interval(0, float('inf'), 'OCCUPIED')], [interval(2, 1, 'OCCUPIED')],
                                 [interval(0, 1, 'CLEAN_BY_AI')]])
def test_bad_or_overlapping_labels_are_rejected(rows):
    with pytest.raises(ValueError):
        evaluate_intervals(rows, [])


def test_foreign_prediction_table_is_rejected():
    with pytest.raises(ValueError):
        evaluate_intervals([interval(0, 10, 'OCCUPIED')], [interval(0, 10, 'OCCUPIED', 'foreign')])
