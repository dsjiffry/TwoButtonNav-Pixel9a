# Two-Button Navigation for Pixel 9a (Android 17)

A **KernelSU / Magisk module** that brings back Android 9-style **2-button navigation**
(back + home) on the **Google Pixel 9a** running Android 17.

> [!IMPORTANT]
> **Pixel 9a (`tegu`) only.** Only tested on a Pixel 9a. Each release works on **one exact
> Android build**. Pick the release for your build in the [table below](#which-release-do-i-need).

| Action | Result |
|---|---|
| Tap home | Home |
| Long-press home | Assistant / Circle to Search |
| Tap back | Back |
| Swipe up from the bar | Recents |
| Swipe sideways along the bar | Switch to the previous / next app |

> [!NOTE]
> **No prebuilt zips.** The module contains a patched copy of Google's Pixel Launcher, which
> can't be redistributed here. You build the module zip yourself (a few minutes, see
> [Build the module](#build-the-module)), from your own phone or from Google's OTA.

## Prerequisites

1. **Pixel 9a** on one of the Android builds listed below.
2. **Root** with **KernelSU** (tested) or **Magisk** (untested).
3. **overlayfs support for modules:**
   * **KernelSU:** install the **meta-overlayfs** metamodule (from the
     [KernelSU](https://kernelsu.org) project) **first**, and reboot. Without a metamodule,
     KernelSU installs this module but can't mount its files, so nothing changes. If you
     installed this module before meta-overlayfs, install it again afterwards.
   * **Magisk:** nothing extra; Magisk mounts module files itself.
4. **A PC** to build the module: Python 3.10+, Java 17+,
   [apktool](https://apktool.org/) 3.x, Android SDK build-tools, and adb
   ([platform-tools](https://developer.android.com/tools/releases/platform-tools)).

## Which release do I need?

Find your build in *Settings → About phone → Build number* (and *Android version → Android
security update*), then use the matching release from [Releases](../../releases).

| Release | Android | Build number | Security patch | Stock launcher SHA-256 |
|---|---|---|---|---|
| [`v3.2-CP4A.261105.040.A1`](../../releases/tag/v3.2-CP4A.261105.040.A1) | Android 17 | `CP4A.261105.040.A1` | November 2026 (`2026-11-05`) | `bb41ffda…` |
| [`v3.2-CP3A.261005.005`](../../releases/tag/v3.2-CP3A.261005.005) | Android 17 | `CP3A.261005.005` | October 2026 (`2026-10-05`) | `9806f0ca…` |

Your build isn't listed? It hasn't been tested. The builder may still work: if Google changed
the launcher code, it stops without making a zip.

## Build the module

1. Download the **Source code (zip)** of your release and unzip it.
2. Download [apktool](https://apktool.org/) 3.x and save it as `tools/apktool.jar`.
3. Build it, either way:
   * **From your phone** (easiest): turn on USB debugging, connect the phone and run
     ```bash
     python build_module.py
     ```
     Root isn't needed for this step.
   * **From Google's full OTA** for your build
     ([developers.google.com/android/ota#tegu](https://developers.google.com/android/ota#tegu),
     also needs 7-Zip):
     ```bash
     python build_module.py --ota tegu-ota-<build>-<hash>.zip
     ```
   If build-tools aren't found, add `--build-tools <sdk>/build-tools/<version>`.
4. Check that the printed `stock launcher` SHA-256 matches your release (table above).
   The module is in `out/TwoButtonNav-tegu-<build>-<version>.zip`.

The first build creates a signing key in `keystore/`. Keep it, and use the same key for later
builds (see [BUILDING.md](BUILDING.md#signing-key)).

## Install

1. Meet the [prerequisites](#prerequisites) (KernelSU: meta-overlayfs first, then reboot).
2. KernelSU / Magisk → Modules → Install → choose the zip you built.
3. Reboot. About 30 seconds after boot the module:
   * switches the phone to 2-button navigation (first boot only),
   * compiles the patched launcher once, which may reload the home screen.

Switch modes any time in *Settings → System → Navigation mode*, or with the module's
**Action** button (2-button ↔ gestures).

## After a monthly update

An OTA removes root and changes the Pixel Launcher. When the module sees a launcher it wasn't
built for, it turns its launcher patch **off by itself** and switches you to gestures, so
nothing breaks. After re-rooting, build and install the module again for your new build.

## Troubleshooting

* **Nothing changed after reboot (KernelSU):** meta-overlayfs is missing, or was installed
  after this module. Install meta-overlayfs, reboot, reinstall this module, reboot.
* **Back to gestures:** *Settings → System → Navigation mode*, or
  `adb shell cmd overlay enable-exclusive --category com.android.internal.systemui.navbar.gestural`
* **Uninstall:** remove the module in KernelSU / Magisk and reboot; navigation returns to gestures.
* **Logs:** `/data/adb/modules/two_button_navigation_launcher/guard.log` and `twobutton.log`

## How it works

Since Android 16/17 the phone navigation bar is drawn by the **Pixel Launcher's taskbar
code**, not SystemUI, and it only creates buttons in 3-button mode. A framework overlay alone
therefore only gives a pill with no back button.

The module contains the framework's 2-button overlay plus a **patched copy of the Pixel
Launcher** from the matching Android build:

| # | Change |
|---|---|
| P1 | The taskbar draws back + home in 2-button mode |
| P2 | Taps on the bar reach the buttons; only a real swipe becomes a gesture |
| P3 | The Recents button is hidden (and stays hidden across lock/unlock) |
| P4 | Swipe up opens recents; a sideways swipe with nowhere to go springs back |
| P5 | Gestures start immediately (gesture mode's touch threshold instead of 3×) |

The installer and a boot-time check both verify the stock launcher's SHA-256, so the patched
launcher only ever runs on the exact build it was made from. Android keeps the launcher's
data (your home screen layout) even though its signature changes.

Maintainers: see [BUILDING.md](BUILDING.md) to build a release for a new Android build, and
[CHANGELOG.md](CHANGELOG.md) for changes.

## Credits

* The 2-button navigation overlay comes from rwilco12's Android 12/13 module, repackaged with
  a newer signature.
* [apktool](https://github.com/iBotPeaches/Apktool) for decoding and rebuilding the launcher.

## License

[MIT](LICENSE), for this project's scripts and patches. The Pixel Launcher belongs to Google
and is never included here; the bundled 2-button overlay keeps its original authors' terms.

## Disclaimer

Modifying system apps can break things. Use at your own risk, and keep a way to recover
(USB debugging, or KernelSU/Magisk safe mode).
