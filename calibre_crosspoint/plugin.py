"""
CrossPointDevice — Calibre DevicePlugin implementation.

Detection strategy
------------------
Because the Xteink X4 does NOT expose USB mass storage, we cannot match
on a USB vendor/product ID.  Instead we use MANAGES_DEVICE_PRESENCE = True
and implement detect_managed_devices() to scan mounted volumes for the
.crosspoint/ directory signature.

Sync flow
---------
1. detect_managed_devices()  — called repeatedly by Calibre; returns device
                               handle when a CrossPoint SD is mounted.
2. open()                    — stores the SD root path.
3. books()                   — enumerates EPUBs present on the SD card.
4. upload_books()            — copies EPUBs from Calibre to SD root.
5. delete_books()            — removes EPUBs from SD card.
6. sync_booklists()          — reads progress.bin / book.bin and writes
                               progress back to Calibre custom columns.
"""

import hashlib
import os
import shutil
import sys
import time

from calibre.devices.interface import DevicePlugin
from calibre.devices.usbms.books import BookList, Book

from .crosspoint.detector import find_crosspoint_mounts
from .crosspoint.book_list import list_epubs
from .crosspoint.progress_reader import read_progress
from .crosspoint.book_bin_parser import parse_book_bin
from .calibre_sync.metadata_matcher import match_books
from .calibre_sync.custom_columns import write_progress, ensure_columns
from .config.settings_widget import ConfigWidget


class CrossPointDevice(DevicePlugin):
    # ------------------------------------------------------------------
    # Plugin identity
    # ------------------------------------------------------------------
    name = 'CrossPoint SD Device'
    description = (
        'Sync books and reading progress with a CrossPoint e-reader '
        'via SD card (Xteink X4 / CrossPoint firmware).'
    )
    author = 'CrossPoint Plugin'
    version = (0, 2, 0)
    minimum_calibre_version = (6, 0, 0)
    supported_platforms = ['windows', 'osx', 'linux']

    # ------------------------------------------------------------------
    # Device capabilities
    # ------------------------------------------------------------------
    FORMATS = ['epub']
    MANAGES_DEVICE_PRESENCE = True
    CAN_SET_METADATA = []

    # Fake USB IDs — required by DevicePlugin even when not used.
    VENDOR_ID = [0x0000]
    PRODUCT_ID = [0x0000]
    BCD = [0x0000]

    # ------------------------------------------------------------------
    # Internal state
    # ------------------------------------------------------------------
    _sd_root = None          # Absolute path to the mounted SD card
    _prompt_sync = False     # Trigger sync-prompt on next books() call

    # ------------------------------------------------------------------
    # Device presence (MANAGES_DEVICE_PRESENCE = True)
    # ------------------------------------------------------------------

    def detect_managed_devices(self, devices_on_system, force_refresh=False):
        """Scan mounted volumes for a CrossPoint SD card.

        Called periodically by Calibre.  Returns a non-None handle when a
        CrossPoint SD is detected, None otherwise.
        """
        mounts = find_crosspoint_mounts()
        if mounts:
            return mounts[0]  # Use the first CrossPoint volume found
        return None

    def debug_managed_device_detection(self, devices_on_system, output):
        mounts = find_crosspoint_mounts()
        output.append(f'CrossPoint mounts found: {mounts}')

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def open(self, connected_device, library_uuid):
        """Store the SD card root path after Calibre detects the device."""
        self._sd_root = connected_device  # detect_managed_devices returns the path
        self._prompt_sync = True
        print(f'[CrossPoint] Opened SD card at: {self._sd_root}', file=sys.stderr)
        db = _get_library_db()
        if db is not None:
            ensure_columns(db)

    def eject(self):
        self._sd_root = None

    def post_yank_cleanup(self):
        self._sd_root = None

    # ------------------------------------------------------------------
    # Device settings (required by Calibre before sending books)
    # ------------------------------------------------------------------

    def settings(self):
        """Return an OptionValues object describing device capabilities.

        Calibre calls this before transferring books to learn the
        preferred format order and other device options.
        """
        from calibre.utils.config_base import OptionValues
        s = OptionValues()
        s.format_map = ['epub']
        s.use_subdirs = False
        s.read_metadata = False
        s.use_author_sort = False
        s.save_template = '{title}'
        s.extra_customization = []
        return s

    # ------------------------------------------------------------------
    # Device information
    # ------------------------------------------------------------------

    def get_device_information(self, end_session=True):
        return ('CrossPoint SD', '1.0', '1.0', 'application/epub+zip')

    def get_device_uid(self):
        if self._sd_root:
            return f'crosspoint:{self._sd_root}'
        return 'crosspoint:unknown'

    def card_prefix(self, end_session=True):
        return (None, None)

    def set_progress_reporter(self, report_progress):
        self._report_progress = report_progress

    def reset(self, key=None, log_packets=False, report_progress=None, detected_device=None):
        self._sd_root = None

    def free_space(self, end_session=True):
        if self._sd_root:
            try:
                stat = shutil.disk_usage(self._sd_root)
                return [stat.free, -1, -1]
            except Exception:
                pass
        return [-1, -1, -1]

    def total_space(self, end_session=True):
        if self._sd_root:
            try:
                stat = shutil.disk_usage(self._sd_root)
                return [stat.total, -1, -1]
            except Exception:
                pass
        return [-1, -1, -1]

    # ------------------------------------------------------------------
    # Book enumeration
    # ------------------------------------------------------------------

    def books(self, oncard=None, end_session=True):
        """Return a BookList of all EPUBs on the SD card (main storage only).

        Reads EPUB metadata (including the Calibre-embedded UUID) from each
        file so Calibre can match device books to library entries across
        reconnects.
        """
        bl = BookList(None, None, None)
        if self._sd_root is None or oncard is not None:
            return bl

        from calibre.ebooks.metadata.epub import get_metadata

        epub_list = list_epubs(self._sd_root)
        for i, entry in enumerate(epub_list):
            rel_path = os.path.relpath(entry['path'], self._sd_root)

            # Read EPUB metadata so Calibre can match this book to the library.
            mi = None
            try:
                with open(entry['path'], 'rb') as f:
                    mi = get_metadata(f, extract_cover=False)
            except Exception as exc:
                print(f"[CrossPoint] Could not read metadata from {entry['path']}: {exc}",
                      file=sys.stderr)

            book = Book(self._sd_root, rel_path, size=entry['size'], other=mi)
            book.path = entry['path']
            book.datetime = time.gmtime(entry['mtime'])

            # Fall back to filename if EPUB has no title
            if not book.title:
                book.title = os.path.splitext(os.path.basename(entry['path']))[0]
            if not book.authors:
                book.authors = ['Unknown']

            bl.append(book)

        if self._prompt_sync:
            self._prompt_sync = False
            self._maybe_sync_on_connect()

        return bl

    # ------------------------------------------------------------------
    # Book transfer
    # ------------------------------------------------------------------

    def upload_books(self, files, names, on_card=None, end_session=True, metadata=None):
        """Copy EPUB files from Calibre into per-author folders on the SD card.

        Each book is placed at <sd_root>/<author>/<filename>.epub.
        Returns a list of (absolute_dest_path, on_card) 2-tuples, which
        Calibre passes directly to add_books_to_metadata.
        """
        if self._sd_root is None:
            return []
        metadata = list(metadata) if metadata else [None] * len(files)
        results = []
        for src, name, mi in zip(files, names, metadata):
            # Use the original EPUB from the Calibre library rather than
            # the temp file Calibre prepared (which has UUID, cover pages,
            # and OPF changes injected that CrossPoint's parser can't handle).
            actual_src = _original_epub_path(mi)
            if actual_src is None:
                print(
                    f'[CrossPoint] WARNING: could not locate original EPUB for "{name}"; '
                    'falling back to Calibre temp file — CrossPoint may fail to open this book.',
                    file=sys.stderr,
                )
                actual_src = src

            src_size = os.path.getsize(actual_src)
            tmp_size = os.path.getsize(src)
            using = 'library' if actual_src != src else 'temp'
            src_md5 = _md5(actual_src)
            print(
                f'[CrossPoint] src={actual_src} ({src_size} bytes, md5={src_md5}, from {using}); '
                f'calibre tmp={src} ({tmp_size} bytes)',
                file=sys.stderr,
            )

            author = _safe_dirname(mi.authors[0] if mi and mi.authors else 'Unknown')
            author_dir = os.path.join(self._sd_root, author)
            os.makedirs(author_dir, exist_ok=True)
            dest = os.path.join(author_dir, name)
            shutil.copyfile(actual_src, dest)  # copyfile = bytes only; copy2 fails on FAT32/exFAT
            dest_md5 = _md5(dest)
            print(
                f'[CrossPoint] dest={dest} md5={dest_md5} '
                f'({"OK - matches source" if dest_md5 == src_md5 else "MISMATCH - copy may be corrupt"})',
                file=sys.stderr,
            )
            results.append((dest, on_card))
            print(f'[CrossPoint] Uploaded: {author}/{name} ({src_size} bytes)', file=sys.stderr)
        return results

    @classmethod
    def add_books_to_metadata(cls, locations, metadata, booklists):
        """Add newly uploaded books to Calibre's device book list.

        Called by Calibre immediately after upload_books, without device
        communication.  locations is the list returned by upload_books.
        """
        for location, meta in zip(locations, metadata):
            abs_path, on_card = location
            blist_idx = 2 if on_card == 'cardb' else 1 if on_card == 'carda' else 0
            booklist = booklists[blist_idx]

            # Derive lpath (path relative to device root) from the absolute path.
            # We use the book's path attribute on the existing list to find the
            # prefix, falling back to the dirname of the first existing book.
            prefix = None
            for book in booklist:
                bp = getattr(book, 'path', '')
                lp = getattr(book, 'lpath', '')
                if bp and lp and bp.endswith(lp):
                    prefix = bp[: len(bp) - len(lp)]
                    break

            if prefix and abs_path.startswith(prefix):
                lpath = abs_path[len(prefix):]
            else:
                lpath = os.path.basename(abs_path)

            lpath = lpath.lstrip('/')

            try:
                size = os.path.getsize(abs_path)
            except OSError:
                size = 0

            # Build a Book from the Calibre Metadata object so title/author
            # are populated correctly.
            book = Book(prefix or os.path.dirname(abs_path), lpath,
                        size=size, other=meta)
            book.path = abs_path
            book.datetime = time.gmtime()
            booklist.add_book(book, replace_metadata=True)

    @classmethod
    def remove_books_from_metadata(cls, paths, booklists):
        """Remove deleted books from Calibre's device book list.

        Called by Calibre immediately after delete_books, without device
        communication.
        """
        for path in paths:
            for booklist in booklists:
                for book in list(booklist):
                    if getattr(book, 'path', '') == path or \
                       getattr(book, 'lpath', '') == path or \
                       path.endswith(getattr(book, 'lpath', '\x00')):
                        booklist.remove_book(book)
                        break

    def delete_books(self, paths, end_session=True):
        """Delete EPUB files from the SD card."""
        for path in paths:
            if not os.path.isabs(path) and self._sd_root:
                path = os.path.join(self._sd_root, path)
            try:
                os.remove(path)
                print(f'[CrossPoint] Deleted: {path}', file=sys.stderr)
            except Exception as exc:
                print(f'[CrossPoint] Delete failed for {path}: {exc}', file=sys.stderr)

    # ------------------------------------------------------------------
    # Metadata sync (progress read-back)
    # ------------------------------------------------------------------

    def sync_booklists(self, booklists, end_session=True):
        """Read progress from SD card and write it to Calibre custom columns.

        booklists is a 3-tuple: (main_bl, carda_bl, cardb_bl).
        We only use main_bl (index 0).
        """
        if self._sd_root is None:
            return
        db = _get_library_db()
        if db is None:
            print('[CrossPoint] sync_booklists: could not reach library DB', file=sys.stderr)
            return
        matched, unmatched = self._perform_sync(db)
        print(
            f'[CrossPoint] Sync complete: {matched} matched, {unmatched} unmatched',
            file=sys.stderr,
        )

    def _perform_sync(self, db):
        """Read SD progress, match to library, write columns. Returns (matched, unmatched)."""
        crosspoint_dir = os.path.join(self._sd_root, '.crosspoint')
        if not os.path.isdir(crosspoint_dir):
            return 0, 0

        cache_dirs = [
            os.path.join(crosspoint_dir, d)
            for d in os.listdir(crosspoint_dir)
            if d.startswith('epub_') and os.path.isdir(os.path.join(crosspoint_dir, d))
        ]
        print(f'[CrossPoint] _perform_sync: {len(cache_dirs)} epub cache dir(s)', file=sys.stderr)

        sd_books = []
        for cache_dir in cache_dirs:
            meta = parse_book_bin(cache_dir)
            if meta is None:
                continue
            sd_books.append({
                'title': meta.title,
                'author': meta.author,
                'cache_dir': cache_dir,
                'meta': meta,
                'progress': read_progress(cache_dir),
            })

        calibre_books = _get_calibre_books(db)
        matched = 0
        unmatched = 0
        for sd_book, cal_book in match_books(sd_books, calibre_books):
            if cal_book is None:
                unmatched += 1
                print(
                    f"[CrossPoint] No Calibre match for: {sd_book['title']} "
                    f"by {sd_book['author']}",
                    file=sys.stderr,
                )
                continue

            progress = sd_book.get('progress')
            if progress is None:
                continue  # Book was never opened — skip

            meta = sd_book['meta']
            spine_index = progress['spine_index']
            page_index = progress['page_index']
            progress_pct = meta.progress_percent(spine_index, page_index)

            write_progress(db, cal_book['calibre_id'], spine_index, page_index, progress_pct)
            matched += 1
            print(
                f"[CrossPoint] Synced: {sd_book['title']} → {progress_pct:.1f}%",
                file=sys.stderr,
            )

        try:
            api = db.new_api if hasattr(db, 'new_api') else db
            api.commit()
        except Exception:
            pass

        return matched, unmatched

    def _has_progress_data(self):
        """Return True if at least one epub_* cache dir contains a progress.bin."""
        if self._sd_root is None:
            return False
        crosspoint_dir = os.path.join(self._sd_root, '.crosspoint')
        if not os.path.isdir(crosspoint_dir):
            return False
        try:
            for d in os.listdir(crosspoint_dir):
                if d.startswith('epub_') and os.path.isfile(
                    os.path.join(crosspoint_dir, d, 'progress.bin')
                ):
                    return True
        except OSError:
            pass
        return False

    def _maybe_sync_on_connect(self):
        """If progress data exists on SD, ask user and optionally sync. Runs in device thread."""
        if not self._has_progress_data():
            return
        try:
            from .ui.sync_prompt import ask_sync_prompt
        except Exception as exc:
            print(f'[CrossPoint] sync_prompt import failed: {exc}', file=sys.stderr)
            return
        if not ask_sync_prompt():
            return
        db = _get_library_db()
        if db is None:
            return
        matched, unmatched = self._perform_sync(db)
        print(
            f'[CrossPoint] On-connect sync: {matched} matched, {unmatched} unmatched',
            file=sys.stderr,
        )

    # ------------------------------------------------------------------
    # Plugin configuration UI
    # ------------------------------------------------------------------

    def customization_help(self, gui=False):
        """Return a non-empty string so Calibre enables 'Customize plugin'."""
        return 'Configure CrossPoint SD column mappings and sync options.'

    def config_widget(self):
        """Return the configuration widget shown in 'Customize plugin'."""
        return ConfigWidget()

    def save_settings(self, widget):
        """Persist settings after the user clicks OK in the config dialog."""
        widget.commit()

    def startup(self):
        pass

    def shutdown(self):
        pass

    # ------------------------------------------------------------------
    # is_usb_connected (required by interface; never triggers for us
    # because MANAGES_DEVICE_PRESENCE = True, but must not raise)
    # ------------------------------------------------------------------

    def is_usb_connected(self, devices_on_system, debug=False, only_presence=False):
        return False, None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _original_epub_path(mi):
    """Return the absolute path to the original EPUB in the Calibre library.

    Calibre modifies a temp copy of the EPUB before passing it to
    upload_books (injecting UUID, cover pages, OPF changes).  CrossPoint's
    parser rejects those modifications, so we bypass the temp file and copy
    the pristine original from the library instead.

    Returns None if the path cannot be determined (fallback to temp file).
    """
    try:
        book_id = getattr(mi, 'application_id', None)
        if not book_id:
            return None
        db = _get_library_db()
        if db is None:
            return None
        api = db.new_api if hasattr(db, 'new_api') else db
        path = api.format_abspath(book_id, 'EPUB')
        if path and os.path.isfile(path):
            return path
    except Exception as exc:
        print(f'[CrossPoint] Could not resolve original EPUB path: {exc}', file=sys.stderr)
    return None


def _get_library_db():
    """Return the current Calibre library DB by reaching into the running GUI.

    Device plugin methods run inside the Calibre process, so get_gui() gives
    us the main window and its database without needing an explicit reference
    to be passed in.  Returns None when running outside the GUI (e.g. tests).
    """
    try:
        from calibre.gui2.ui import get_gui
        gui = get_gui()
        if gui is not None:
            return gui.current_db
    except Exception as exc:
        print(f'[CrossPoint] Could not get library DB: {exc}', file=sys.stderr)
    return None


def _md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _safe_dirname(name):
    """Return a filesystem-safe version of *name* for use as a directory name.

    Strips or replaces characters that are illegal on macOS, Windows, or Linux.
    """
    import re
    # Replace path separators and null bytes
    name = re.sub(r'[/\\:\*\?"<>\|]', '_', name)
    # Strip leading/trailing dots and spaces (Windows dislikes them)
    name = name.strip('. ')
    return name or 'Unknown'


def _get_calibre_books(db):
    """Return a list of dicts with keys title, author, calibre_id."""
    results = []
    try:
        api = db.new_api if hasattr(db, 'new_api') else db
        ids = api.all_book_ids()
        fields = api.all_field_for('title', ids), api.all_field_for('authors', ids)
        titles, authors_map = fields
        for book_id in ids:
            title = titles.get(book_id, '')
            authors = authors_map.get(book_id, [])
            author = authors[0] if authors else ''
            results.append({
                'calibre_id': book_id,
                'title': title,
                'author': author,
            })
    except Exception as exc:
        print(f'[CrossPoint] Could not read Calibre library: {exc}', file=sys.stderr)
    return results
