"""
Write CrossPoint reading progress to Calibre custom columns.

Column labels are read from user preferences (config/prefs.py) so they
are configurable without touching code.  All writes are best-effort: if
a column does not exist the write is silently skipped.

Calibre API notes
-----------------
* Column creation  → db.new_api.create_custom_column(label, name, datatype, is_multiple)
* Existence check  → '#label' in db.new_api.field_metadata.custom_field_keys()
* Value write      → db.new_api.set_field('#label', {book_id: value})
* set_custom()     lives only on the OLD API (db); the new Cache API does NOT have it.
"""

import sys


# Column definitions: pref_key → (calibre_datatype, display_name)
_COLUMN_SPECS = {
    'col_progress': ('float', 'CrossPoint reading progress (%)'),
    'col_spine':    ('int',   'CrossPoint spine (chapter) index'),
    'col_page':     ('int',   'CrossPoint page index within chapter'),
}


def _get_prefs():
    """Return the prefs dict; falls back to DEFAULTS outside Calibre."""
    try:
        from ..config.prefs import prefs
        return prefs
    except ImportError:
        from ..config.prefs import DEFAULTS
        return DEFAULTS


def ensure_columns(db):
    """Create any missing CrossPoint custom columns if the user has opted in.

    Reads column labels and the auto-create flag from saved preferences.
    Silently skips columns that already exist.  Requires a Calibre restart
    for newly created columns to appear in the UI column chooser.
    """
    p = _get_prefs()
    if not p.get('auto_create_cols', True):
        return

    try:
        api = db.new_api if hasattr(db, 'new_api') else db
        existing = set(api.field_metadata.custom_field_keys())  # e.g. {'#cp_progress', ...}

        for pref_key, (datatype, display_name) in _COLUMN_SPECS.items():
            raw_label = p.get(pref_key, '').strip()
            label = raw_label.lstrip('#') if raw_label else pref_key.replace('col_', 'cp_')
            field_key = '#' + label

            if field_key not in existing:
                api.create_custom_column(
                    label=label,
                    name=display_name,
                    datatype=datatype,
                    is_multiple=False,
                )
                print(f'[CrossPoint] Created custom column {field_key}', file=sys.stderr)
            else:
                print(f'[CrossPoint] Column {field_key} already exists', file=sys.stderr)

    except Exception as exc:
        print(f'[CrossPoint] ensure_columns failed: {exc}', file=sys.stderr)


def write_progress(db, book_id, spine_index, page_index, progress_pct):
    """Write progress values to the configured Calibre custom columns.

    Uses the new Cache API (set_field) which is available in Calibre 6+.

    Parameters
    ----------
    db:
        Value returned by get_gui().current_db  (has .new_api attribute).
    book_id:
        Integer Calibre book ID.
    spine_index, page_index:
        Raw values from progress.bin.
    progress_pct:
        Overall progress as a float in [0, 100].
    """
    p = _get_prefs()
    api = db.new_api if hasattr(db, 'new_api') else db

    _set(api, book_id, p['col_progress'], round(float(progress_pct), 2))
    _set(api, book_id, p['col_spine'],    int(spine_index))
    _set(api, book_id, p['col_page'],     int(page_index))


def read_progress_from_calibre(db, book_id):
    """Read spine_index and page_index from Calibre custom columns.

    Returns ``{'spine_index': int, 'page_index': int}`` or ``None`` if
    either column is absent or has no value for this book.
    """
    p = _get_prefs()
    api = db.new_api if hasattr(db, 'new_api') else db
    spine_field = '#' + p.get('col_spine', 'cp_spine').lstrip('#')
    page_field  = '#' + p.get('col_page',  'cp_page' ).lstrip('#')
    try:
        spine = api.field_for(spine_field, book_id)
        page  = api.field_for(page_field,  book_id)
        if spine is not None and page is not None:
            return {'spine_index': int(spine), 'page_index': int(page)}
    except Exception as exc:
        print(f'[CrossPoint] Could not read progress columns: {exc}', file=sys.stderr)
    return None


def _set(api, book_id, label, value):
    """Write *value* to custom column *label* for *book_id* via the new API."""
    field_key = '#' + label.lstrip('#')
    try:
        api.set_field(field_key, {book_id: value})
        print(f'[CrossPoint] Wrote {field_key}={value!r} for book {book_id}', file=sys.stderr)
    except Exception as exc:
        print(
            f'[CrossPoint] Could not write {field_key} for book {book_id}: {exc}',
            file=sys.stderr,
        )
