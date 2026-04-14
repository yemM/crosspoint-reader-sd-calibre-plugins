"""
Generate binary test fixtures for CrossPoint unit tests.

Run this script once to (re-)create the binary files under
tests/fixtures/mock_sd/.crosspoint/epub_12345/.
"""

import io
import os
import struct
import sys

FIXTURE_DIR = os.path.join(
    os.path.dirname(__file__), 'fixtures', 'mock_sd', '.crosspoint', 'epub_12345'
)


def write_string(buf, s):
    encoded = s.encode('utf-8')
    buf.write(struct.pack('<I', len(encoded)))
    buf.write(encoded)


def build_book_bin(title, author, spine_entries):
    """Build a version-5 book.bin bytestring.

    spine_entries: list of (href, cumulative_size) tuples.
    """
    buf = io.BytesIO()

    # --- header placeholder (we'll fix up LUT offset later) ---
    version = 5
    buf.write(struct.pack('B', version))
    lut_offset_pos = buf.tell()
    buf.write(struct.pack('<I', 0))          # LUT offset placeholder
    buf.write(struct.pack('<II', len(spine_entries), 0))  # spine_count, toc_count

    # metadata strings
    write_string(buf, title)
    write_string(buf, author)
    write_string(buf, 'en')
    write_string(buf, 'cover.jpg')
    write_string(buf, 'text.html')

    # spine entries (written sequentially; we record their offsets for LUT)
    spine_offsets = []
    for href, cumulative in spine_entries:
        spine_offsets.append(buf.tell())
        write_string(buf, href)
        buf.write(struct.pack('<Ih', cumulative, -1))  # cumulative_size, toc_index=-1

    # LUT (spine offsets as uint32, then toc offsets — empty here)
    lut_pos = buf.tell()
    for off in spine_offsets:
        buf.write(struct.pack('<I', off))

    # Fix up the LUT offset in the header
    data = buf.getvalue()
    data = (
        data[:lut_offset_pos]
        + struct.pack('<I', lut_pos)
        + data[lut_offset_pos + 4:]
    )
    return data


def main():
    os.makedirs(FIXTURE_DIR, exist_ok=True)

    # progress.bin: spine_index=2, page_index=7
    progress_path = os.path.join(FIXTURE_DIR, 'progress.bin')
    with open(progress_path, 'wb') as f:
        f.write(struct.pack('<HH', 2, 7))
    print(f'Wrote {progress_path}')

    # book.bin: 5 spine entries, each with 100 cumulative pages
    spine_entries = [
        ('chapter1.html', 0),
        ('chapter2.html', 100),
        ('chapter3.html', 200),
        ('chapter4.html', 300),
        ('chapter5.html', 400),
    ]
    book_bin_data = build_book_bin('Test Book', 'Test Author', spine_entries)
    book_bin_path = os.path.join(FIXTURE_DIR, 'book.bin')
    with open(book_bin_path, 'wb') as f:
        f.write(book_bin_data)
    print(f'Wrote {book_bin_path} ({len(book_bin_data)} bytes)')

    # Placeholder EPUB
    epub_path = os.path.join(
        os.path.dirname(FIXTURE_DIR), '..', '..', 'test_book.epub'
    )
    epub_path = os.path.normpath(epub_path)
    if not os.path.exists(epub_path):
        with open(epub_path, 'wb') as f:
            f.write(b'PK\x03\x04')  # Minimal ZIP/EPUB magic bytes
        print(f'Wrote placeholder {epub_path}')


if __name__ == '__main__':
    main()
