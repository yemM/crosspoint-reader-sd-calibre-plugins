"""Tests for book_bin_parser.py"""

import io
import struct

import pytest

from calibre_crosspoint.crosspoint.book_bin_parser import (
    parse_book_bin,
    BookMetadata,
    SpineEntry,
    BOOK_BIN_VERSION,
)
from tests.make_fixtures import build_book_bin


def write_book_bin(directory, title, author, spine_entries):
    import os
    data = build_book_bin(title, author, spine_entries)
    path = os.path.join(directory, 'book.bin')
    with open(path, 'wb') as f:
        f.write(data)
    return path


class TestParseBookBin:
    def test_parses_basic_metadata(self, tmp_path):
        spine = [('ch1.html', 0), ('ch2.html', 100)]
        write_book_bin(str(tmp_path), 'My Title', 'Some Author', spine)
        meta = parse_book_bin(str(tmp_path))
        assert meta is not None
        assert meta.title == 'My Title'
        assert meta.author == 'Some Author'
        assert meta.language == 'en'

    def test_parses_spine_entries(self, tmp_path):
        spine = [('ch1.html', 0), ('ch2.html', 50), ('ch3.html', 120)]
        write_book_bin(str(tmp_path), 'Book', 'Author', spine)
        meta = parse_book_bin(str(tmp_path))
        assert meta.spine_count == 3
        assert meta.spine_entries[0].href == 'ch1.html'
        assert meta.spine_entries[0].cumulative_size == 0
        assert meta.spine_entries[1].cumulative_size == 50
        assert meta.spine_entries[2].cumulative_size == 120

    def test_returns_none_when_file_absent(self, tmp_path):
        assert parse_book_bin(str(tmp_path)) is None

    def test_returns_none_for_empty_file(self, tmp_path):
        import os
        path = os.path.join(str(tmp_path), 'book.bin')
        with open(path, 'wb') as f:
            pass
        assert parse_book_bin(str(tmp_path)) is None

    def test_returns_none_for_truncated_file(self, tmp_path):
        import os
        path = os.path.join(str(tmp_path), 'book.bin')
        with open(path, 'wb') as f:
            f.write(b'\x05\x00\x00\x00')  # version + partial LUT offset
        assert parse_book_bin(str(tmp_path)) is None

    def test_single_spine_progress_is_zero(self, tmp_path):
        write_book_bin(str(tmp_path), 'B', 'A', [('ch1.html', 0)])
        meta = parse_book_bin(str(tmp_path))
        assert meta.progress_percent(0, 5) == 0.0

    def test_progress_percent_midpoint(self, tmp_path):
        spine = [(f'ch{i}.html', i * 100) for i in range(5)]
        write_book_bin(str(tmp_path), 'B', 'A', spine)
        meta = parse_book_bin(str(tmp_path))
        # spine_index=2, page_index=0 → cumulative=200 out of 400+
        pct = meta.progress_percent(2, 0)
        assert 40.0 <= pct <= 60.0

    def test_progress_clamps_to_100(self, tmp_path):
        spine = [('ch1.html', 0), ('ch2.html', 100)]
        write_book_bin(str(tmp_path), 'B', 'A', spine)
        meta = parse_book_bin(str(tmp_path))
        pct = meta.progress_percent(1, 99999)
        assert pct <= 100.0
