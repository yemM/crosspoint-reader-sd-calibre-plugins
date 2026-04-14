"""
Enumerate EPUB files on a CrossPoint SD card.
"""

import os


def list_epubs(sd_root):
    """Return a list of dicts describing every EPUB on the SD card.

    Each dict has keys:
      path  — absolute filesystem path to the EPUB
      size  — file size in bytes
      mtime — modification time as a float (seconds since epoch)

    Hidden directories (names starting with '.') are skipped so that the
    .crosspoint/ cache directory is never traversed.
    """
    results = []
    for dirpath, dirnames, filenames in os.walk(sd_root):
        # Skip hidden directories in-place so os.walk won't recurse into them.
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for name in filenames:
            if name.lower().endswith('.epub') and not name.startswith('._'):
                full = os.path.join(dirpath, name)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                results.append({
                    'path': full,
                    'size': st.st_size,
                    'mtime': st.st_mtime,
                })
    return results
