# CrossPoint SD — Calibre Plugin

A [Calibre](https://calibre-ebook.com) device plugin that treats a **CrossPoint-formatted microSD card** as a reading device, enabling:

- Transferring EPUBs from your Calibre library to the SD card
- Syncing reading progress from the SD card back into configurable Calibre custom columns

Targets the **Xteink X4** running the [CrossPoint firmware](https://github.com/crosspoint-reader/crosspoint-reader).

---

## How it works

The Xteink X4 does not expose USB mass storage — the SD card must be removed and inserted via an adapter. Once mounted, the plugin detects it by the presence of a `.crosspoint/` directory at the card root, then:

1. Lists all EPUBs on the card for Calibre's device view
2. Copies EPUBs to/from the card root on send/remove
3. On sync, reads each book's `progress.bin` (current chapter + page) and `book.bin` (title, author, spine metadata), matches them to your Calibre library by title + author, and writes the progress values to custom columns

---

## Requirements

- Calibre 6.0 or later
- Python 3.8+ (bundled with Calibre)
- A CrossPoint-formatted microSD card with a `.crosspoint/` directory
- **FAT32 recommended over exFAT** — exFAT works for most books, but fragmented files can fail to open due to a SdFat cluster traversal limitation (reads silently stop after 8 KB). If an EPUB opens fine on your PC but not on the device, reformat the SD card as FAT32 and re-copy your books.

---

## Installation

### From a release ZIP

1. Download `crosspoint_plugin.zip` from the [Releases](../../releases) page
2. In Calibre: **Preferences → Plugins → Load plugin from file**
3. Select the ZIP — Calibre installs and activates it immediately

### Build from source

```bash
git clone https://github.com/yemM/crosspoint-reader-sd-calibre-plugins
cd crosspoint-reader-sd-calibre-plugins
make install        # builds the ZIP and runs calibre-customize -a
make debug          # launches calibre-debug -g for live output
```

---

## Setup

### 1. Create custom columns in Calibre

Go to **Preferences → Add a custom column** and create the three columns below. The labels (without `#`) must match what you configure in the plugin settings.

| Label | Type | Purpose |
|---|---|---|
| `cp_progress` | Floating point numbers | Reading progress (0–100 %) |
| `cp_spine` | Integers | Current chapter (spine index) |
| `cp_page` | Integers | Current page within chapter |

Alternatively, enable **Auto-create missing columns** in the plugin settings and the columns will be created automatically the first time the SD card is connected.

### 2. Configure column names (optional)

In Calibre: **Preferences → Plugins → Device Interface → CrossPoint SD Device → Customize plugin**

| Setting | Default | Description |
|---|---|---|
| Progress column | `cp_progress` | Calibre column label for reading % |
| Chapter column | `cp_spine` | Calibre column label for spine index |
| Page column | `cp_page` | Calibre column label for page index |
| Auto-create missing columns | On | Creates columns automatically on first connect |

Enter labels without the leading `#`. Leave a field blank to keep its default.

---

## Usage

1. Remove the microSD card from the Xteink X4 and insert it via a USB adapter
2. Calibre detects the card and shows it in the device panel
3. Drag books from your library onto the device to copy EPUBs
4. Click **Send changes to device** (or the sync button) to pull reading progress back into your library columns

> **Note:** Moving EPUB files to a different folder on the SD card resets the CrossPoint progress cache for that book (the cache key is derived from the file path). Keep books in place after copying.

---

## Project structure

```
calibre_crosspoint/
├── __init__.py                        Plugin entry point
├── plugin.py                          CrossPointDevice(DevicePlugin) — all Calibre methods
├── crosspoint/
│   ├── detector.py                    Scans mounted volumes for .crosspoint/ signature
│   ├── book_list.py                   Recursive EPUB enumerator
│   ├── progress_reader.py             Parses 4-byte progress.bin
│   └── book_bin_parser.py             Parses book.bin v5 (metadata + spine entries)
├── calibre_sync/
│   ├── metadata_matcher.py            Fuzzy title + author matching
│   └── custom_columns.py             Writes progress data to Calibre columns
└── config/
    ├── prefs.py                       JSONConfig preferences store
    └── settings_widget.py            Qt configuration widget
tests/
├── fixtures/mock_sd/                  Binary test fixtures
├── make_fixtures.py                   Regenerate binary fixtures
├── test_book_bin_parser.py
├── test_book_list.py
├── test_metadata_matcher.py
└── test_progress_reader.py
```

---

## Development

### Run tests

```bash
python3 -m pytest tests/ -v
```

Tests run without a Calibre installation — the Calibre-specific imports are guarded so the pure-logic modules can be tested standalone.

### Regenerate binary fixtures

```bash
python3 tests/make_fixtures.py
```

### Build targets

| Command | Description |
|---|---|
| `make zip` | Package plugin as `crosspoint_plugin.zip` |
| `make install` | Build ZIP and install into local Calibre |
| `make debug` | Launch `calibre-debug -g` |
| `make test` | Run pytest |
| `make clean` | Remove build artefacts |

---

## Known limitations

| Issue | Detail |
|---|---|
| No USB mass storage | The Xteink X4 requires physical SD card removal; no USB transfer |
| exFAT fragmentation | exFAT works for most books, but fragmented files can silently fail to open (reads stop after 8 KB). FAT32 avoids this. |
| Path-sensitive cache | Moving an EPUB on the card breaks its progress cache |
| `book.bin` version | Parser targets format version 5; older firmware may differ |
| Cache built on first open | Books never opened on the device have no progress data |

---

## References

- [CrossPoint firmware](https://github.com/crosspoint-reader/crosspoint-reader)
- [Calibre plugin API](https://manual.calibre-ebook.com/plugins.html#module-calibre.devices.interface)
- [Xteink X4](https://www.xteink.com/products/xteink-x4)
