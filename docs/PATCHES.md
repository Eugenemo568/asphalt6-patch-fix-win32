# Technical notes

These notes cover the loader `Asphalt 6.exe` from `Asphalt6-Win32.zip` (archive.org item `asphalt-6-win-32`),
sha256 `8b184e4bdc21ff9e51b72e58ca0ae0d618088ecd7f12699811989bf05ee87147`, image base `0x30000000`.
The game code itself is the original Mac App Store i386 Mach-O (`Asphalt 6.app/Contents/MacOS/Asphalt 6`). The loader maps it,
applies `code_relocs.bin`, binds its imports to Win32 shims and jumps to its entry point.

## How the port is put together

- `code_relocs.bin` is an uncompressed custom table. It starts with the magic `A6RL`, then a `u32` count (163 662), then
  `count × u32` sorted offsets into the Mach-O image. These are the absolute slots the loader slides after placing the image.
  It is not an archive or a disk image.
- `UserData\glsl.config` is created empty on purpose (`[host] created empty glsl.config in UserData`).
- The movies (`Resources/data/LOGO_Gameloft_1280x720.mov`, `A6_1280x720.mov`) are H.264 Main + AAC LC 48 kHz stereo.
  The loader plays them through Media Foundation (`MFCreateSourceReaderFromURL`) in place of QuickTime's `QTMovie`.

## Bug: hang on the Gameloft logo

Symptom: the logo movie plays, then the game sits on its last frame forever. The main loop keeps running, and the
watchdog never reports a stall.

The movie tick function (`0x30025570`) declares end of playback only when every opened stream has hit EOF:

```
(no video stream || video EOF [+0x4c]) && (no audio stream || audio EOF [+0x50]) && no pending samples
```

Audio samples are only pulled while the WASAPI render client `[+0x74]` exists:

```
3002575b  cmp dword [esi+0x74], 0
3002575f  je  0x30025929          ; skip audio entirely -> audio EOF is never set
```

That client is created in `0x30025980`:

```
IAudioClient::Initialize(AUDCLNT_SHAREMODE_SHARED, StreamFlags = 0, 1 s, 0,
                         WAVEFORMATEX{PCM, 2 ch, 48000 Hz, 16 bit}, NULL)
```

The stream flags are 0, so `AUTOCONVERTPCM` is missing. When the shared-mode engine does not accept that exact format,
`Initialize` fails and `[+0x74]` stays NULL. The movie's audio stream then never reaches EOF, so the movie never ends,
and the game waits for it forever. The device format is the likely trigger (for example a 44.1 kHz or 24-bit device).
The loader's own game-audio path already retries with the device mix format, but the movie path has no such fallback.

### Fix (`video-hang-fix` group)

| VA | Change |
|---|---|
| `0x30025b0a` | Jump to a cave at `0x3004ece0` that calls `Initialize` with `StreamFlags = 0x88000000` (`AUTOCONVERTPCM \| SRC_DEFAULT_QUALITY`), then returns |
| `0x3002575f` | No audio render client → jump to `0x30025922` (`mov [esi+0x50],1`). The movie plays silently instead of hanging |
| `0x300257a7` | Audio `ReadSample` failure → audio EOF (was: retry forever) |
| `0x30025648` | Video `ReadSample` failure → video EOF (was: retry forever) |

The `base` group sets the `.text` `VirtualSize` from `0x4dc9b` to `0x4de00` (the raw size), so the zero padding at the end of
`.text` is mapped executable and can hold the caves.

## Optional: `debug-log` group

The release loader prints nothing:

- Its logger was compiled down to `xor eax,eax; ret` at `0x300082e0`. Because of identical-code folding, the same address is
  also used as a generic "return 0" shim for dozens of Mac APIs. Patching the stub itself would break those shims.
- Its `fprintf` wrapper at `0x30025bc0` discards everything written to `stdout` and `stderr`.

The patch adds `log(fmt, ...) → __stdio_common_vfprintf(stderr, ...)` in a cave at `0x3004ecb0` and redirects only the
51 direct log call sites to it (listed in `tools/log_call_sites.json`). It also NOPs the wrapper's stderr check
(`0x30025bdf`). Run the game with `2> log.txt` (see the diagnostic launcher) to capture the output.

## Environment variables understood by the loader

| Variable | Effect |
|---|---|
| `A6_WINDOWED` | Windowed instead of fullscreen |
| `A6_WATCHDOG` | Samples the main thread and reports main-loop stalls on stderr (works without `debug-log`) |
| `A6_DUMP_UNRESOLVED` | Lists Mac imports bound to logging trampolines |
| `A6_DUMPSHADER` | Dumps GLSL shaders to files |
| `A6_FRAMEDUMP`, `A6_PRESENTDUMP` | Write frames as BMP files |
| `A6_DIAG_TEX`, `A6_DIAG_ALLTEX` | Texture diagnostics / dumps |
| `A6_DIAG_DRAWSTATE`, `A6_DIAG_RSTATE`, `A6_DIAG_SEM`, `A6_DIAG_STEP`, `A6_DIAG_STEPRECT`, `A6_DIAG_FRAME`, `A6_FRAMESTAT` | Renderer diagnostics |
| `A6_PROFILE` | Per-600-frame timing |
| `A6_NOPAD`, `A6_PAD_DEBUG` | Disable / debug gamepad support |
| `A6_NET_DEBUG` | LAN multiplayer debug |
| `A6_CHECK_STRINGS`, `A6_WATCH_RELOC`, `A6_LOG_STRGAPS`, `A6_DUMP_MARKS` | Relocation checks |
| `A6_ASSERT_CONTINUE` | Continue after a failed assert |

Only `A6_WINDOWED`, `A6_WATCHDOG`, `A6_DUMP_UNRESOLVED` and `A6_NOPAD` were checked. The other effects are
inferred from the variable names and the log strings next to them. Most of these print through the logger, so they need
the `debug-log` group to show anything.

## Rebuilding the patch file

```
pip install pefile keystone-engine
python tools/build_patches.py "path/to/original/Asphalt 6.exe"
```

This assembles every patch from source and rewrites `patches/asphalt6-win32.json`. Both patchers read that file.
