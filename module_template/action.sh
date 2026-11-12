#!/system/bin/sh
# Toggle between 2-button and gesture navigation (Magisk v28+ / KernelSU "Action" button).
TWO=com.android.internal.systemui.navbar.twobutton
GEST=com.android.internal.systemui.navbar.gestural
THREE=com.android.internal.systemui.navbar.threebutton

state=$(cmd overlay list 2>/dev/null | grep "$TWO")
if [ -z "$state" ]; then
  echo "! Overlay $TWO not found. Reboot after installing the module."
  exit 1
fi

if echo "$state" | grep -q '\[x\]'; then
  if cmd overlay list | grep -q "$GEST"; then target=$GEST; else target=$THREE; fi
  echo "- 2-button is ON, switching to $target"
else
  target=$TWO
  echo "- Switching to 2-button navigation"
fi
cmd overlay enable-exclusive --category "$target" && echo "- Done"
cmd overlay list | grep -i navbar
