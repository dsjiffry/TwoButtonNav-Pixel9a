#!/system/bin/sh
# Turns on 2-button mode once after install (later choices in Settings are respected).
MODDIR=${0%/*}
PKG=com.android.internal.systemui.navbar.twobutton
LOG="$MODDIR/twobutton.log"

until [ "$(getprop sys.boot_completed)" = "1" ]; do sleep 2; done
sleep 5

i=0
until cmd overlay list 2>/dev/null | grep -q "$PKG"; do
  i=$((i + 1)); [ $i -ge 30 ] && break; sleep 2
done

{
  echo "=== $(date) | API $(getprop ro.build.version.sdk) | $(getprop ro.build.fingerprint)"
  cmd overlay list 2>&1 | grep -i 'navbar'
} > "$LOG"

if ! cmd overlay list 2>/dev/null | grep -q "$PKG"; then
  echo "ERROR: overlay $PKG not found" >> "$LOG"
  exit 0
fi

# Only switch if the launcher patch is actually active; otherwise 2-button mode
# would show just a pill with no back button.
if [ ! -d "$MODDIR/system/$(. "$MODDIR/launcher.conf"; echo "$LAUNCHER_REL")" ]; then
  echo "launcher patch parked - not enabling 2-button mode" >> "$LOG"
  # Without the patched launcher, 2-button mode has no back button: fall back to gestures.
  if cmd overlay list 2>/dev/null | grep -q "\[x\] $PKG"; then
    cmd overlay enable-exclusive --category com.android.internal.systemui.navbar.gestural >> "$LOG" 2>&1
    rm -f "$MODDIR/.applied"
    echo "switched to gestures" >> "$LOG"
  fi
  exit 0
fi

if [ ! -f "$MODDIR/.applied" ]; then
  if cmd overlay enable-exclusive --category "$PKG" >> "$LOG" 2>&1; then
    touch "$MODDIR/.applied"
    echo "enabled $PKG" >> "$LOG"
  fi
fi
cmd overlay list 2>&1 | grep -i 'navbar' >> "$LOG"

# The module hides Google's precompiled launcher code (oat/ + .prof), so a freshly
# installed patched launcher runs uncompiled (janky gestures) until the overnight
# dexopt job. Compile it once per install, then restart it so the code is used now.
LAUNCHER=com.google.android.apps.nexuslauncher
if [ ! -f "$MODDIR/.compiled" ]; then
  sleep 20
  echo "$(date) compiling $LAUNCHER (speed)..." >> "$LOG"
  if cmd package compile -m speed -f "$LAUNCHER" >> "$LOG" 2>&1; then
    touch "$MODDIR/.compiled"
    am force-stop "$LAUNCHER" >> "$LOG" 2>&1
    echo "$(date) compiled + restarted launcher" >> "$LOG"
  fi
fi
