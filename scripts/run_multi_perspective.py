#!/usr/bin/env python3
"""Run multi-perspective research against a question and print summary."""
from myai.aggregator import aggregate_question
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('question')
parser.add_argument('--max-iterations', type=int, default=6)
parser.add_argument('--min-confidence', type=int, default=8)
args = parser.parse_args()

res = aggregate_question(args.question, max_iterations=args.max_iterations, min_confidence=args.min_confidence)
print('Perspectives:', [p.get('id') if isinstance(p, dict) else p for p in res.perspectives])
print('Answers:', len(res.answers))
print('Merged sources:', len(res.merged_sources))
for s in res.merged_sources:
    print('-', s.title, s.url)
