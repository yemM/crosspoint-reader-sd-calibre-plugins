"""
Library identity of the books on a CrossPoint SD card.

upload_books copies the pristine library EPUB, so the OPF on the card keeps
whatever UUID and title the file had when it was added to Calibre.  Calibre
matches device books to the library by UUID, then by title + author, so a
title edited in Calibre without "Embed metadata" makes the book look absent.

This cache, kept at the card root, records the library UUID, title and authors
of each book Calibre sent or recognised, keyed by its card-relative path.
books() prefers it over the OPF while the file size is unchanged.

Pure module: no Calibre imports, so it can be unit-tested directly.
"""

import json
import os
import sys
import unicodedata

CACHE_NAME = '.crosspoint_calibre.json'
VERSION = 1


def cache_key(lpath):
    """Normalise a card-relative path: forward slashes, NFC (macOS walks may
    return NFD names), no leading slash."""
    return unicodedata.normalize('NFC', lpath.replace('\\', '/')).lstrip('/')


def _entry_ok(entry):
    return (
        isinstance(entry, dict)
        and isinstance(entry.get('uuid'), str) and entry['uuid']
        and isinstance(entry.get('size'), int)
        and isinstance(entry.get('title'), str)
        and isinstance(entry.get('authors'), list)
    )


def load_cache(sd_root):
    """Return {key: entry} from the card, or {} when absent or unreadable."""
    path = os.path.join(sd_root, CACHE_NAME)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        print(f'[CrossPoint] Ignoring unreadable {CACHE_NAME}: {exc}', file=sys.stderr)
        return {}
    if not isinstance(data, dict) or data.get('version') != VERSION:
        return {}
    books = data.get('books')
    if not isinstance(books, dict):
        return {}
    return {cache_key(k): v for k, v in books.items() if _entry_ok(v)}


def save_cache(sd_root, cache):
    """Write the cache atomically (temp file + rename). Returns True on success."""
    path = os.path.join(sd_root, CACHE_NAME)
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'version': VERSION, 'books': cache}, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, path)
        return True
    except OSError as exc:
        print(f'[CrossPoint] Could not write {CACHE_NAME}: {exc}', file=sys.stderr)
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


def make_entry(uuid, title, authors, size):
    return {'uuid': uuid, 'title': title or '', 'authors': list(authors or []), 'size': int(size)}


def lookup(cache, lpath, size):
    """Cached entry for *lpath* when the file still has the recorded size."""
    entry = cache.get(cache_key(lpath))
    if entry is not None and entry['size'] == size:
        return entry
    return None


def merge(cache, files, resolved):
    """Return the cache to store after a sync.

    files    -- {lpath: size} of the EPUBs actually on the card
    resolved -- {lpath: entry} for books the current library recognises

    A resolved entry wins.  Otherwise the previous entry survives while its
    file is unchanged, so books from another Calibre library keep their
    identity.  Entries for deleted or replaced files are dropped.
    """
    sizes = {cache_key(k): v for k, v in files.items()}
    out = {}
    for key, entry in cache.items():
        if sizes.get(key) == entry['size']:
            out[key] = entry
    for lpath, entry in resolved.items():
        key = cache_key(lpath)
        if key in sizes:
            out[key] = dict(entry, size=sizes[key])
    return out
