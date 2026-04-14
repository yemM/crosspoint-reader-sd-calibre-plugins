"""
Persistent preferences for the CrossPoint plugin.

Stored in Calibre's config directory as a JSON file.  All access goes
through the ``prefs`` singleton; callers read/write it like a dict:

    from calibre_crosspoint.config.prefs import prefs
    label = prefs['col_progress']
    prefs['col_progress'] = 'my_progress'
"""

from calibre.utils.config import JSONConfig

# Defaults — the Calibre custom column labels (without the leading '#').
DEFAULTS = {
    'col_progress':    'cp_progress',   # float [0, 100]
    'col_spine':       'cp_spine',      # int — spine (chapter) index
    'col_page':        'cp_page',       # int — page index within chapter
    'auto_create_cols': True,           # create missing columns automatically
}

prefs = JSONConfig('plugins/crosspoint_sd')
prefs.defaults = DEFAULTS
