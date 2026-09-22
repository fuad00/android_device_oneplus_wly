#!/bin/bash
# =============================================================================
# LineageOS 23 (wly / OnePlus 10 Pro 5G) — reproducible build
#
# Builds lineage-23.0 for NE2213 from a stock OxygenOS 15 OTA payload.
# Tested on: Ubuntu 24.04 LTS, x86_64, 16 cores, 62 GB RAM, 424 GB disk.
#
# Requirements (one-time):
#   apt install openjdk-17-jdk git git-lfs curl rsync ccache wget unzip zip \
#     bison flex gperf squashfs-tools zlib1g-dev libc6-dev schedtool \
#     p7zip-full libssl-dev libxml2 libxml2-utils lz4 pigz gdisk mtools \
#     patchelf optipng golang-go liblzma-dev
#
# Inputs:
#   <top>/stock/OOS_15.0.0.700_EU_NE2213.zip   (stock OOS 15 full payload)
#
# Disk: ~180 GB sources + ~60 GB out/  -> keep >= 400 GB free.
# Time: ~1-2 h first build (ninja, 16 cores) on a clean out/.
# =============================================================================
set -euo pipefail

TOP="${1:-$HOME/lineage}"
STOCK="$TOP/stock"
FW="$TOP/vendor/oneplus/wly/firmware"
LUNCH="lineage_wly bp2a userdebug"

cd "$TOP"

# ---- 1. Sync sources -------------------------------------------------------
# Local manifest (in .repo/local_manifests/oneplus-wly-local.xml) pins:
#   device/oneplus/wly            -> fuad00/android_device_oneplus_wly
# The rest (sm8450-common, hardware/oplus, pixelworks, kernels) are cloned
# manually (see "manual trees" below) because repo's metadata conflicts
# with the pinned revisions.
if [ ! -d "$TOP/.repo" ]; then
  /root/bin/repo init -u https://github.com/LineageOS/android.git -b lineage-23.0
fi
repo sync -c -j16

# Manual trees (repo metadata conflicts with pinned revisions; clone bare +
# materialize a worktree). All on lineage-23.0 unless noted.
clone_tree() { # <github-url> <revision> <path>
  local url=$1 rev=$2 path=$3
  if [ ! -d "$TOP/$path" ]; then
    mkdir -p "$TOP/$path"
    git -C "$TOP/$path" init -q
    git -C "$TOP/$path" remote add origin "$url"
    git -C "$TOP/$path" fetch -q origin "$rev"
    git -C "$TOP/$path" checkout -q -b "$rev" FETCH_HEAD
  fi
}
clone_tree https://github.com/pjgowtham/android_device_oneplus_sm8450-common lineage-23.0 device/oneplus/sm8450-common
clone_tree https://github.com/LineageOS/android_hardware_pixelworks_interfaces lineage-23.0 hardware/pixelworks
# hardware/oplus: pjgowtham/lineage-23.0 (has commondcs; NOT the other 3,
# which wly prebuilds). LineageOS mainline 23.0 also works.
clone_tree https://github.com/pjgowtham/android_hardware_oplus lineage-23.0 hardware/oplus

# Kernel trees (required: BoardConfigKernel reads kernel/oneplus/sm8450/Makefile
# for TARGET_KERNEL_VERSION). Pin via local manifest + repo sync:
python3 - <<'EOF'
xml = """  <project name="pjgowtham/android_kernel_oneplus_sm8450" path="kernel/oneplus/sm8450" revision="lineage-23.0"/>
  <project name="pjgowtham/android_kernel_oneplus_sm8450-modules" path="kernel/oneplus/sm8450-modules" revision="lineage-23.0"/>
  <project name="pjgowtham/android_kernel_oneplus_sm8450-devicetrees" path="kernel/oneplus/sm8450-devicetrees" revision="lineage-23.0"/>
"""
for f in __import__("glob").glob(".repo/local_manifests/*.xml"):
    s = open(f).read()
    if 'path="kernel/oneplus/sm8450"' not in s:
        s = s.replace("</manifest>", xml + "</manifest>")
        open(f, "w").write(s)
EOF
repo sync -c -j16 kernel/oneplus/sm8450 kernel/oneplus/sm8450-modules kernel/oneplus/sm8450-devicetrees

# chromium-webview prebuilts: repo sync leaves LFS pointers (smudge --skip),
# so webview.apk is a 134-byte pointer -> "failed opening zip: Invalid file".
# Re-materialize via a throwaway clone with LFS smudge (only the 2 arches
# this product needs; arm64 = target, x86_64 = host tooling fallback).
for arch in arm64 x86_64; do
  f="external/chromium-webview/prebuilt/$arch/webview.apk"
  if [ "$(wc -c < "$TOP/$f" 2>/dev/null || echo 0)" -lt 1000 ]; then
    (cd /tmp && rm -rf wv_$arch && git init -q wv_$arch && cd wv_$arch &&
     git remote add origin "https://github.com/LineageOS/android_external_chromium-webview_prebuilt_${arch}.git" &&
     git lfs install --force && git fetch -q --depth 1 origin main && git checkout -q FETCH_HEAD)
    cp /tmp/wv_$arch/webview.apk "$TOP/$f"
  fi
done

# ---- 2. Vendor blobs --------------------------------------------------------
# Preferred: pre-extracted blobs from the vendor repo (no stock OTA needed).
# Fallback: extract from the stock OxygenOS 15 payload.
VENDOR_REPO="https://github.com/fuad00/proprietary_vendor_oneplus_wly"
if [ ! -d "$TOP/vendor/oneplus/wly/proprietary" ]; then
  if [ -d /tmp/wly_vendor_repo/wly/proprietary ]; then
    # already cloned below
    :
  else
    git clone -q --depth 1 "$VENDOR_REPO" /tmp/wly_vendor_repo
  fi
  mkdir -p "$TOP/vendor/oneplus/wly" "$TOP/vendor/oneplus/sm8450-common"
  cp -a /tmp/wly_vendor_repo/wly/proprietary "$TOP/vendor/oneplus/wly/proprietary"
  cp -a /tmp/wly_vendor_repo/sm8450-common/proprietary "$TOP/vendor/oneplus/sm8450-common/proprietary"
  # generate the per-device vendor make/bp files from the device trees
  (cd "$TOP/device/oneplus/wly" && ./setup-makefiles.py "$TOP/vendor/oneplus/wly")
  (cd "$TOP/device/oneplus/sm8450-common" && ./setup-makefiles.py "$TOP/vendor/oneplus/sm8450-common")
elif [ ! -f "$STOCK/payload.bin" ] && [ -f "$STOCK/OOS_15.0.0.700_EU_NE2213.zip" ]; then
  cd "$STOCK"
  unzip -o -q OOS_15.0.0.700_EU_NE2213.zip payload.bin
  cd "$TOP"
fi

# payload-dump (build once)
if [ ! -x /root/go/bin/payload-dump ]; then
  (cd /tmp && rm -rf pdg && git clone -q --depth 1 --branch 2.0.2 \
      https://github.com/ssut/payload-dumper-go pdg && cd pdg && \
      go build -o /root/go/bin/payload-dump .)
fi

# Dump the partitions we need
mkdir -p "$STOCK/partitions"
/root/go/bin/payload-dump -o "$STOCK/partitions" \
  -p vendor,odm,system_ext,product,system "$STOCK/payload.bin"

# Mount each ext4 image and copy to a plain dir (mounts are read-only and
# extract-files.py's cleanup() would wipe them).
mkdir -p "$FW"
for p in vendor odm system_ext product system; do
  losetup -f --show "$STOCK/partitions/$p.img" > /tmp/lo_$p
  mkdir -p /tmp/mnt_$p && mount -o ro "$(cat /tmp/lo_$p)" /tmp/mnt_$p
  mkdir -p "$FW/$p"
  cp -a /tmp/mnt_$p/. "$FW/$p"
  umount /tmp/mnt_$p; losetup -d "$(cat /tmp/lo_$p)"
done

# ---- 3. Run extract-files.py ------------------------------------------------
cd "$TOP/device/oneplus/wly"
./extract-files.py "$FW"

# Reapply the fixes extract-files.py regenerates away (idempotent)
python3 reapply-patches.py "$TOP"

# chmod 755 /root && chmod 666 /root/.repo_.gitconfig.json 2>/dev/null
# (ckati runs sub-rules as `nobody` in a bwrap sandbox; the build-manifest.xml
# rule calls `repo manifest` which wants to write /root/.repo_.gitconfig.json —
# EROFS if /root is 700)
chmod 755 /root 2>/dev/null
chmod 666 /root/.repo_.gitconfig.json 2>/dev/null

# ---- 4. Build ----------------------------------------------------------------
cd "$TOP"
source build/envsetup.sh
lunch $LUNCH
mka bacon

# ---- 5. Result ----------------------------------------------------------------
ls -lh "$TOP/out/target/product/wly/lineage-23.0-*-wly.zip"
