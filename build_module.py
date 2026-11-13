#!/usr/bin/env python3
"""
Build a Magisk/KernelSU module that restores Android 9-style 2-button navigation
(back + home pill, swipe up for recents) on Android 17 Pixels.

On Android 16+/17 the phone nav bar is drawn by the Pixel Launcher's taskbar code,
which only creates buttons in 3-button mode. This script patches YOUR phone's own
Pixel Launcher so that 2-button mode works again:

  P1 TaskbarActivityContext.isThreeButtonNav()  -> true for any non-gesture mode
                                                   (taskbar draws back/home)
  P2 RecentsAnimationDeviceState.isInDeferredGestureRegion() -> true in 2-button
                                                   mode (a tap reaches the buttons,
                                                   a swipe still becomes a gesture)
  P3 after mRecentsButton is created -> hide it in 2-button mode (keeps slot)
  P4 AbsSwipeUpHandler.getHomeTarget() -> when not fully gestural: RECENTS if the
                                                   swipe went up, else LAST_TASK
                                                   (swipe up = recents, tap = home)
  P5 RecentsAnimationDeviceState.getTouchSlop() -> gestural 1.414x slop in 2-button
                                                   mode instead of 3x (swipes start
                                                   sooner; taps still reach buttons)

Pixel 9a (tegu) only. Builds are refused for any other device.

Usage:
  python build_module.py --ota tegu-ota-<build>.zip      # from Google's full OTA (recommended)
  python build_module.py                                 # from a connected Pixel 9a (adb)
  python build_module.py --apk NexusLauncherRelease.apk \\
      --device-path /system_ext/priv-app/NexusLauncherRelease/NexusLauncherRelease.apk \\
      --built-for google/tegu/tegu:17/<BUILD_ID>/<incremental>:user/release-keys

Output: out/TwoButtonNav-tegu-<BUILD_ID>-<version>.zip (+ .sha256)

Requirements: Python 3.10+ (3.14+ for zstd OTAs), Java 17+, apktool 3.x jar
(tools/apktool.jar), Android build-tools (zipalign, apksigner); adb for phone
input; 7-Zip for OTA input.
"""
import argparse, glob, hashlib, os, re, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# Release metadata: bump VERSION / VERSION_CODE when the patches or scripts change.
VERSION = "v3.2"
VERSION_CODE = 320
MODULE_ID = "two_button_navigation_launcher"
AUTHOR = "TwoButtonNav-Pixel9a contributors"
DEVICE = "tegu"  # Pixel 9a only
LAUNCHER_PKG = "com.google.android.apps.nexuslauncher"
HELPER = "Lcom/twobtn/TwoButtonPatch;->hideRecentsIfTwoButton(Landroid/view/View;)V"
NAVMODE = "Lcom/android/launcher3/util/NavigationMode;"
# P4: minimum swipe-up progress (mCurrentShift, 0..1) for a 2-button swipe to open recents.
P4_MIN_SHIFT = 0.06
P4_MIN_SHIFT_HEX = "0x%08x" % __import__("struct").unpack(">I", __import__("struct").pack(">f", P4_MIN_SHIFT))[0]


RELEASE_NOTES = """\
# Two-Button Navigation {version} for Pixel 9a · Android {android} {build_id} ({month})

> [!IMPORTANT]
> **Only for the Pixel 9a (`tegu`) running exactly this Android version:**
>
> | | |
> |---|---|
> | Android version | **Android {android}** |
> | Build number | **`{build_id}`** |
> | Security patch | **{month}** (`{sec_patch}`) |
> | Build fingerprint | `{fingerprint}` |
>
> Check *Settings → About phone → Android version / Build number*. A module built for this
> release only installs on this build; on any other build the installer stops without changing
> anything. Only tested on a Pixel 9a.

**There is no prebuilt zip.** The module contains a patched copy of Google's Pixel Launcher,
so you build it yourself on your PC from your own phone or from Google's OTA. The result is a
normal KernelSU / Magisk module zip.

## Prerequisites

On the phone:

* Root with **KernelSU** (tested) or **Magisk** (untested)
* **overlayfs**: on KernelSU, install the **meta-overlayfs** metamodule *before* this module
  and reboot. Without a metamodule, KernelSU can't mount the module's files and nothing changes.
  Magisk mounts modules itself and needs nothing extra.

On the PC: Python 3.10+, Java 17+, [apktool](https://apktool.org/) 3.x saved as
`tools/apktool.jar`, Android SDK build-tools, and adb (or 7-Zip for the OTA route).

## Build

1. Download this release's **Source code (zip)** below and unzip it.
2. Build the module, either way:
   * **From your phone** (USB debugging on, no root needed): `python build_module.py`
   * **From Google's full OTA** for `{build_id}` (developers.google.com/android/ota#tegu):
     `python build_module.py --ota tegu-ota-{build_id_lower}-<hash>.zip`
3. Check that the builder prints this stock launcher SHA-256. If it differs, your phone isn't
   on `{build_id}`:
   `{stock_sha}`

The module is written to `out/{zip}`.

## Install

1. KernelSU / Magisk → Modules → Install → `{zip}`
2. Reboot. About 30 seconds after boot the phone switches to 2-button navigation and the
   patched launcher is compiled once (the home screen may reload).
"""


class PatchError(Exception):
    pass


# ----------------------------------------------------------------------------- tools
def run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd))
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.stdout.write(r.stdout[-3000:]); sys.stderr.write(r.stderr[-3000:])
        raise SystemExit(f"command failed ({r.returncode}): {cmd[0]}")
    return r.stdout


def find_build_tools(arg):
    cands = [arg] if arg else []
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(env):
            cands += sorted(glob.glob(os.path.join(os.environ[env], "build-tools", "*")), reverse=True)
    cands += sorted(glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\build-tools\*")), reverse=True)
    cands += sorted(glob.glob(os.path.expanduser("~/Android/Sdk/build-tools/*")), reverse=True)
    for c in cands:
        if c and (Path(c) / "lib" / "apksigner.jar").exists():
            return Path(c)
    raise SystemExit("Android build-tools not found; pass --build-tools <dir>")


def find_apktool(arg):
    for c in [arg, os.environ.get("APKTOOL_JAR"), HERE / "tools" / "apktool.jar"]:
        if c and Path(c).exists():
            return Path(c)
    raise SystemExit("apktool jar not found; pass --apktool <apktool.jar> or put it in tools/apktool.jar")


def find_adb(arg):
    if arg:
        return arg
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(env):
            p = Path(os.environ[env]) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
            if p.exists():
                return str(p)
    p = Path(os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"))
    return str(p) if p.exists() else "adb"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ----------------------------------------------------------------------------- smali helpers
def find_class(root, cls):
    """cls like com/android/quickstep/AbsSwipeUpHandler"""
    hits = [p for p in root.glob(f"smali*/{cls}.smali")]
    if len(hits) != 1:
        raise PatchError(f"class {cls} found {len(hits)} times")
    return hits[0]


def method_span(text, name_re):
    m = re.search(r"^\.method [^\n]*\b" + name_re + r"\n", text, re.M)
    if not m:
        raise PatchError(f"method {name_re} not found")
    end = text.index("\n.end method", m.end())
    return m.start(), end


def ensure_locals(body, need, label):
    m = re.search(r"^(\s*)\.locals (\d+)$", body, re.M)
    if not m:
        raise PatchError(f"{label}: no .locals directive")
    n = int(m.group(2))
    if n < need:
        body = body[:m.start()] + f"{m.group(1)}.locals {need}" + body[m.end():]
    return body, m


def insert_after_locals(body, code, need, label):
    body, _ = ensure_locals(body, need, label)
    m = re.search(r"^\s*\.locals \d+\n", body, re.M)
    return body[:m.end()] + code + body[m.end():]


# ----------------------------------------------------------------------------- patches
def p1_three_button(root):
    f = find_class(root, "com/android/launcher3/taskbar/TaskbarActivityContext")
    t = f.read_text(encoding="utf-8")
    s, e = method_span(t, r"isThreeButtonNav\(\)Z")
    body = t[s:e]
    if body.count(f"{NAVMODE}->THREE_BUTTONS:") != 1:
        raise PatchError("P1: unexpected isThreeButtonNav() shape")
    ops = re.findall(r"\bif-(ne|eq) ", body)
    if len(ops) != 1:
        raise PatchError("P1: expected exactly one comparison in isThreeButtonNav()")
    body = body.replace(f"{NAVMODE}->THREE_BUTTONS:", f"{NAVMODE}->NO_BUTTON:")
    body = re.sub(r"\bif-(ne|eq) ", lambda m: "if-eq " if m.group(1) == "ne" else "if-ne ", body)
    f.write_text(t[:s] + "    # 2BTN-PATCH P1\n" + body + t[e:], encoding="utf-8")
    return str(f.relative_to(root))


def p2_deferred_region(root):
    f = find_class(root, "com/android/quickstep/RecentsAnimationDeviceState")
    t = f.read_text(encoding="utf-8")
    if not re.search(rf"^\.field [^\n]* mMode:{re.escape(NAVMODE)}$", t, re.M):
        raise PatchError("P2: field mMode not found")
    s, e = method_span(t, r"isInDeferredGestureRegion\(Landroid/view/MotionEvent;\)Z")
    code = (
        "\n    # 2BTN-PATCH P2: defer every touch in 2-button mode so taps reach the buttons\n"
        f"    iget-object v0, p0, Lcom/android/quickstep/RecentsAnimationDeviceState;->mMode:{NAVMODE}\n\n"
        f"    sget-object v1, {NAVMODE}->TWO_BUTTONS:{NAVMODE}\n\n"
        "    if-ne v0, v1, :twobtn_p2_orig\n\n"
        "    const/4 v0, 0x1\n\n"
        "    return v0\n\n"
        "    :twobtn_p2_orig\n"
    )
    body = insert_after_locals(t[s:e], code, 2, "P2")
    f.write_text(t[:s] + body + t[e:], encoding="utf-8")
    return str(f.relative_to(root))


def p3_hide_recents(root):
    pat = re.compile(
        r"^(\s*)iput-object ([vp]\d+), [vp]\d+, Lcom/android/launcher3/taskbar/NavbarButtonsViewController;"
        r"->mRecentsButton:Landroid/widget/ImageView;\n", re.M)
    files = []
    for f in root.glob("smali*/**/*.smali"):
        t = f.read_text(encoding="utf-8")
        if "->mRecentsButton:Landroid/widget/ImageView;" not in t:
            continue
        new, n = pat.subn(
            lambda m: m.group(0) + f"\n{m.group(1)}# 2BTN-PATCH P3\n"
                      f"{m.group(1)}invoke-static/range {{{m.group(2)} .. {m.group(2)}}}, {HELPER}\n", t)
        if n:
            f.write_text(new, encoding="utf-8")
            files.append(f"{f.relative_to(root)} x{n}")
    if not files:
        raise PatchError("P3: mRecentsButton assignment not found")
    return ", ".join(files)


def p4_swipe_recents(root):
    f = find_class(root, "com/android/quickstep/AbsSwipeUpHandler")
    t = f.read_text(encoding="utf-8")
    if "Lcom/android/quickstep/AbsSwipeUpHandler;->mDeviceState:Lcom/android/quickstep/RecentsAnimationDeviceState;" not in t:
        raise PatchError("P4: mDeviceState field not found")
    s, e = method_span(t, r"getHomeTarget\(\)Lcom/android/quickstep/GestureState\$GestureEndTarget;")
    code = (
        "\n    # 2BTN-PATCH P4: when not fully gestural, a swipe that went up = recents;\n"
        "    # a mostly sideways swipe (e.g. past the last app) springs back instead\n"
        "    iget-object v0, p0, Lcom/android/quickstep/AbsSwipeUpHandler;->mDeviceState:Lcom/android/quickstep/RecentsAnimationDeviceState;\n\n"
        "    invoke-virtual {v0}, Lcom/android/quickstep/RecentsAnimationDeviceState;->isFullyGesturalNavMode()Z\n\n"
        "    move-result v0\n\n"
        "    if-nez v0, :twobtn_p4_orig\n\n"
        "    iget-object v0, p0, Lcom/android/quickstep/SwipeUpAnimationLogic;->mCurrentShift:Lcom/android/launcher3/anim/AnimatedFloat;\n\n"
        "    iget v0, v0, Lcom/android/launcher3/anim/AnimatedFloat;->value:F\n\n"
        f"    const v1, {P4_MIN_SHIFT_HEX}    # {P4_MIN_SHIFT}f\n\n"
        "    cmpl-float v0, v0, v1\n\n"
        "    if-ltz v0, :twobtn_p4_stay\n\n"
        "    sget-object v0, Lcom/android/quickstep/GestureState$GestureEndTarget;->RECENTS:Lcom/android/quickstep/GestureState$GestureEndTarget;\n\n"
        "    return-object v0\n\n"
        "    :twobtn_p4_stay\n"
        "    sget-object v0, Lcom/android/quickstep/GestureState$GestureEndTarget;->LAST_TASK:Lcom/android/quickstep/GestureState$GestureEndTarget;\n\n"
        "    return-object v0\n\n"
        "    :twobtn_p4_orig\n"
    )
    if "Lcom/android/quickstep/SwipeUpAnimationLogic;" not in t.split("\n", 3)[1]:
        raise PatchError("P4: AbsSwipeUpHandler no longer extends SwipeUpAnimationLogic")
    body = insert_after_locals(t[s:e], code, 2, "P4")
    f.write_text(t[:s] + body + t[e:], encoding="utf-8")
    return str(f.relative_to(root))


def p5_touch_slop(root):
    """2-button mode uses a 3x touch slop (vs 1.414x gestural). With the deferred
    region (P2) every swipe waits for that slop before the animation starts, so
    use the gestural multiplier in 2-button mode. 3-button mode is unchanged."""
    f = find_class(root, "com/android/quickstep/RecentsAnimationDeviceState")
    t = f.read_text(encoding="utf-8")
    s, e = method_span(t, r"getTouchSlop\(\)F")
    body = t[s:e]
    hits = list(re.finditer(r"^(\s*)const/high16 (v\d+), 0x40400000(\s*# 3\.0f)?$", body, re.M))
    if len(hits) != 1 or "0x3fb4fdf4" not in body:
        raise PatchError("P5: unexpected getTouchSlop() shape")
    ind, reg = hits[0].group(1), hits[0].group(2)
    tmp = "v1" if reg != "v1" else "v0"
    code = (
        f"{ind}# 2BTN-PATCH P5: gestural touch slop in 2-button mode\n"
        f"{ind}iget-object {reg}, p0, Lcom/android/quickstep/RecentsAnimationDeviceState;->mMode:{NAVMODE}\n\n"
        f"{ind}sget-object {tmp}, {NAVMODE}->TWO_BUTTONS:{NAVMODE}\n\n"
        f"{ind}if-ne {reg}, {tmp}, :twobtn_p5_3x\n\n"
        f"{ind}const {reg}, 0x3fb4fdf4    # 1.414f\n\n"
        f"{ind}goto :twobtn_p5_done\n\n"
        f"{ind}:twobtn_p5_3x\n"
        f"{ind}const/high16 {reg}, 0x40400000    # 3.0f\n\n"
        f"{ind}:twobtn_p5_done"
    )
    body = body[:hits[0].start()] + code + body[hits[0].end():]
    body, _ = ensure_locals(body, 2, "P5")
    f.write_text(t[:s] + body + t[e:], encoding="utf-8")
    return str(f.relative_to(root))


def add_helper(root):
    nums = [int(m.group(1) or 1) for d in root.glob("smali*")
            if (m := re.fullmatch(r"smali(?:_classes(\d+))?", d.name))]
    d = root / f"smali_classes{max(nums) + 1}" / "com" / "twobtn"
    d.mkdir(parents=True)
    for f in sorted((HERE / "patch").glob("*.smali")):
        shutil.copy(f, d / f.name)
    return f"{d.relative_to(root)} ({len(list(d.glob('*.smali')))} classes)"


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ota", help="Pixel 9a full OTA zip (tegu-ota-*.zip) to take the launcher from")
    ap.add_argument("--apk", help="stock Pixel Launcher APK (default: pull from connected phone)")
    ap.add_argument("--device-path", help="on-device path of the stock APK (needed with --apk)")
    ap.add_argument("--built-for", default=None, help="full build fingerprint (needed with --apk)")
    ap.add_argument("--security-patch", default=None, help="security patch level YYYY-MM-DD (needed with --apk)")
    ap.add_argument("--serial", help="adb serial")
    ap.add_argument("--adb"); ap.add_argument("--apktool"); ap.add_argument("--build-tools")
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--keep-work", action="store_true")
    a = ap.parse_args()

    bt, apktool, adb = find_build_tools(a.build_tools), find_apktool(a.apktool), find_adb(a.adb)
    adbc = [adb] + (["-s", a.serial] if a.serial else [])
    work = Path(tempfile.mkdtemp(prefix="twobtn_"))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    print(f"work dir: {work}")

    # 1. stock APK
    if a.ota:
        import ota_extract
        meta = ota_extract.ota_metadata(a.ota)
        if meta.get("pre-device") != DEVICE:
            raise SystemExit(f"OTA is for '{meta.get('pre-device')}', this project only supports {DEVICE} (Pixel 9a)")
        if "pre-build" in meta:
            raise SystemExit("this is an incremental OTA; use the full OTA zip")
        stock, built_for, _ = ota_extract.extract_launcher(a.ota, work / "ota")
        dev_path = "/system_ext/" + ota_extract.LAUNCHER_IN_SYSTEM_EXT
        sec_patch = meta.get("post-security-patch-level", "")
    elif a.apk:
        if not a.device_path or not a.built_for or not a.security_patch:
            raise SystemExit("--apk needs --device-path, --built-for <full build fingerprint> and --security-patch YYYY-MM-DD")
        stock, dev_path = Path(a.apk), a.device_path
        built_for, sec_patch = a.built_for, a.security_patch
    else:
        paths = [l[8:].strip() for l in run(adbc + ["shell", "pm", "path", LAUNCHER_PKG]).splitlines() if l.startswith("package:")]
        if len(paths) != 1:
            raise SystemExit(f"expected one APK for {LAUNCHER_PKG}, got {paths}")
        dev_path = paths[0]
        if dev_path.startswith("/data/"):
            raise SystemExit("The Pixel Launcher was updated through the Play Store (lives in /data). "
                             "Uninstall its updates first so the system copy is the active one.")
        stock = work / "stock.apk"
        run(adbc + ["pull", dev_path, str(stock)])
        built_for = a.built_for or run(adbc + ["shell", "getprop", "ro.build.fingerprint"]).strip()
        sec_patch = run(adbc + ["shell", "getprop", "ro.build.version.security_patch"]).strip()
    fp = re.fullmatch(r"google/([^/]+)/([^/:]+):(\d+)/([^/]+)/[^/]+:user/release-keys", built_for)
    if not fp or fp.group(1) != DEVICE or fp.group(2) != DEVICE:
        raise SystemExit(f"build fingerprint '{built_for}' is not a Pixel 9a ({DEVICE}) release build; "
                         "this project only supports the Pixel 9a")
    android, build_id = fp.group(3), fp.group(4)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", sec_patch or ""):
        raise SystemExit(f"bad security patch level '{sec_patch}' (expected YYYY-MM-DD)")
    month = __import__("datetime").date.fromisoformat(sec_patch).strftime("%B %Y")
    os_label = f"Android {android} ({build_id}, {month} security patch {sec_patch})"
    m = re.fullmatch(r"/(.+)/([^/]+\.apk)", dev_path)
    if not m:
        raise SystemExit(f"unexpected device path {dev_path}")
    rel_dir, apk_name = m.group(1), m.group(2)
    stock_sha = sha256(stock)
    print(f"stock: {dev_path}\n  sha256 {stock_sha}\n  built for {built_for}")

    # 2. decode + patch
    dec = work / "dec"
    run(["java", "-jar", apktool, "d", "-r", "-f", "-o", dec, stock])
    try:
        for name, fn in [("P1 isThreeButtonNav", p1_three_button), ("P2 deferred region", p2_deferred_region),
                         ("P3 hide recents", p3_hide_recents), ("P4 swipe->recents", p4_swipe_recents),
                         ("P5 touch slop", p5_touch_slop), ("helper class", add_helper)]:
            print(f"  {name}: {fn(dec)}")
    except PatchError as e:
        raise SystemExit(f"PATCH FAILED: {e}\nThis launcher build differs from the tested one; no module was built.")

    # 3. build, align, sign
    unsigned, aligned, signed = work / "u.apk", work / "a.apk", work / apk_name
    run(["java", "-jar", apktool, "b", dec, "-o", unsigned])
    run([bt / ("zipalign.exe" if os.name == "nt" else "zipalign"), "-f", "-p", "4", unsigned, aligned])
    # Signing key: private, never committed (keystore/ is gitignored). Created on first run.
    ks = Path(os.environ.get("TWOBTN_KEYSTORE", HERE / "keystore" / "twobtn.p12"))
    ks_pass = os.environ.get("TWOBTN_KEYSTORE_PASS", "twobutton")
    if not ks.exists():
        ks.parent.mkdir(parents=True, exist_ok=True)
        run(["keytool", "-genkeypair", "-keystore", ks, "-storetype", "PKCS12", "-storepass", ks_pass,
             "-alias", "twobtn", "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
             "-dname", "CN=TwoButtonNav Launcher Patch"])
    run(["java", "-jar", bt / "lib" / "apksigner.jar", "sign", "--ks", ks, "--ks-pass", f"pass:{ks_pass}",
         "--ks-key-alias", "twobtn", "--out", signed, aligned])
    run(["java", "-jar", bt / "lib" / "apksigner.jar", "verify", signed])
    patched_sha = sha256(signed)

    # 4. module
    mod = work / "module"
    shutil.copytree(HERE / "module_template", mod)
    dest = mod / "system" / rel_dir
    dest.mkdir(parents=True)
    shutil.copy(signed, dest / apk_name)
    (dest / ".replace").write_text("")  # hide stock oat/odex so ART doesn't use stale code
    desc_ok = (f"2-button navigation (back + home) for Pixel 9a. ONLY for {os_label}. "
               "Requires overlayfs (KernelSU: meta-overlayfs metamodule).")
    (mod / "launcher.conf").write_text(
        f'DEVICE="{DEVICE}"\nLAUNCHER_REL="{rel_dir}"\nLAUNCHER_APK="{apk_name}"\nSTOCK_SHA256="{stock_sha}"\n'
        f'PATCHED_SHA256="{patched_sha}"\nBUILT_FOR="{built_for}"\nBUILD_ID="{build_id}"\n'
        f'SECURITY_PATCH="{sec_patch}"\nOS_LABEL="{os_label}"\nDESC_OK="{desc_ok}"\n', newline="\n")
    (mod / "module.prop").write_text(
        f"id={MODULE_ID}\nname=Two-Button Navigation for Pixel 9a (Android 17)\n"
        f"version={VERSION}-{build_id}\nversionCode={VERSION_CODE}\nauthor={AUTHOR}\n"
        f"description={desc_ok}\n", newline="\n")
    zpath = out / f"TwoButtonNav-{DEVICE}-{build_id}-{VERSION}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(mod.rglob("*")):
            if p.is_file():
                arc = p.relative_to(mod).as_posix()
                zi = zipfile.ZipInfo(arc, (2026, 1, 1, 0, 0, 0))
                zi.external_attr = (0o100755 if arc.endswith(".sh") or arc.endswith("update-binary") else 0o100644) << 16
                zi.compress_type = zipfile.ZIP_STORED if arc.endswith(".apk") else zipfile.ZIP_DEFLATED
                data = p.read_bytes()
                if arc.endswith(".sh") or arc.endswith(".conf") or arc.endswith("update-binary"):
                    data = data.replace(b"\r\n", b"\n")
                z.writestr(zi, data)
    zsha = sha256(zpath)
    (out / (zpath.name + ".sha256")).write_text(f"{zsha}  {zpath.name}\n", newline="\n")
    tag = f"{VERSION}-{build_id}"
    notes = out / f"release-notes-{tag}.md"
    notes.write_text(RELEASE_NOTES.format(
        version=VERSION, build_id=build_id, android=android, month=month, sec_patch=sec_patch,
        fingerprint=built_for, zip=zpath.name, stock_sha=stock_sha, build_id_lower=build_id.lower()),
        encoding="utf-8", newline="\n")
    print(f"\nMODULE: {zpath}\n  release tag     {tag}\n  release notes   {notes}\n"
          f"  OS              {os_label}\n  zip sha256      {zsha}\n  stock launcher  {stock_sha}\n"
          f"  patched launcher {patched_sha}")
    if not a.keep_work:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
