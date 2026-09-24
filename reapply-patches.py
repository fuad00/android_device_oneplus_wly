#!/usr/bin/env python3
"""Reapply build fixes that extract-files.py regenerates away.

The generated vendor/oneplus/sm8450-common/Android.bp and the
sm8450-common/proprietary-files.txt come from pjgowtham's trees and get
regenerated on every `extract-files.py` run, so the manual fixes below
must be re-applied each time before building. Idempotent: safe to run
repeatedly.

Run: python3 reapply-patches.py <top>
"""
import re
import sys
import os

top = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
vendor_bp = os.path.join(top, "vendor/oneplus/sm8450-common/Android.bp")
common_ptxt = os.path.join(top, "device/oneplus/sm8450-common/proprietary-files.txt")


def block_range(s, start_idx, end_idx):
    """Return the text of the cc_prebuilt block starting at start_idx."""
    return s[start_idx:end_idx]


def patch_bp(path):
    s = open(path).read()
    orig = s
    # 1) olc2 / radio / charger prebuilt _ndk_platform: match their source
    #    aidl_interface partition (system_ext) so they don't collide with the
    #    platform-backend variant. Idempotent: skip if already present.
    for m in ["olc2", "radio", "charger"]:
        anchor = re.compile(
            r'cc_prebuilt_library_shared \{\n    name: "vendor\.oplus\.hardware\.'
            + m + r'-V\d+-ndk_platform",\n    owner: "oneplus",')
        am = anchor.search(s)
        if not am:
            continue
        close = s.find("\n}", am.end())
        block = s[am.end():close]
        new_block = block
        if "system_ext_specific: true," not in new_block:
            # insert right after the owner line
            new_block = new_block.replace("\n", "\n    system_ext_specific: true,", 1)
        new_block = re.sub(r"\n    (?:soc|device)_specific: true,", "", new_block)
        if new_block != block:
            s = s[:am.end()] + new_block + s[close:]
    # 2) libwfdservice: drop explicit android.media.audio.common.types-V2-cpp
    #    (conflicts with V4 pulled transitively; WFD/Miracast is non-critical).
    lib = re.compile(
        r'cc_prebuilt_library_shared \{\n    name: "libwfdservice",')
    lm = lib.search(s)
    if lm:
        close = s.find("\n}", lm.end())
        block = s[lm.end():close]
        if "android.media.audio.common.types-V2-cpp" in block:
            block2 = block.replace('                "android.media.audio.common.types-V2-cpp",\n', "")
            s = s[:lm.end()] + block2 + s[close:]
    # 3) Any prebuilt (library or binary) that links a vendor.pixelworks
    #    HIDL interface: those HIDL libs are system_ext_specific, so soong
    #    filters them out of the vendor module's shared_libs and
    #    check_elf_file then fails. Disable the check (check_elf_file's own
    #    suggestion); linker namespaces resolve it at runtime.
    blocks = re.compile(
        r'cc_prebuilt_(?:library_shared|binary) \{\n    name: "[^"]+",.*?\n\}', re.S)
    out = []
    last = 0
    for bm in blocks.finditer(s):
        blk = bm.group(0)
        if "check_elf_files: false," in blk:
            continue
        if re.search(r'"vendor\.pixelworks\.hardware\.[^"]+"', blk):
            body = blk[:-1].rstrip().rstrip(',')
            blk = body + ",\n    check_elf_files: false,\n}"
        out.append(s[last:bm.start()])
        out.append(blk)
        last = bm.end()
    out.append(s[last:])
    s = "".join(out)
    s = s.replace("true,,", "true,")
    if s != orig:
        open(path, "w").write(s)
        print(f"patched {path}")
    else:
        print(f"{path}: no changes needed")


def patch_common_ptxt(path):
    if not os.path.exists(path):
        print(f"{path}: not present, skip")
        return
    s = open(path).read()
    orig = s
    # blobs only in newer (901) base, absent in 15.0.0.700
    drops = [
        r'^odm/firmware/fastchg/charge_time_config\.csv\|[0-9a-f]{40}\n',
        r'^my_product/etc/sysconfig/com\.android\.hotwordenrollment\.common\.util\.xml[^\n]*\n',
        r'^my_product/framework/com\.android\.hotwordenrollment\.common\.util\.jar[^\n]*\n',
        r'^my_product/priv-app/HotwordEnrollmentXGoogleHEXAGON_WIDEBAND\.apk[^\n]*\n',
        r'^my_product/priv-app/HotwordEnrollmentYGoogleHEXAGON_WIDEBAND\.apk[^\n]*\n',
    ]
    for d in drops:
        s, _ = re.subn(d, "", s, flags=re.M)
    if s != orig:
        open(path, "w").write(s)
        print(f"patched {path} (dropped 15.0.0.700-absent blobs)")
    else:
        print(f"{path}: no changes needed")


def patch_vendor_mk(path):
    if not os.path.exists(path):
        print(f"{path}: not present, skip")
        return
    s = open(path).read()
    orig = s
    # WFD/Miracast stack is out of scope for this build:
    #  - wfdservice is a 32-bit prebuilt that never registers on this
    #    64-bit-only product ("non-existent module in PRODUCT_PACKAGES")
    #  - the rest (libwfd*, wfd* services, WfdService/WfdCommon apps)
    #    fails check_elf on stale surfaceflinger symbols.
    # Each entry line carries its own trailing backslash, so deleting
    # the whole line keeps the continuation chain intact. Idempotent.
    pat = re.compile(r"^[ \t]*(?:lib)?[wW]fd[a-zA-Z0-9_]*[ \t]*\\\n", re.M)
    s, n = pat.subn("", s)
    if s != orig:
        open(path, "w").write(s)
        print(f"patched {path} (dropped {n} WFD entries from product)")
    else:
        print(f"{path}: no changes needed")


def remove_euicc(top):
    # hardware/oplus/Euicc (legacy OplusEuicc app) duplicates the mainline
    # packages/apps/EuiccPolicy -> "MODULE.TARGET.ETC.hidden-api-whitelist-
    # org.lineageos.euicc.xml already defined". OplusEuicc is not in any
    # PRODUCT_PACKAGES, so removing the dir is safe.
    import shutil
    d = os.path.join(top, "hardware/oplus/Euicc")
    if os.path.isdir(d):
        shutil.rmtree(d)
        print(f"removed {d} (legacy OplusEuicc duplicates mainline EuiccPolicy)")
    else:
        print(f"{d}: already absent")


def patch_kernel_modules(top):
    # cam_req_mgr_workq.c redefines struct sched_param, which 5.10
    # include/linux/sched.h already defines -> "redefinition of 'sched_param'".
    f = os.path.join(
        top, "kernel/oneplus/sm8450-modules/qcom/opensource/camera-kernel/",
        "drivers/cam_req_mgr/cam_req_mgr_workq.c")
    if not os.path.exists(f):
        print(f"{f}: not present, skip")
        return
    s = open(f).read()
    dup = "struct sched_param {\n\tint sched_priority;\n};\n\n"
    if dup in s:
        open(f, "w").write(s.replace(dup, "", 1))
        print(f"patched {f} (dropped duplicate struct sched_param)")
    else:
        print(f"{f}: no changes needed")


def patch_boot_jars_allowlist(top):
    # oplus-fwk.jar (hardware/oplus) lands on the bootclasspath carrying
    # many vendor packages (net.oneplus.odm, com.oplus.*, oplus.*);
    # check_boot_jars rejects any package not in the allow list. Add every
    # non-android.* package found in the jar. Only runs after the jar is
    # built; on a fresh tree the next build pass picks it up.
    import subprocess
    f = os.path.join(top, "build/soong/scripts/check_boot_jars/package_allowed_list.txt")
    jar = os.path.join(top, "out/soong/.intermediates/hardware/oplus/oplus-fwk/"
                       "oplus-fwk/android_common/aligned/oplus-fwk.jar")
    dexdump = os.path.join(top, "out/host/linux-x86/bin/dexdump")
    if not (os.path.exists(f) and os.path.exists(jar) and os.path.exists(dexdump)):
        print(f"{os.path.basename(f)}: prerequisites not ready yet, skip")
        return
    out = subprocess.run([dexdump, "-d", jar], capture_output=True, text=True).stdout
    pkgs = set()
    for m in re.finditer(r"Class descriptor.*?L([a-zA-Z0-9_./]+);", out):
        parts = m.group(1).split("/")
        if len(parts) > 1:
            pkgs.add(".".join(parts[:-1]))
    pkgs = {p for p in pkgs if not (p.startswith("android.") or p.startswith("com.android."))}
    cur = set(open(f).read().split())
    missing = sorted(pkgs - cur)
    if missing:
        open(f, "a").write("".join(p + "\n" for p in missing))
        print(f"patched {os.path.basename(f)} (allow {len(missing)}: {", ".join(missing)})")
    else:
        print(f"{os.path.basename(f)}: no changes needed")


if __name__ == "__main__":
    patch_bp(vendor_bp)
    patch_boot_jars_allowlist(top)
    patch_kernel_modules(top)
    patch_vendor_mk(os.path.join(top, "vendor/oneplus/sm8450-common/sm8450-common-vendor.mk"))
    patch_common_ptxt(common_ptxt)
    remove_euicc(top)
