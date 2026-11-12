#!/usr/bin/env python3
"""
Pull the stock Pixel Launcher out of a Pixel 9a (tegu) full OTA zip.

Reads payload.bin straight from the OTA (no full unzip), rebuilds the system_ext
partition image (verified against the OTA's SHA-256), then uses 7-Zip to copy
priv-app/NexusLauncherRelease/NexusLauncherRelease.apk out of that ext4 image.

Supports full OTAs only (REPLACE / REPLACE_BZ / REPLACE_XZ / REPLACE_ZSTD / ZERO).

usage: python ota_extract.py <tegu-ota-*.zip> <out_dir>      (prints the fingerprint)
"""
import bz2, glob, hashlib, lzma, os, shutil, struct, subprocess, sys, zipfile
from pathlib import Path

try:
    from compression import zstd  # Python 3.14+
except ImportError:
    zstd = None

LAUNCHER_IN_SYSTEM_EXT = "priv-app/NexusLauncherRelease/NexusLauncherRelease.apk"


# ---------------------------------------------------------------- protobuf (just enough)
def _varint(b, i):
    r = s = 0
    while True:
        c = b[i]; i += 1
        r |= (c & 0x7F) << s; s += 7
        if c < 0x80:
            return r, i


def _fields(b):
    i, out = 0, []
    while i < len(b):
        key, i = _varint(b, i)
        f, wt = key >> 3, key & 7
        if wt == 0:
            v, i = _varint(b, i)
        elif wt == 2:
            n, i = _varint(b, i); v = b[i:i + n]; i += n
        elif wt == 1:
            v = b[i:i + 8]; i += 8
        elif wt == 5:
            v = b[i:i + 4]; i += 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wt}")
        out.append((f, v))
    return out


def _get(fl, n, default=None):
    for f, v in fl:
        if f == n:
            return v
    return default


# ---------------------------------------------------------------- OTA metadata
def ota_metadata(ota):
    """key=value pairs from META-INF/com/android/metadata"""
    with zipfile.ZipFile(ota) as z:
        txt = z.read("META-INF/com/android/metadata").decode()
    return dict(l.split("=", 1) for l in txt.splitlines() if "=" in l)


# ---------------------------------------------------------------- payload.bin
def extract_partition(ota, name, out_img):
    z = zipfile.ZipFile(ota)
    info = z.getinfo("payload.bin")
    if info.compress_type != zipfile.ZIP_STORED:
        raise SystemExit("payload.bin is compressed inside the zip (not a standard OTA)")
    with open(ota, "rb") as f:
        f.seek(info.header_offset)
        lh = f.read(30)
        base = info.header_offset + 30 + struct.unpack("<H", lh[26:28])[0] + struct.unpack("<H", lh[28:30])[0]
        f.seek(base)
        magic, ver, msize, sigsize = struct.unpack(">4sQQI", f.read(24))
        if magic != b"CrAU" or ver != 2:
            raise SystemExit(f"not an A/B payload ({magic}, v{ver})")
        manifest = _fields(f.read(msize))
        data_off = base + 24 + msize + sigsize
        bs = _get(manifest, 3, 4096)
        for fld, pv in manifest:
            if fld != 13:
                continue
            p = _fields(pv)
            if _get(p, 1, b"").decode() != name:
                continue
            pinfo = _fields(_get(p, 7, b""))
            size, want_sha = _get(pinfo, 1, 0), _get(pinfo, 2, b"")
            with open(out_img, "wb") as o:
                o.truncate(size)
                for of, ov in p:
                    if of != 8:
                        continue
                    op = _fields(ov)
                    t, doff, dlen, dsha = _get(op, 1, 0), _get(op, 2, 0), _get(op, 3, 0), _get(op, 8, b"")
                    ext = [(_get(_fields(e), 1, 0), _get(_fields(e), 2, 0)) for ef, e in op if ef == 6]
                    f.seek(data_off + doff)
                    raw = f.read(dlen)
                    if dsha and hashlib.sha256(raw).digest() != dsha:
                        raise SystemExit(f"{name}: operation data hash mismatch (corrupt OTA?)")
                    if t == 0:
                        d = raw
                    elif t == 1:
                        d = bz2.decompress(raw)
                    elif t == 8:
                        d = lzma.decompress(raw)
                    elif t == 14:
                        if zstd is None:
                            raise SystemExit("OTA uses zstd: needs Python 3.14+")
                        d = zstd.decompress(raw)
                    elif t in (6, 7):
                        d = None
                    else:
                        raise SystemExit(f"{name}: operation type {t} needs a source build "
                                         "(this is an incremental OTA; use the full OTA)")
                    pos = 0
                    for start, num in ext:
                        n = num * bs
                        o.seek(start * bs)
                        o.write(b"\0" * n if d is None else d[pos:pos + n])
                        pos += 0 if d is None else n
            h = hashlib.sha256()
            with open(out_img, "rb") as r:
                for chunk in iter(lambda: r.read(1 << 24), b""):
                    h.update(chunk)
            if want_sha and h.digest() != want_sha:
                raise SystemExit(f"{name}: rebuilt image hash mismatch")
            return out_img
    raise SystemExit(f"partition {name} not found in payload")


# ---------------------------------------------------------------- ext4 (via 7-Zip)
def find_7z():
    for c in ("7z", "7zz", "7za"):
        if shutil.which(c):
            return shutil.which(c)
    for c in glob.glob(r"C:\Program Files*\7-Zip\7z.exe"):
        return c
    raise SystemExit("7-Zip not found (needed to read the ext4 system_ext image); install it or add 7z to PATH")


def extract_launcher(ota, out_dir):
    """returns (launcher_apk_path, fingerprint, metadata)"""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    meta = ota_metadata(ota)
    img = out_dir / "system_ext.img"
    print(f"  extracting system_ext from {Path(ota).name} ...")
    extract_partition(ota, "system_ext", img)
    r = subprocess.run([find_7z(), "x", "-y", f"-o{out_dir / 'system_ext'}", str(img),
                        LAUNCHER_IN_SYSTEM_EXT.replace("/", os.sep)], capture_output=True, text=True)
    apk = out_dir / "system_ext" / LAUNCHER_IN_SYSTEM_EXT
    if r.returncode != 0 or not apk.exists():
        sys.stderr.write(r.stdout[-2000:] + r.stderr[-2000:])
        raise SystemExit("could not extract the launcher APK from system_ext")
    img.unlink()
    return apk, meta.get("post-build", ""), meta


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    apk, fp, _ = extract_launcher(sys.argv[1], sys.argv[2])
    print(f"{apk}\n{fp}")
