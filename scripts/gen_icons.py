"""生成 PWA 所需的纯色 PNG 图标（无第三方依赖）。"""
import struct
import zlib


def _chunk(tag: bytes, data: bytes) -> bytes:
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def write_png(path: str, size: int, rgb: tuple[int, int, int]) -> None:
    row = b"\x00" + bytes(rgb) * size
    raw = row * size
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    data = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )
    with open(path, "wb") as fh:
        fh.write(data)


if __name__ == "__main__":
    write_png("web/public/icon-192.png", 192, (31, 111, 235))
    write_png("web/public/icon-512.png", 512, (31, 111, 235))
    print("generated web/public/icon-192.png, web/public/icon-512.png")