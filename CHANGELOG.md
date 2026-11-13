# Changelog

## v3.2
* Swipes start right away. 2-button mode used a 3× touch threshold, which delayed every
  gesture by 50–120 ms and made quick-switch flicks fail (P5).
* A sideways swipe with no app to switch to springs back instead of opening recents (P4).
* The patched launcher is compiled once on first boot, so it doesn't run slow uncompiled
  code until the overnight compile job.
* The installer shows the exact Android version each zip requires, refuses other builds and
  devices, and on KernelSU warns if no overlayfs metamodule (meta-overlayfs) is installed.
* Builder: build straight from a Pixel 9a full OTA (`--ota`); Pixel 9a only.
* Releases are source only: you build the module zip yourself (no patched Google launcher is
  published). MIT license.

## v3.1
* The Recents button no longer reappears after locking/unlocking (P3: no icon, swallows touches).

## v3.0
* First patched-launcher release: back + home buttons in 2-button mode on Android 17 (P1–P4).
* Boot-time guard parks the patch automatically after an OTA.
