"""
Parse book.bin from a CrossPoint cache directory.

book.bin format (version 5, all integers little-endian):

  Offset  Size   Field
  ------  -----  -----
  0x00    1      version byte (must be 5)
  0x01    4      LUT offset (uint32) — we skip via sequential reads
  0x05    4      spine_count (uint32)
  0x09    4      toc_count (uint32)
  0x0D    var    title         — length-prefixed UTF-8 string (uint32 len + bytes)
  ...     var    author        — length-prefixed UTF-8 string
  ...     var    language      — length-prefixed UTF-8 string
  ...     var    cover_href    — length-prefixed UTF-8 string
  ...     var    text_ref_href — length-prefixed UTF-8 string
  Then spine_count × SpineEntry:
    var   href              — length-prefixed UTF-8 string
    4     cumulative_size   — uint32 (cumulative page count before this chapter)
    2     toc_index         — int16 (–1 if none)
  Then toc_count × TocEntry (parsed but not returned by default)
"""

import os
import struct
from dataclasses import dataclass, field
from typing import List, Optional

BOOK_BIN_VERSION = 5


@dataclass
class SpineEntry:
    href: str
    cumulative_size: int  # cumulative page count before this chapter
    toc_index: int        # –1 if not linked to a TOC entry


@dataclass
class BookMetadata:
    title: str
    author: str
    language: str
    cover_href: str
    text_ref_href: str
    spine_entries: List[SpineEntry] = field(default_factory=list)

    @property
    def spine_count(self):
        return len(self.spine_entries)

    def progress_percent(self, spine_index, page_index):
        """Compute reading progress as a float in [0, 100].

        Uses cumulative page counts from spine entries when available.
        Falls back to spine_index / spine_count when cumulative data is
        incomplete (e.g. the last spine's total page count is unknown
        without reading sections/N.bin).
        """
        count = self.spine_count
        if count == 0:
            return 0.0

        if count == 1:
            return 0.0

        # If we have cumulative sizes, use them for a more accurate estimate.
        # The last spine entry's cumulative_size is pages before the last chapter;
        # we don't know that chapter's page count without sections/N.bin, so we
        # approximate total as cumulative_size[-1] + page_index_in_last_chapter.
        last_cum = self.spine_entries[-1].cumulative_size
        if last_cum > 0 and spine_index < count:
            current_cum = self.spine_entries[spine_index].cumulative_size
            absolute = current_cum + page_index
            # Rough total: pretend the last chapter has at least as many pages
            # as the deepest page we've seen (conservative lower bound).
            total = max(last_cum + page_index + 1, last_cum + 1)
            return min((absolute / total) * 100.0, 100.0)

        # Simple fallback: fraction of spine items completed.
        return (spine_index / max(count - 1, 1)) * 100.0


def parse_book_bin(cache_dir):
    """Parse book.bin from *cache_dir*.

    Returns a :class:`BookMetadata` instance, or ``None`` on any error
    (file missing, wrong version, truncated data, etc.).
    """
    path = os.path.join(cache_dir, 'book.bin')
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'rb') as f:
            return _parse(f)
    except Exception:
        return None


def _parse(f):
    # Version byte
    version_byte = f.read(1)
    if not version_byte:
        return None
    version = version_byte[0]
    if version != BOOK_BIN_VERSION:
        # Warn but attempt to continue; format may still be compatible.
        import sys
        print(
            f'[CrossPoint] book.bin version {version} != expected {BOOK_BIN_VERSION}',
            file=sys.stderr,
        )

    # LUT offset — read and discard; we parse sequentially.
    raw = f.read(4)
    if len(raw) < 4:
        return None
    # lut_offset = struct.unpack('<I', raw)[0]  # not used

    # Counts
    raw = f.read(8)
    if len(raw) < 8:
        return None
    spine_count, toc_count = struct.unpack('<II', raw)

    # Metadata strings
    title = _read_string(f)
    author = _read_string(f)
    language = _read_string(f)
    cover_href = _read_string(f)
    text_ref_href = _read_string(f)

    if None in (title, author, language, cover_href, text_ref_href):
        return None

    # Spine entries
    spine_entries = []
    for _ in range(spine_count):
        entry = _read_spine_entry(f)
        if entry is None:
            return None
        spine_entries.append(entry)

    return BookMetadata(
        title=title,
        author=author,
        language=language,
        cover_href=cover_href,
        text_ref_href=text_ref_href,
        spine_entries=spine_entries,
    )


def _read_string(f):
    """Read a uint32-length-prefixed UTF-8 string. Returns None on failure."""
    raw = f.read(4)
    if len(raw) < 4:
        return None
    length = struct.unpack('<I', raw)[0]
    if length == 0:
        return ''
    data = f.read(length)
    if len(data) < length:
        return None
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        return data.decode('utf-8', errors='replace')


def _read_spine_entry(f):
    """Read one SpineEntry. Returns None on failure."""
    href = _read_string(f)
    if href is None:
        return None
    raw = f.read(6)  # uint32 cumulative_size + int16 toc_index
    if len(raw) < 6:
        return None
    cumulative_size, toc_index = struct.unpack('<Ih', raw)
    return SpineEntry(href=href, cumulative_size=cumulative_size, toc_index=toc_index)
