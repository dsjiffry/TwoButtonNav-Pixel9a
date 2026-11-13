# Magisk / KernelSU / APatch install script
. "$MODPATH/launcher.conf"

ui_print "**********************************************"
ui_print "  Two-Button Navigation for Pixel 9a (A17)"
ui_print "  (patched Pixel Launcher + 2-button overlay)"
ui_print "**********************************************"
ui_print "- Requires: Pixel 9a, $OS_LABEL"
ui_print "- This phone: $(getprop ro.product.model), Android $(getprop ro.build.version.release) ($(getprop ro.build.id), patch $(getprop ro.build.version.security_patch))"

# Pixel 9a only.
dev=$(getprop ro.product.device)
if [ "$dev" != "$DEVICE" ]; then
  abort "! This module is for the Pixel 9a ($DEVICE) only. This device is '$dev'."
fi

# Exact Android build only.
if [ "$(getprop ro.build.id)" != "$BUILD_ID" ]; then
  abort "! Wrong Android build: this zip is ONLY for $OS_LABEL. Build the module for build $(getprop ro.build.id) from the matching release."
fi

# KernelSU needs an overlayfs metamodule (e.g. meta-overlayfs) to mount module files.
if [ "$KSU" = "true" ]; then
  if ls /data/adb/modules/*/metamount.sh /data/adb/modules_update/*/metamount.sh >/dev/null 2>&1; then
    ui_print "- overlayfs metamodule found"
  else
    ui_print "!"
    ui_print "! No overlayfs metamodule found (e.g. meta-overlayfs)."
    ui_print "! KernelSU can't mount this module without one: install"
    ui_print "! meta-overlayfs, reboot, then install this module again."
    ui_print "!"
  fi
fi

STOCK="/$LAUNCHER_REL/$LAUNCHER_APK"
if [ -f "$STOCK" ]; then
  cur=$(sha256sum "$STOCK" | cut -d' ' -f1)
  if [ "$cur" != "$STOCK_SHA256" ] && [ "$cur" != "$PATCHED_SHA256" ]; then
    abort "! This zip is for build $(echo "$BUILT_FOR" | cut -d/ -f4). Your Pixel Launcher differs: build the module again for your build."
  fi
  ui_print "- Stock launcher matches the build"
else
  abort "! $STOCK not found on this device"
fi

# Remove earlier 2-button modules that ship the same overlay.
for old in two_button_navigation Android13_Two-Button_Navigation_Standard Android12_Two-Button_Navigation_Standard; do
  if [ -d "/data/adb/modules/$old" ]; then
    ui_print "- Marking old module '$old' for removal"
    touch "/data/adb/modules/$old/remove"
  fi
done

# If the ROM already ships its own 2-button overlay, don't add a duplicate.
stock_overlay=$(pm path com.android.internal.systemui.navbar.twobutton 2>/dev/null | grep -v NavigationBarMode2ButtonOverlay/)
if [ -n "$stock_overlay" ]; then
  ui_print "- ROM already has a 2-button overlay, using it"
  rm -rf "$MODPATH/system/product"
fi

set_perm_recursive "$MODPATH" 0 0 0755 0644
[ -d "$MODPATH/system/product" ] && set_perm_recursive "$MODPATH/system/product" 0 0 0755 0644 u:object_r:system_file:s0
set_perm_recursive "$MODPATH/system/$LAUNCHER_REL" 0 0 0755 0644 u:object_r:system_file:s0

ui_print "- Reboot. 2-button mode turns on ~10-30 s after boot."
ui_print "- Action button toggles 2-button / gestures."
ui_print "- If a system update changes the launcher, the patch switches"
ui_print "  itself off; rebuild the zip for the new build."
