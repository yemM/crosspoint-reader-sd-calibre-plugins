"""
Configuration widget for the CrossPoint SD plugin.

Calibre displays this widget under Preferences → Plugins when the user
clicks "Customize plugin".  It must implement:

  genesis()  — populate controls from saved prefs
  commit()   — validate and save controls back to prefs

The widget is a plain QWidget; Calibre wraps it in its own dialog.
"""

from qt.core import (
    QWidget, QFormLayout, QLineEdit, QCheckBox,
    QLabel, QVBoxLayout, Qt,
)

from .prefs import prefs, DEFAULTS


class ConfigWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        # ── Description ──────────────────────────────────────────────
        desc = QLabel(
            'Enter the Calibre custom column <b>labels</b> (without the '
            'leading <code>#</code>) that CrossPoint should write to when '
            'syncing reading progress from the SD card.'
        )
        desc.setWordWrap(True)
        outer.addWidget(desc)

        # ── Column name fields ────────────────────────────────────────
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        outer.addLayout(form)

        self._progress_edit = QLineEdit()
        self._progress_edit.setPlaceholderText(DEFAULTS['col_progress'])
        form.addRow(
            '<b>#</b>Progress column&nbsp;'
            '<small>(float 0–100)</small>',
            self._progress_edit,
        )

        self._spine_edit = QLineEdit()
        self._spine_edit.setPlaceholderText(DEFAULTS['col_spine'])
        form.addRow(
            '<b>#</b>Chapter column&nbsp;'
            '<small>(integer)</small>',
            self._spine_edit,
        )

        self._page_edit = QLineEdit()
        self._page_edit.setPlaceholderText(DEFAULTS['col_page'])
        form.addRow(
            '<b>#</b>Page column&nbsp;'
            '<small>(integer)</small>',
            self._page_edit,
        )

        # ── Auto-create toggle ────────────────────────────────────────
        self._auto_create = QCheckBox(
            'Auto-create missing columns when the SD card is connected'
        )
        outer.addWidget(self._auto_create)

        outer.addStretch()
        self.genesis()

    # ------------------------------------------------------------------
    # Calibre lifecycle
    # ------------------------------------------------------------------

    def genesis(self):
        """Populate controls from saved preferences."""
        self._progress_edit.setText(prefs['col_progress'])
        self._spine_edit.setText(prefs['col_spine'])
        self._page_edit.setText(prefs['col_page'])
        self._auto_create.setChecked(prefs['auto_create_cols'])

    def commit(self):
        """Validate inputs and save to preferences.

        Returns a human-readable error string if validation fails, or
        an empty string on success (Calibre convention).
        """
        progress = self._progress_edit.text().strip().lstrip('#')
        spine    = self._spine_edit.text().strip().lstrip('#')
        page     = self._page_edit.text().strip().lstrip('#')

        # Fall back to defaults when left blank
        progress = progress or DEFAULTS['col_progress']
        spine    = spine    or DEFAULTS['col_spine']
        page     = page     or DEFAULTS['col_page']

        error = _validate_label(progress, 'Progress')
        if error:
            return error
        error = _validate_label(spine, 'Chapter')
        if error:
            return error
        error = _validate_label(page, 'Page')
        if error:
            return error

        prefs['col_progress']    = progress
        prefs['col_spine']       = spine
        prefs['col_page']        = page
        prefs['auto_create_cols'] = self._auto_create.isChecked()
        return ''


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

import re as _re

_LABEL_RE = _re.compile(r'^[a-z][a-z0-9_]{0,58}$')


def _validate_label(label, field_name):
    """Return an error string if *label* is not a valid Calibre column label."""
    if not _LABEL_RE.match(label):
        return (
            f'{field_name} column label "{label}" is invalid. '
            'Labels must start with a lowercase letter and contain only '
            'lowercase letters, digits, and underscores (max 59 chars).'
        )
    return ''
