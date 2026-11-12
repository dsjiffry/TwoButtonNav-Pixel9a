#!/system/bin/sh
# Runs before Magisk/KernelSU mounts module files.
# Safety guard: only replace the launcher if the phone's stock Pixel Launcher is
# exactly the one this module was built from. After an OTA changes it, the
# patched copy is parked (not mounted) until you rebuild the module.
MODDIR=${0%/*}
. "$MODDIR/launcher.conf"

LOG="$MODDIR/guard.log"
ACTIVE="$MODDIR/system/$LAUNCHER_REL"
PARKED="$MODDIR/parked_launcher"
STOCK="/$LAUNCHER_REL/$LAUNCHER_APK"

cur=$(sha256sum "$STOCK" 2>/dev/null | cut -d' ' -f1)
echo "$(date) stock=$cur expected=$STOCK_SHA256" > "$LOG"

set_desc() {
  sed -i "s|^description=.*|description=$1|" "$MODDIR/module.prop"
}

if [ "$cur" = "$STOCK_SHA256" ] || [ "$cur" = "$PATCHED_SHA256" ]; then
  if [ ! -d "$ACTIVE" ] && [ -d "$PARKED" ]; then
    mkdir -p "${ACTIVE%/*}"
    mv "$PARKED" "$ACTIVE"
  fi
  echo "launcher patch ACTIVE" >> "$LOG"
  set_desc "$DESC_OK"
else
  if [ -d "$ACTIVE" ]; then
    rm -rf "$PARKED"
    mv "$ACTIVE" "$PARKED"
  fi
  echo "stock launcher changed (OTA?) - patch PARKED, rebuild the module" >> "$LOG"
  set_desc "WARNING: Pixel Launcher changed since this module was built (system update?). Launcher patch is OFF. Re-run build_module.py and flash the new zip."
fi
