#!/usr/bin/env python3
"""
Asphalt 6 Win32 port fixer (cross-platform, standard library only).

    python patch.py [GAME_DIR] [--debug-log] [--restore]

GAME_DIR is the folder that contains "Asphalt 6.exe" (default: current folder).
The original exe is kept as "Asphalt 6.exe.orig"; --restore puts it back.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = "Asphalt 6.exe"
BACKUP = EXE + ".orig"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_spec():
    with open(os.path.join(HERE, "patches", "asphalt6-win32.json"), encoding="utf-8") as f:
        return json.load(f)


def selected_patches(spec, debug_log):
    names = [n for n, g in spec["groups"].items() if g["default"]]
    if debug_log:
        names.append("debug-log")
    seen, out = set(), []
    for n in names:
        for p in spec["groups"][n]["patches"]:
            if p["offset"] in seen:
                continue
            seen.add(p["offset"])
            out.append(p)
    return names, out


def is_applied(data, patches):
    return all(data[p["offset"]:p["offset"] + len(p["patched"]) // 2] == bytes.fromhex(p["patched"])
               for p in patches)


def main():
    ap = argparse.ArgumentParser(description="Fix the Asphalt 6 Win32 port (hang on the Gameloft logo).")
    ap.add_argument("game_dir", nargs="?", default=".", help='folder that contains "Asphalt 6.exe"')
    ap.add_argument("--debug-log", action="store_true", help="also re-enable the diagnostic log on stderr")
    ap.add_argument("--restore", action="store_true", help="restore the original exe from the backup")
    a = ap.parse_args()

    exe = os.path.join(a.game_dir, EXE)
    bak = os.path.join(a.game_dir, BACKUP)
    if not os.path.isfile(exe) and not os.path.isfile(bak):
        sys.exit(f'"{EXE}" not found in {os.path.abspath(a.game_dir)}')

    spec = load_spec()

    if a.restore:
        if not os.path.isfile(bak):
            sys.exit(f'no backup "{BACKUP}" to restore')
        shutil.copyfile(bak, exe)
        print("restored the original exe")
        return

    # Always patch from the pristine original (the backup if we made one earlier).
    src = bak if os.path.isfile(bak) else exe
    data = open(src, "rb").read()
    names, patches = selected_patches(spec, a.debug_log)

    if sha256(data) != spec["original_sha256"]:
        if src == exe and is_applied(data, patches):
            print("already patched - nothing to do")
            return
        sys.exit("unknown version of the exe (sha256 %s).\n"
                 "This patch is for Asphalt6-Win32.zip from archive.org/details/asphalt-6-win-32 "
                 "(sha256 %s)." % (sha256(data), spec["original_sha256"]))

    buf = bytearray(data)
    for p in patches:
        o, old, new = p["offset"], bytes.fromhex(p["original"]), bytes.fromhex(p["patched"])
        if buf[o:o + len(old)] != old:
            sys.exit(f"unexpected bytes at {o:#x} - aborting, nothing was written")
        buf[o:o + len(new)] = new

    if not os.path.isfile(bak):
        shutil.copyfile(exe, bak)
        print(f'backup: "{BACKUP}"')
    with open(exe, "wb") as f:
        f.write(buf)
    print("applied:", ", ".join(names), f"({len(patches)} patches)")
    print("sha256:", sha256(bytes(buf)))


if __name__ == "__main__":
    main()
