"""Tests for book_list.py"""

import os

import pytest

from calibre_crosspoint.crosspoint.book_list import list_epubs


class TestListEpubs:
    def test_finds_epub_in_root(self, tmp_path):
        (tmp_path / 'book.epub').write_bytes(b'PK')
        result = list_epubs(str(tmp_path))
        assert len(result) == 1
        assert result[0]['path'].endswith('book.epub')

    def test_finds_epub_in_subdirectory(self, tmp_path):
        subdir = tmp_path / 'subdir'
        subdir.mkdir()
        (subdir / 'nested.epub').write_bytes(b'PK')
        result = list_epubs(str(tmp_path))
        assert len(result) == 1

    def test_skips_hidden_directories(self, tmp_path):
        hidden = tmp_path / '.crosspoint' / 'epub_123'
        hidden.mkdir(parents=True)
        (hidden / 'secret.epub').write_bytes(b'PK')
        result = list_epubs(str(tmp_path))
        assert result == []

    def test_skips_non_epub_files(self, tmp_path):
        (tmp_path / 'readme.txt').write_text('hello')
        (tmp_path / 'book.pdf').write_bytes(b'%PDF')
        result = list_epubs(str(tmp_path))
        assert result == []

    def test_case_insensitive_extension(self, tmp_path):
        (tmp_path / 'UPPERCASE.EPUB').write_bytes(b'PK')
        result = list_epubs(str(tmp_path))
        assert len(result) == 1

    def test_returns_size_and_mtime(self, tmp_path):
        (tmp_path / 'book.epub').write_bytes(b'PK\x03\x04')
        result = list_epubs(str(tmp_path))
        assert result[0]['size'] == 4
        assert result[0]['mtime'] > 0

    def test_empty_directory(self, tmp_path):
        assert list_epubs(str(tmp_path)) == []

    def test_multiple_epubs(self, tmp_path):
        for i in range(3):
            (tmp_path / f'book{i}.epub').write_bytes(b'PK')
        result = list_epubs(str(tmp_path))
        assert len(result) == 3
