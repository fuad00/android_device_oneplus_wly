#!/usr/bin/env python3
"""Post-extract-files fixup for lineage-23.0 bp2a base (Sep 2026).

Run after every extract-files.py + setup-makefiles.py on the sm8450-common
vendor tree.

Part 1: libwfdservice prebuilt requests audio.common.types-V2-cpp while the
new base's libmedia pulls V4; soong forbids two versions of one interface in
a dependency graph. Drop the V2-cpp entry (WFD tolerates it).

Part 2: wfdservice 32-bit prebuilt fails to register as a soong module on the
new base and breaks PRODUCT_PACKAGES resolution. Removed from Android.bp and
sm8450-common-vendor.mk.

Part 3: pixelworks iris prebuilt blobs fail check_elf_file because the
source-built vendor.pixelworks.hardware.* HIDL interfaces do not propagate
vendor-variant shared-lib entries to them. Skip strict ELF verification on
these vendor blobs.
"""
import re
import sys

BP = "/root/lineage/vendor/oneplus/sm8450-common/Android.bp"
MK = "/root/lineage/vendor/oneplus/sm8450-common/sm8450-common-vendor.mk"

# --- part 1: libwfdservice V2-cpp dep ---
s = open(BP).read()
lib = re.compile(r'cc_prebuilt_library_shared \{\n    name: "libwfdservice",')
m = lib.search(s)
if m:
    close = s.find("\n}", m.end())
    block = s[m.end():close]
    if "android.media.audio.common.types-V2-cpp" in block:
        s = s[:m.end()] + block.replace(
            '                "android.media.audio.common.types-V2-cpp",\n', "") + s[close:]
        open(BP, "w").write(s)
        print("part1: dropped V2-cpp from libwfdservice")
    else:
        print("part1: already clean")
else:
    print("part1: libwfdservice not found")

# --- part 2: remove wfdservice prebuilt ---
s = open(MK).read()
s2 = re.sub(r"\n    wfdservice \\\n", "\n", s)
if s2 != s:
    open(MK, "w").write(s2)
    print("part2: removed wfdservice from PRODUCT_PACKAGES")
s = open(BP).read()
m = re.search(r'cc_prebuilt_binary \{\n    name: "wfdservice",.*?\n\}\n', s, re.S)
if m:
    open(BP, "w").write(s.replace(m.group(0), ""))
    print("part2: removed wfdservice module from Android.bp")

# --- part 3: check_elf_files off for pixelworks iris blobs ---
MODULES = [
    "libpwirisfeature", "libpwirissoft", "libpwirishalwrapper",
    "libpwirisservice", "libpwiriscalibrate", "libpwirisIoctlWrapper",
    "libpwsoftirisPCS", "irisConfig",
    "vendor.pixelworks.hardware.feature.irisfeature-service",
    "vendor.pixelworks.hardware.display.iris-service",
]
s = open(BP).read()
n = 0
for name in MODULES:
    block = re.search(
        r'(?s)((?:cc_prebuilt_library_shared|cc_prebuilt_binary) \{\n    name: "%s",.*?\n\})' % name, s)
    if not block or "check_elf_files" in block.group(1):
        continue
    patched = block.group(1).replace("    owner:", "    check_elf_files: false,\n    owner:", 1)
    s = s[:block.start(1)] + patched + s[block.end(1):]
    n += 1
open(BP, "w").write(s)
print("part3: check_elf_files disabled for %d pixelworks blobs" % n)
