"""
Match books on the CrossPoint SD card to entries in the Calibre library.

Matching is done by normalized title + author comparison so that minor
punctuation/case differences don't cause missed matches.
"""

import re
import unicodedata


def normalize(s):
    """Return a canonical form of *s* suitable for fuzzy comparison.

    Steps:
      1. Unicode NFC normalization
      2. Lowercase
      3. Strip accents (NFD → drop combining marks)
      4. Remove all non-alphanumeric characters except spaces
      5. Collapse whitespace
    """
    if not s:
        return ''
    s = unicodedata.normalize('NFC', s)
    s = s.lower()
    # Decompose so we can strip combining characters
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    # Keep only letters, digits, spaces
    # Drop apostrophes/curly quotes entirely (so "it's" → "its").
    s = re.sub(r"['\u2018\u2019\u02bc]", '', s)
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def match_books(sd_books, calibre_books):
    """Match SD card books to Calibre library books.

    Parameters
    ----------
    sd_books:
        Iterable of dicts, each with keys ``title`` and ``author``
        (strings, from book.bin or EPUB metadata).
    calibre_books:
        Iterable of dicts, each with keys ``title``, ``author``, and
        ``calibre_id`` (the Calibre book ID integer).

    Returns
    -------
    list of (sd_book_dict, calibre_book_dict | None)
        Each SD book is paired with its matching Calibre entry, or
        ``None`` if no match was found.
    """
    # Build index: (norm_title, norm_author) → calibre_book
    index = {}
    for cb in calibre_books:
        key = _book_key(cb.get('title', ''), cb.get('author', ''))
        index[key] = cb

    results = []
    for sb in sd_books:
        key = _book_key(sb.get('title', ''), sb.get('author', ''))
        calibre_match = index.get(key)
        results.append((sb, calibre_match))
    return results


def _book_key(title, author):
    return (normalize(title), normalize(author))
