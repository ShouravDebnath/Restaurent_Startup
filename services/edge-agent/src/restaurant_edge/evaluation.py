"""Duration-weighted comparisons of explicitly labeled private intervals.

This calculates reports from supplied labels; it never invents ground truth,
opens footage, measures detector AP, or certifies restaurant accuracy.
"""

import math
from collections import defaultdict
from itertools import pairwise

STATES = {'UNKNOWN', 'AVAILABLE', 'OCCUPIED', 'RESET_PENDING', 'CLEANING', 'OUT_OF_SERVICE'}


def validate_intervals(rows):
    grouped = defaultdict(list)
    if len(rows) > 100_000:
        raise ValueError('Evaluation interval quota exceeded')
    for row in rows:
        if set(row) != {'table_id', 'start', 'end', 'state'} or row['state'] not in STATES:
            raise ValueError('Invalid labeled interval contract')
        start, end = row['start'], row['end']
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (start, end)) or not 0 <= start < end:
            raise ValueError('Invalid interval timing')
        grouped[row['table_id']].append(row)
    for intervals in grouped.values():
        intervals.sort(key=lambda r: r['start'])
        if any(a['end'] > b['start'] for a, b in pairwise(intervals)):
            raise ValueError('Overlapping intervals need independent review')
    return grouped


def evaluate_intervals(truth, predictions):
    expected, estimated = validate_intervals(truth), validate_intervals(predictions)
    if set(estimated) - set(expected):
        raise ValueError('Prediction table is outside the labeled scope')
    confusion = defaultdict(float)
    excluded = 0.0
    for key, intervals in expected.items():
        predicted = estimated.get(key, [])
        for interval in intervals:
            if interval['state'] == 'UNKNOWN':
                excluded += interval['end'] - interval['start']
                continue
            covered = 0.0
            for row in predicted:
                overlap = max(0, min(row['end'], interval['end']) - max(row['start'], interval['start']))
                if overlap:
                    confusion[(interval['state'], row['state'])] += overlap
                    covered += overlap
            # Missing prediction time is UNKNOWN, not vacant/correct by default.
            confusion[(interval['state'], 'UNKNOWN')] += interval['end'] - interval['start'] - covered
    total = sum(confusion.values())
    unknown = sum(seconds for (_, predicted), seconds in confusion.items() if predicted == 'UNKNOWN')
    correct = sum(seconds for (actual, predicted), seconds in confusion.items() if actual == predicted)
    def ratio(top, bottom):
        return top / bottom if bottom else None
    per_state = {}
    for state in sorted(STATES - {'UNKNOWN'}):
        tp = confusion[(state, state)]
        expected_seconds = sum(seconds for (actual, _), seconds in confusion.items() if actual == state)
        predicted_seconds = sum(seconds for (_, predicted), seconds in confusion.items() if predicted == state)
        per_state[state] = {'precision': ratio(tp, predicted_seconds), 'recall': ratio(tp, expected_seconds)}
    return {'labeled_known_seconds': total, 'excluded_unknown_truth_seconds': excluded,
            'unknown_fraction': ratio(unknown, total),
            'accuracy_all_labeled_time': ratio(correct, total),
            'accuracy_on_known_predictions': ratio(correct, total - unknown), 'per_state': per_state,
            'confusion_seconds': [{'actual': a, 'predicted': p, 'seconds': seconds}
                                  for (a, p), seconds in confusion.items() if seconds],
            'scope': 'Supplied interval comparison only; not detector AP or pilot validation.'}
