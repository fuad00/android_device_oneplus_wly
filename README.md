# OnePlus 10 Pro (taro) — LineageOS 23

Unofficial LineageOS 23 (Android 16) device tree for the **OnePlus 10 Pro** (`taro`, NE2213), based on the [pjgowtham/android_device_oneplus_wly](https://github.com/pjgowtham/android_device_oneplus_wly) build.

| | |
|---|---|
| **Device** | OnePlus 10 Pro 5G (NE2213) |
| **Codename** | `taro` |
| **SoC** | Qualcomm SM8450 (Snapdragon 8 Gen 1) |
| **LineageOS** | 23.x (Android 16) |
| **Base firmware** | OxygenOS 15 (`NE2213_15.0.0.700(EX01)` / `S.12f8570_15_17`) |
| **Status** | Unofficial / daily-drivable |
| **Upstream** | [pjgowtham/android_device_oneplus_wly](https://github.com/pjgowtham/android_device_oneplus_wly) |

## Status

| Feature | Works | Feature | Works |
|---|:---:|---|:---:|
| Boot | ✅ | WiFi | ✅ |
| Camera | ✅ | Bluetooth | ✅ |
| Torch | ✅ | eSIM / VoLTE | ✅ |
| Fingerprint (UDFPS) | ❌ removed | NFC | ✅ |
| USB | ✅ | GPS | ✅ |

### Fingerprint — intentionally removed

The Goodix under-display fingerprint HAL (`vendor.oplus.hardware.biometrics.fingerprint@2.1-service` + AIDL `@2.3-service.oplus`) is not supported on this hardware: both services crash on start and never register with `hwservicemanager`, while the biometrics framework re-triggers them in a tight loop — the result is a permanent CPU load spike.

To remove the sensor **permanently** this tree:

- drops the AIDL fingerprint service from `PRODUCT_PACKAGES` and the `android.hardware.fingerprint` feature flag (`device.mk`)
- removes the ODM HIDL service, its init `.rc`, VINTF manifest, Goodix drivers and firmware (`proprietary-files.txt`)
- drops the related blob fixups (`extract-files.py`)
- sets `ro.biometric.sensors=` (`vendor.prop`) so the framework stops probing for a sensor entirely

> PIN / pattern unlock work as usual.

## Building

Tested on **Ubuntu 24.04 LTS, x86_64, 16 cores, 62 GB RAM, 424 GB disk**.
macOS / Apple Silicon will *not* work (AOSP expects x86_64 Linux; 36 GB is too little RAM).

### Resource requirements

| | |
|---|---|
| **CPU** | 8 vCPU minimum, 16+ comfortable |
| **RAM** | 32 GB minimum, 64 GB comfortable |
| **Disk free** | **≥ 400 GB** — ~180 GB sources (`/root/lineage`) + ~60 GB `out/` |
| **Build time** | ~1–2 h first build (ninja, 16 cores); incremental rebuilds far faster |

### One-time dependencies

```sh
apt install openjdk-17-jdk git git-lfs curl rsync ccache wget unzip zip \
  bison flex gperf squashfs-tools zlib1g-dev libc6-dev schedtool \
  p7zip-full libssl-dev libxml2 libxml2-utils lz4 pigz gdisk mtools \
  patchelf optipng golang-go liblzma-dev
```

(`golang-go` + `liblzma-dev` are for `payload-dumper-go`, which unpacks the stock OTA payload.)

### Vendor blobs (no stock OTA needed)

Pre-extracted proprietary blobs live in
[`fuad00/proprietary_vendor_oneplus_wly`](https://github.com/fuad00/proprietary_vendor_oneplus_wly)
(~1.9 GB, from OxygenOS 15.0.0.700 EU). `build.sh` clones it and lays out:

```
wly/proprietary/           -> vendor/oneplus/wly/proprietary
sm8450-common/proprietary/ -> vendor/oneplus/sm8450-common/proprietary
```

then regenerates the per-device make/bp files with `setup-makefiles.py` and
re-applies the build fixes with `reapply-patches.py`.

### Stock firmware input (fallback)


You need the **stock OxygenOS 15 full OTA payload** for NE2213 —
`NE2213_15.0.0.700(EX01)` (EU). It is a ~5.7 GB `.zip` containing
`payload.bin`. Drop it at:

```
<top>/stock/OOS_15.0.0.700_EU_NE2213.zip
```

### One-shot build

```sh
./build.sh ~/lineage
```

`build.sh` does the whole job: sync sources, clone the pinned manual trees,
unpack the payload, run `extract-files.py`, reapply the regeneratable fixes,
`lunch lineage_wly bp2a userdebug`, `mka bacon`. The resulting zip lands in
`out/target/product/wly/lineage-23.0-*-wly.zip`.

### Manual equivalent (what `build.sh` does)

```sh
# 1. Sources
mkdir -p ~/lineage && cd ~/lineage
repo init -u https://github.com/LineageOS/android.git -b lineage-23.0
cat > .repo/local_manifests/wly-local.xml <<'EOF'
<?xml version="1.0"?>
<manifest>
  <remote name="fuad00" fetch="https://github.com/fuad00" review="https://github.com"/>
  <project path="device/oneplus/wly" name="fuad00/android_device_oneplus_wly"/>
  <project name="fuad00/android_kernel_oneplus_sm8450" path="kernel/oneplus/sm8450" revision="wly-lineage-23.0"/>
  <project name="pjgowtham/android_kernel_oneplus_sm8450-modules" path="kernel/oneplus/sm8450-modules" revision="lineage-23.0"/>
  <project name="pjgowtham/android_kernel_oneplus_sm8450-devicetrees" path="kernel/oneplus/sm8450-devicetrees" revision="lineage-23.0"/>
</manifest>
EOF
repo sync -c -j16

# 2. Manual trees (repo metadata conflicts with these pinned revisions,
#    so clone + materialize a worktree at the exact branch):
#    device/oneplus/sm8450-common  <- pjgowtham/android_device_oneplus_sm8450-common lineage-23.0
#    hardware/pixelworks           <- LineageOS/android_hardware_pixelworks_interfaces lineage-23.0
#    hardware/oplus                <- pjgowtham/android_hardware_oplus lineage-23.0
#        (has commondcs + oplus-multihal sensors; LineageOS mainline lacks the latter)
#    kernel/oneplus/sm8450{,-modules,-devicetrees} <- pjgowtham, lineage-23.0
#        (pinned in the local manifest above; BoardConfigKernel needs the kernel
#         Makefile for TARGET_KERNEL_VERSION — without it ckati dies on
#         vendor/lineage/build/tasks/kernel.mk: "Argument missing")

# 3. Payload -> vendor blobs
unzip -o -q stock/OOS_15.0.0.700_EU_NE2213.zip payload.bin
payload-dump -o stock/partitions -p vendor,odm,system_ext,product,system stock/payload.bin
# mount each ext4 image read-only and copy to vendor/oneplus/wly/firmware/<part>

# 4. Extract + fix + build
cd device/oneplus/wly
./extract-files.py /path/to/firmware
python3 reapply-patches.py $TOP
cd ~/lineage && source build/envsetup.sh && lunch lineage_wly bp2a userdebug
mka bacon
```

### Why `reapply-patches.py`

`extract-files.py` **regenerates** `vendor/oneplus/sm8450-common/Android.bp`
from scratch every run, which drops manual build fixes. The idempotent
`reapply-patches.py` restores them:

- `olc2` / `radio` / `charger` prebuilt `-ndk_platform` libs → `system_ext_specific`
  (they must match their source `aidl_interface` partition once the AIDL NDK
  platform backend is on; `soc_specific` / `device_specific` are removed since
  they are mutually exclusive)
- `libwfdservice`: drop the explicit `android.media.audio.common.types-V2-cpp`
  dep (it collides with V4 pulled transitively; WFD/Miracast is non-critical)
- `sm8450-common-vendor.mk`: drop `wfdservice` from `PRODUCT_PACKAGES` — it is a
  32-bit prebuilt (`compile_multilib: "32"`) and does not register on this
  64-bit-only product ("non-existent module in PRODUCT_PACKAGES")
- remove `hardware/oplus/Euicc/` — the legacy `OplusEuicc` app duplicates the
  mainline `packages/apps/EuiccPolicy` hidden-api-whitelist module; it is not in
  any `PRODUCT_PACKAGES` so the dir can go

Also, `device/oneplus/wly/BoardConfig.mk` sets `NEED_AIDL_NDK_PLATFORM_BACKEND
:= true` — required so prebuilt vendor AIDL libs (e.g. `libsecurity_event_dcs`)
can resolve their `-ndk_platform` variant.

### Base-firmware notes

The blob lists target `15.0.0.700`. A few blobs that only exist in newer
(901) bases are excluded: the irissoft `S6E3HC3` panel firmware, the
fastcharge `charge_time_config.csv`, and the HEXAGON hotword-enrollment
apps. All are non-essential for the features above.

## Credits

- [pjgowtham](https://github.com/pjgowtham) — original device tree and builds
- [LineageOS](https://lineageos.org) team
