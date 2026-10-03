#!/usr/bin/env python3
"""
Regenerates patches/asphalt6-win32.json from the original "Asphalt 6.exe" loader.

Every patch is assembled from source here, so the JSON can be audited and rebuilt.
Requires: pip install pefile keystone-engine

    python tools/build_patches.py "path/to/original/Asphalt 6.exe"
"""
import hashlib
import json
import os
import struct
import sys

import keystone
import pefile

BASE = 0x30000000
ORIGINAL_SHA256 = "8b184e4bdc21ff9e51b72e58ca0ae0d618088ecd7f12699811989bf05ee87147"
HERE = os.path.dirname(os.path.abspath(__file__))
KS = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)

# Code caves in the zero padding at the end of .text (VA 0x3004ec9b..0x3004ee00)
LOG_CAVE = 0x3004ECB0
AUDIO_CAVE = 0x3004ECE0

# Loader internals (from the original binary)
ACRT_IOB_FUNC = 0x300292A8          # __acrt_iob_func(int)
PRINTF_OPTIONS = 0x30001000         # returns &__local_stdio_printf_options
STDIO_COMMON_VFPRINTF = 0x3002C1BF  # __stdio_common_vfprintf
LOG_STUB = 0x300082E0               # "xor eax,eax; ret" - compiled-out logger (also used as a generic return-0 shim!)


def asm(src, va):
    return bytes(KS.asm(src, va)[0])


class Image:
    def __init__(self, data):
        self.raw = bytearray(data)
        pe = pefile.PE(data=bytes(data))
        self.text = pe.sections[0]
        assert self.text.Name.rstrip(b"\0") == b".text"
        self.patches = []

    def off(self, va):
        t = self.text
        return va - BASE - t.VirtualAddress + t.PointerToRawData

    def put_file(self, offset, old, new, note):
        assert len(old) == len(new)
        cur = bytes(self.raw[offset:offset + len(old)])
        assert cur == old, f"{offset:#x}: expected {old.hex()} got {cur.hex()}"
        self.raw[offset:offset + len(new)] = new
        self.patches.append({"offset": offset, "original": old.hex(), "patched": new.hex(), "note": note})

    def put(self, va, old, new, note):
        self.put_file(self.off(va), old, new, f"VA {va:#010x}: {note}")

    def cave(self, va, code, note):
        o = self.off(va)
        assert va + len(code) <= BASE + self.text.VirtualAddress + self.text.SizeOfRawData
        self.put_file(o, bytes(len(code)), code, f"VA {va:#010x}: {note}")


def base_group(img):
    """Grow .text VirtualSize so the code caves in its file padding are mapped executable."""
    vs_off = img.text.get_file_offset() + 8
    old = struct.pack("<I", img.text.Misc_VirtualSize)
    new = struct.pack("<I", img.text.SizeOfRawData)
    img.put_file(vs_off, old, new, ".text VirtualSize 0x4dc9b -> 0x4de00 (maps the code caves)")


def video_hang_group(img):
    # Movie audio: IAudioClient::Initialize(SHARED, flags=0, 1s, 0, 48k/16-bit PCM) fails when the
    # device mix format differs -> movie audio never reaches EOF -> movie never ends -> hang on logo.
    code = asm(
        "mov eax,[esi]; push 0x88000000; push 0; push esi; mov eax,[eax+0xc]; call eax; jmp 0x30025b16",
        AUDIO_CAVE,
    )
    img.cave(AUDIO_CAVE, code,
             "IAudioClient::Initialize with AUTOCONVERTPCM|SRC_DEFAULT_QUALITY (0x88000000)")
    jmp = asm(f"jmp {AUDIO_CAVE:#x}", 0x30025B0A)
    img.put(0x30025B0A, bytes.fromhex("8b066a006a00568b400cffd0"), jmp + b"\x90" * (12 - len(jmp)),
            "movie audio init -> cave with conversion flags")
    # If the audio client still could not be created, treat the movie's audio track as finished
    # (movie plays silently instead of never ending).
    img.put(0x3002575F, bytes.fromhex("0f84c4010000"),
            b"\x0f\x84" + struct.pack("<i", 0x30025922 - 0x30025765),
            "no audio render client -> mark audio EOF")
    # A failing IMFSourceReader::ReadSample ends the stream instead of retrying forever.
    img.put(0x300257A7, bytes.fromhex("0f887c010000"),
            b"\x0f\x88" + struct.pack("<i", 0x30025922 - 0x300257AD),
            "audio ReadSample failure -> mark audio EOF")
    img.put(0x30025648, bytes.fromhex("7862"), bytes.fromhex("785b"),
            "video ReadSample failure -> mark video EOF")


def debug_log_group(img):
    # The release loader compiled its logger down to the shared "return 0" stub at 0x300082e0.
    # That stub doubles as a shim for many Mac APIs, so it must NOT be patched; instead the 51
    # direct log call sites are redirected to a new vfprintf(stderr, ...) routine in a code cave.
    code = asm(
        f"""lea eax,[esp+8]; push eax; push 0; push dword ptr [esp+0xc];
            push 2; call {ACRT_IOB_FUNC:#x}; add esp,4; push eax;
            call {PRINTF_OPTIONS:#x}; push dword ptr [eax+4]; push dword ptr [eax];
            call {STDIO_COMMON_VFPRINTF:#x}; add esp,0x18; ret""",
        LOG_CAVE,
    )
    img.cave(LOG_CAVE, code, "log(fmt, ...) -> vfprintf(stderr, fmt, args)")
    sites = json.load(open(os.path.join(HERE, "log_call_sites.json")))
    assert len(sites) == 51
    for va in sites:
        old = b"\xe8" + struct.pack("<i", LOG_STUB - (va + 5))
        new = b"\xe8" + struct.pack("<i", LOG_CAVE - (va + 5))
        img.put(va, old, new, "loader log call -> cave")
    # fprintf wrapper drops writes to stdout and stderr; let stderr through (engine/NSLog/video logs).
    img.put(0x30025BDF, bytes.fromhex("7420"), bytes.fromhex("9090"),
            "fprintf wrapper: stop discarding stderr")


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "Asphalt 6.exe"
    data = open(src, "rb").read()
    sha = hashlib.sha256(data).hexdigest()
    if sha != ORIGINAL_SHA256:
        sys.exit(f"unexpected input sha256 {sha}")
    groups = {}
    for name, fn, desc, default in [
        ("base", base_group, "Required by all other groups: maps the code caves.", True),
        ("video-hang-fix", video_hang_group,
         "Fixes the hang on the Gameloft logo when the audio device is not 48 kHz/16-bit.", True),
        ("debug-log", debug_log_group,
         "Optional: re-enables the loader/engine log on stderr (for bug reports).", False),
    ]:
        img = Image(data)
        fn(img)
        groups[name] = {"description": desc, "default": default, "patches": img.patches}
    out = {
        "name": "Asphalt 6 Win32 port fixes",
        "target": "Asphalt 6.exe (Asphalt6-Win32.zip, archive.org/details/asphalt-6-win-32)",
        "original_size": len(data),
        "original_sha256": ORIGINAL_SHA256,
        "groups": groups,
    }
    path = os.path.join(HERE, "..", "patches", "asphalt6-win32.json")
    with open(path, "w", newline="\n") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    print("wrote", os.path.normpath(path), {k: len(v["patches"]) for k, v in groups.items()})


if __name__ == "__main__":
    main()
