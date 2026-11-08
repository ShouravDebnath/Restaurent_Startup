"""Compare authorized private interval labels; never opens footage or downloads models."""

import argparse
import json
from pathlib import Path

from restaurant_edge.evaluation import evaluate_intervals

ROOT = Path(__file__).resolve().parents[1]


def private_path(value):
    path = Path(value).resolve()
    if not any(path.is_relative_to(ROOT / name) for name in ('.secrets', '.cache')):
        raise ValueError('Evaluation inputs/outputs must stay in private project directories')
    return path


def main():
    parser = argparse.ArgumentParser(description='Compare explicit private interval labels; no AI accuracy is assumed')
    parser.add_argument('--labels', required=True)
    parser.add_argument('--predictions', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        def read(path):
            if path.stat().st_size > 10_000_000:
                raise ValueError('Report exceeds quota')
            return json.loads(path.read_text(encoding='utf-8'))
        truth, predictions = read(private_path(args.labels)), read(private_path(args.predictions))
        fields = {'format_version', 'clock', 'clip_sha256', 'scope', 'evidence_kind', 'intervals'}
        if set(truth) != fields or set(predictions) != fields:
            raise ValueError('Explicit evaluation provenance required')
        if (truth['format_version'] != 1 or predictions['format_version'] != 1 or
            truth['clock'] != 'media_seconds' or predictions['clock'] != 'media_seconds' or
            truth['clip_sha256'] != predictions['clip_sha256'] or truth['scope'] != predictions['scope'] or
            truth['evidence_kind'] != 'synthetic_fixture' or predictions['evidence_kind'] != 'synthetic_fixture'):
            raise ValueError('Mismatched clock, footage scope or currently approved evidence kind')
        report = evaluate_intervals(truth['intervals'], predictions['intervals'])
        report.update({'evidence_kind': 'synthetic_fixture', 'clock': 'media_seconds',
                       'clip_sha256': truth['clip_sha256'], 'scope': truth['scope'],
                       'real_world_validation': False})
        output = private_path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
        print('Private interval comparison saved. Supplied synthetic labels do not establish real-world accuracy.')
    except (ValueError, OSError, TypeError, KeyError):
        parser.exit(1, 'Evaluation failed; check private schemas/provenance/paths. Existing output files are preserved.\n')


if __name__ == '__main__':
    main()
