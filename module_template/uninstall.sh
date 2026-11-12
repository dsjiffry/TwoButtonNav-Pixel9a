#!/system/bin/sh
# Return to gesture navigation after the module is removed.
(
  until [ "$(getprop sys.boot_completed)" = "1" ]; do sleep 2; done
  sleep 10
  cmd overlay enable-exclusive --category com.android.internal.systemui.navbar.gestural
) &
