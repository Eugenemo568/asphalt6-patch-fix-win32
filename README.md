# Asphalt 6 Win32 port fix

A small patcher for the unofficial **Asphalt 6: Adrenaline** Windows port
([archive.org/details/asphalt-6-win-32](https://archive.org/details/asphalt-6-win-32)), which is built from the Mac App Store i386 build.

**What it fixes:** on some PCs the game plays the Gameloft logo and then freezes on it forever.

> This repository has no game files and no executables. The patcher changes your own copy of `Asphalt 6.exe` and checks
> its SHA-256 first. It is not affiliated with Gameloft or with the author of the port.

## Who needs it

You need it if the game shows the Gameloft logo and then hangs, even in windowed mode. The cause is the movie player in the
loader. It opens the movie's sound with one fixed format (48 kHz / 16-bit) and does not let Windows convert it. If your
sound device does not accept that, the movie's audio never finishes, so the movie never ends and the game waits forever.
The details are in [docs/PATCHES.md](docs/PATCHES.md).

## Install

1. Download this repository and unpack it **into your game folder** (the folder with `Asphalt 6.exe`).
2. Run **`Patch.bat`**.
3. Start the game as usual.

`Patch.bat` finds the game folder on its own: it looks in its own folder and the one above it, and otherwise opens a folder picker.
It keeps the original as `Asphalt 6.exe.orig` and copies two launchers next to the game:

- `Asphalt 6 (windowed).bat`: plays in a window.
- `Asphalt 6 (diagnostic log).bat`: writes `UserData\diag\run_log.txt` for bug reports.

| Command | What it does |
|---|---|
| `Patch.bat` | Applies the fix |
| `Patch.bat -DebugLog` | Fix plus the loader's diagnostic log (useful with the diagnostic launcher) |
| `Patch.bat -Restore` | Puts the original exe back |

Python alternative (any OS, for example Linux with Proton/Wine):
`python3 patch.py "/path/to/game" [--debug-log] [--restore]`

## What changes

33 bytes in `Asphalt 6.exe`:

- The movie's audio is opened with Windows' automatic format conversion, so it works with any sound device format.
- If the movie's audio still cannot be opened, the movie plays silently instead of hanging.
- A movie decode error ends the movie instead of making the game wait forever.

## Known issues (not fixed yet)

- Some users see transparent headlights, interiors and wheels on car models.
- No resolution scaling, and no controller remapping.

Bug reports are welcome. Please attach `UserData\diag\run_log.txt` made with `Patch.bat -DebugLog` and the diagnostic launcher.

## Credits

- The Windows port is by **cedopa2637** (archive.org).
- Asphalt 6: Adrenaline © Gameloft.
- The patcher and its docs are under the MIT license (see `LICENSE`).

---

## По-русски

Патч для неофициального Windows-порта **Asphalt 6: Adrenaline** с archive.org.
Он исправляет **зависание на заставке Gameloft**.

**Причина.** Загрузчик открывает звук роликов в жёстком формате 48 кГц / 16 бит и не разрешает Windows его преобразовать.
Если звуковое устройство такой формат не принимает, звуковая дорожка ролика никогда не «заканчивается», и игра ждёт вечно.

**Установка:**
1. Скачайте репозиторий и распакуйте его в папку с игрой (туда, где `Asphalt 6.exe`).
2. Запустите **`Patch.bat`**.
3. Запускайте игру как обычно.

Оригинал сохраняется как `Asphalt 6.exe.orig`. Вернуть его можно командой `Patch.bat -Restore`.
Если игра не запускается после патча, выполните `Patch.bat -DebugLog`, запустите `Asphalt 6 (diagnostic log).bat` и
приложите `UserData\diag\run_log.txt` к issue.

В репозитории нет файлов игры. Патчер изменяет только вашу копию `Asphalt 6.exe` и перед этим проверяет её контрольную сумму.
