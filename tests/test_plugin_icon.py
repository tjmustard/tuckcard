"""The plugin listing icon is a byte-identical copy of the master. D-022."""

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "media/icons/icon-1024.png"
LISTING = ROOT / "plugins/tuckcard/.claude-plugin/icon.png"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_size(path):
    """Read the size from the IHDR chunk, without an image library."""
    data = path.read_bytes()
    assert data.startswith(PNG_SIGNATURE), "{} is not a PNG".format(path)
    assert data[12:16] == b"IHDR", "{} has no IHDR first".format(path)
    return struct.unpack(">II", data[16:24])


def test_the_listing_icon_is_the_master_byte_for_byte():
    assert MASTER.is_file() and LISTING.is_file()
    assert not LISTING.is_symlink()
    assert LISTING.read_bytes() == MASTER.read_bytes()


def test_both_icons_are_1024_square_pngs():
    assert png_size(MASTER) == (1024, 1024)
    assert png_size(LISTING) == (1024, 1024)
