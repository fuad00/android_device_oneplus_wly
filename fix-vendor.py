#!/usr/bin/env python3
"""Post-extract-files fixup for lineage-23.0 base (Sep 2026):
libwfdservice prebuilt requests audio.common.types-V2-cpp while libmedia pulls V4 —
soong forbids two versions. Drop the V2 dep (WFD is non-critical)."""
import re, sys
p = sys.argv[1] if len(sys.argv) > 1 else "/root/lineage/vendor/oneplus/sm8450-common/Android.bp"
s = open(p).read()
lib = re.compile(r"cc_prebuilt_library_shared \{\n    name: \"libwfdservice\",")
m = lib.search(s)
if not m:
    print("libwfdservice not found"); sys.exit(0)
close = s.find("\n}", m.end())
block = s[m.end():close]
if "android.media.audio.common.types-V2-cpp" in block:
    s = s[:m.end()] + block.replace("                \"android.media.audio.common.types-V2-cpp\",\n", "") + s[close:]
    open(p, "w").write(s)
    print("patched: dropped V2-cpp from libwfdservice")
else:
    print("already patched")

# --- part 2: drop 32-bit wfdservice prebuilt (crash-loops, never registers on sm8450) ---
import re
mk = "/root/lineage/vendor/oneplus/sm8450-common/sm8450-common-vendor.mk"
s = open(mk).read()
s2 = re.sub(r"\n    wfdservice \\\n", "\n", s)
if s2 != s:
    open(mk, "w").write(s2)
    print("mk: removed wfdservice from PRODUCT_PACKAGES")
bp = "/root/lineage/vendor/oneplus/sm8450-common/Android.bp"
b = open(bp).read()
m = re.search(r"cc_prebuilt_binary \{\n    name: \"wfdservice\",.*?\n\}\n", b, re.S)
if m:
    open(bp, "w").write(b.replace(m.group(0), ""))
    print("bp: removed wfdservice module")
