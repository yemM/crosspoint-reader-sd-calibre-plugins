"""
Detect mounted CrossPoint SD cards.

A volume is identified as a CrossPoint SD card if it contains a
`.crosspoint/` directory at its root.
"""

import os
import sys


def find_crosspoint_mounts():
    """Return a list of absolute paths to CrossPoint SD card roots.

    Scans OS-appropriate volume mount points for the `.crosspoint/`
    directory signature. Returns an empty list if none are found.
    """
    candidates = _candidate_roots()
    return [root for root in candidates if _is_crosspoint(root)]


def _is_crosspoint(path):
    """Return True if *path* looks like a CrossPoint SD card root."""
    return os.path.isdir(os.path.join(path, '.crosspoint'))


def _candidate_roots():
    """Return all mounted volume root paths appropriate for the current OS."""
    if sys.platform == 'darwin':
        return _macos_candidates()
    if sys.platform.startswith('linux'):
        return _linux_candidates()
    if sys.platform == 'win32':
        return _windows_candidates()
    return []


def _macos_candidates():
    volumes_dir = '/Volumes'
    if not os.path.isdir(volumes_dir):
        return []
    return [
        os.path.join(volumes_dir, name)
        for name in os.listdir(volumes_dir)
        if os.path.isdir(os.path.join(volumes_dir, name))
    ]


def _linux_candidates():
    roots = []
    for base in ('/media', '/run/media'):
        if not os.path.isdir(base):
            continue
        for entry in os.listdir(base):
            entry_path = os.path.join(base, entry)
            if not os.path.isdir(entry_path):
                continue
            # /run/media/<username>/<volume>
            try:
                sub = os.listdir(entry_path)
            except PermissionError:
                continue
            if sub:
                for vol in sub:
                    roots.append(os.path.join(entry_path, vol))
            else:
                roots.append(entry_path)
    return roots


def _windows_candidates():
    import string
    roots = []
    for letter in string.ascii_uppercase:
        path = letter + ':\\'
        if os.path.isdir(path):
            roots.append(path)
    return roots
