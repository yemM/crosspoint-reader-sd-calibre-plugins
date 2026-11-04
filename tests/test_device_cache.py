"""Tests for device_cache.py"""

import json
import os
import unicodedata

from calibre_crosspoint.crosspoint import device_cache as dc


def entry(uuid='u1', title='T', authors=('A',), size=10):
    return dc.make_entry(uuid, title, authors, size)


class TestCacheKey:
    def test_backslashes_become_slashes(self):
        assert dc.cache_key('Author\\Book.epub') == 'Author/Book.epub'

    def test_leading_slash_stripped(self):
        assert dc.cache_key('/Author/Book.epub') == 'Author/Book.epub'

    def test_nfd_and_nfc_agree(self):
        nfd = unicodedata.normalize('NFD', 'Camille Lys/Club Privé.epub')
        assert dc.cache_key(nfd) == 'Camille Lys/Club Privé.epub'


class TestLoadSave:
    def test_missing_file_is_empty(self, tmp_path):
        assert dc.load_cache(str(tmp_path)) == {}

    def test_round_trip(self, tmp_path):
        cache = {'A/b.epub': entry()}
        assert dc.save_cache(str(tmp_path), cache)
        assert dc.load_cache(str(tmp_path)) == cache
        assert not os.path.exists(os.path.join(str(tmp_path), dc.CACHE_NAME + '.tmp'))

    def test_round_trip_non_ascii(self, tmp_path):
        cache = {'Camille Lys/Club Privé.epub': entry(title='Club Privé – Rituels')}
        dc.save_cache(str(tmp_path), cache)
        assert dc.load_cache(str(tmp_path)) == cache

    def test_corrupt_json_is_empty(self, tmp_path):
        (tmp_path / dc.CACHE_NAME).write_text('{not json')
        assert dc.load_cache(str(tmp_path)) == {}

    def test_other_version_is_empty(self, tmp_path):
        (tmp_path / dc.CACHE_NAME).write_text(json.dumps({'version': 99, 'books': {'a.epub': entry()}}))
        assert dc.load_cache(str(tmp_path)) == {}

    def test_malformed_entries_dropped(self, tmp_path):
        books = {
            'good.epub': entry(),
            'no_uuid.epub': dict(entry(), uuid=''),
            'bad_size.epub': dict(entry(), size='10'),
            'not_dict.epub': 'x',
        }
        (tmp_path / dc.CACHE_NAME).write_text(json.dumps({'version': dc.VERSION, 'books': books}))
        assert list(dc.load_cache(str(tmp_path))) == ['good.epub']

    def test_save_failure_returns_false(self, tmp_path):
        assert not dc.save_cache(str(tmp_path / 'missing_dir'), {})


class TestLookup:
    def test_hit_when_size_matches(self):
        cache = {'A/b.epub': entry(size=10)}
        assert dc.lookup(cache, 'A/b.epub', 10)['uuid'] == 'u1'

    def test_miss_when_size_changed(self):
        cache = {'A/b.epub': entry(size=10)}
        assert dc.lookup(cache, 'A/b.epub', 11) is None

    def test_miss_when_absent(self):
        assert dc.lookup({}, 'A/b.epub', 10) is None

    def test_normalises_path(self):
        cache = {'A/Privé.epub': entry()}
        assert dc.lookup(cache, unicodedata.normalize('NFD', 'A/Privé.epub'), 10) is not None


class TestMerge:
    def test_resolved_entry_takes_current_size(self):
        out = dc.merge({}, {'a.epub': 42}, {'a.epub': entry(size=0)})
        assert out == {'a.epub': entry(size=42)}

    def test_resolved_overrides_previous(self):
        out = dc.merge({'a.epub': entry(uuid='old')}, {'a.epub': 10}, {'a.epub': entry(uuid='new')})
        assert out['a.epub']['uuid'] == 'new'

    def test_unresolved_unchanged_file_kept(self):
        # A book from another Calibre library: not recognised now, still on the card.
        out = dc.merge({'a.epub': entry()}, {'a.epub': 10}, {})
        assert out == {'a.epub': entry()}

    def test_deleted_file_dropped(self):
        assert dc.merge({'a.epub': entry()}, {}, {}) == {}

    def test_replaced_file_dropped(self):
        assert dc.merge({'a.epub': entry(size=10)}, {'a.epub': 11}, {}) == {}

    def test_resolved_without_file_ignored(self):
        assert dc.merge({}, {}, {'a.epub': entry()}) == {}
