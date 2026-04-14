"""Tests for metadata_matcher.py"""

import pytest

from calibre_crosspoint.calibre_sync.metadata_matcher import normalize, match_books


class TestNormalize:
    def test_lowercase(self):
        assert normalize('Hello World') == 'hello world'

    def test_strips_punctuation(self):
        assert normalize("It's a Test!") == 'its a test'

    def test_collapses_whitespace(self):
        assert normalize('  too   many   spaces  ') == 'too many spaces'

    def test_strips_accents(self):
        assert normalize('Ñoño') == 'nono'

    def test_empty_string(self):
        assert normalize('') == ''

    def test_none_like_empty(self):
        assert normalize(None) == ''


class TestMatchBooks:
    def _cal_book(self, book_id, title, author):
        return {'calibre_id': book_id, 'title': title, 'author': author}

    def _sd_book(self, title, author):
        return {'title': title, 'author': author}

    def test_exact_match(self):
        sd = [self._sd_book('Dune', 'Frank Herbert')]
        cal = [self._cal_book(1, 'Dune', 'Frank Herbert')]
        results = match_books(sd, cal)
        assert len(results) == 1
        assert results[0][1]['calibre_id'] == 1

    def test_case_insensitive_match(self):
        sd = [self._sd_book('dune', 'frank herbert')]
        cal = [self._cal_book(1, 'DUNE', 'FRANK HERBERT')]
        results = match_books(sd, cal)
        assert results[0][1] is not None

    def test_punctuation_insensitive(self):
        sd = [self._sd_book("The Hitchhiker's Guide", 'Douglas Adams')]
        cal = [self._cal_book(1, 'The Hitchhikers Guide', 'Douglas Adams')]
        results = match_books(sd, cal)
        assert results[0][1] is not None

    def test_no_match_returns_none(self):
        sd = [self._sd_book('Unknown Book', 'No One')]
        cal = [self._cal_book(1, 'Dune', 'Frank Herbert')]
        results = match_books(sd, cal)
        assert results[0][1] is None

    def test_multiple_books(self):
        sd = [
            self._sd_book('Book A', 'Author A'),
            self._sd_book('Book B', 'Author B'),
            self._sd_book('Book C', 'Author C'),
        ]
        cal = [
            self._cal_book(10, 'Book A', 'Author A'),
            self._cal_book(20, 'Book B', 'Author B'),
        ]
        results = match_books(sd, cal)
        assert results[0][1]['calibre_id'] == 10
        assert results[1][1]['calibre_id'] == 20
        assert results[2][1] is None

    def test_empty_inputs(self):
        assert match_books([], []) == []

    def test_author_mismatch_no_match(self):
        sd = [self._sd_book('Dune', 'Wrong Author')]
        cal = [self._cal_book(1, 'Dune', 'Frank Herbert')]
        results = match_books(sd, cal)
        assert results[0][1] is None
