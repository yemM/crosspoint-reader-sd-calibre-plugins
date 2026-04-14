"""
Read progress.bin from a CrossPoint cache directory.

progress.bin format (EPUB, 4 bytes, little-endian):
  0x00  uint16  spine_index  — current chapter (spine item index)
  0x02  uint16  page_index   — current page within that chapter
"""

import os
import struct


def read_progress(cache_dir):
    """Parse progress.bin from *cache_dir*.

    Returns a dict with keys ``spine_index`` and ``page_index``, or
    ``None`` if the file is absent or malformed.
    """
    path = os.path.join(cache_dir, 'progress.bin')
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except OSError:
        return None

    if len(data) < 4:
        return None

    spine_index, page_index = struct.unpack_from('<HH', data, 0)
    return {'spine_index': spine_index, 'page_index': page_index}
