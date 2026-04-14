"""Tests for progress_reader.py"""

import os
import struct
import tempfile

import pytest

from calibre_crosspoint.crosspoint.progress_reader import read_progress


def write_progress_bin(directory, spine_index, page_index):
    path = os.path.join(directory, 'progress.bin')
    with open(path, 'wb') as f:
        f.write(struct.pack('<HH', spine_index, page_index))
    return path


class TestReadProgress:
    def test_reads_valid_4_byte_file(self, tmp_path):
        write_progress_bin(str(tmp_path), 2, 7)
        result = read_progress(str(tmp_path))
        assert result == {'spine_index': 2, 'page_index': 7}

    def test_returns_none_when_file_absent(self, tmp_path):
        assert read_progress(str(tmp_path)) is None

    def test_returns_none_for_truncated_file(self, tmp_path):
        path = os.path.join(str(tmp_path), 'progress.bin')
        with open(path, 'wb') as f:
            f.write(b'\x02\x00')  # only 2 bytes
        assert read_progress(str(tmp_path)) is None

    def test_handles_max_values(self, tmp_path):
        write_progress_bin(str(tmp_path), 65535, 65535)
        result = read_progress(str(tmp_path))
        assert result == {'spine_index': 65535, 'page_index': 65535}

    def test_handles_zero_progress(self, tmp_path):
        write_progress_bin(str(tmp_path), 0, 0)
        result = read_progress(str(tmp_path))
        assert result == {'spine_index': 0, 'page_index': 0}
