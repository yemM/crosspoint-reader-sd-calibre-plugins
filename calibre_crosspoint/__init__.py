"""
CrossPoint SD Device Plugin for Calibre.

Treats a CrossPoint-formatted microSD card as a Calibre device, enabling:
  - Transferring EPUBs from Calibre library to the SD card
  - Reading back reading progress from the SD card into Calibre custom columns

Target device: Xteink X4 running CrossPoint firmware
Firmware: https://github.com/crosspoint-reader/crosspoint-reader

Note: The Calibre import is deferred so that the crosspoint.* and
calibre_sync.* submodules can be imported and tested without a live
Calibre installation.
"""

try:
    from .plugin import CrossPointDevice  # noqa: F401
    plugin_class = CrossPointDevice
except ImportError:
    # Running outside Calibre (e.g. unit tests) — silently skip.
    pass
