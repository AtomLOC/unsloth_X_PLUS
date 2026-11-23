# SPDX-License-Identifier: AGPL-3.0-only
# Copyright 2026-present the Unsloth AI Inc. team. All rights reserved. See /studio/LICENSE.AGPL-3.0

"""check_dataset_format must describe a streaming dataset, not crash on it.

A stream with no features yet reports `column_names is None`, and `list(None)` raises
`TypeError: 'NoneType' object is not iterable` -- so the format check died before it
could report a format for exactly the shape streaming training produces.
"""

from datasets import Dataset, IterableDataset

from utils.datasets.dataset_utils import check_dataset_format

ROWS = [
    {"instruction": "Say hi", "input": "", "output": "Hi"},
    {"instruction": "Count", "input": "1 2", "output": "1, 2"},
]


def _stream(with_features: bool) -> IterableDataset:
    kwargs = {"features": Dataset.from_list(ROWS).features} if with_features else {}
    return IterableDataset.from_generator(lambda: iter(ROWS), **kwargs)


def test_streaming_dataset_without_features_is_described():
    dataset = _stream(with_features = False)
    assert dataset.column_names is None, "the case under test: a stream before any read"

    result = check_dataset_format(dataset)

    assert result["columns"] == ["instruction", "input", "output"]
    assert result["detected_format"] == "alpaca"
    assert result["requires_manual_mapping"] is False


def test_streaming_dataset_with_features_is_unchanged():
    result = check_dataset_format(_stream(with_features = True))

    assert result["columns"] == ["instruction", "input", "output"]
    assert result["detected_format"] == "alpaca"


def test_empty_stream_reports_no_columns():
    empty = IterableDataset.from_generator(lambda: iter(()))

    result = check_dataset_format(empty)

    assert result["columns"] == []
