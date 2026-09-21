# OnePlus 10 Pro (taro) — LineageOS 23

Unofficial LineageOS 23 (Android 16) device tree for the **OnePlus 10 Pro** (`taro`, NE2213), based on the [pjgowtham/android_device_oneplus_wly](https://github.com/pjgowtham/android_device_oneplus_wly) build.

| | |
|---|---|
| **Device** | OnePlus 10 Pro 5G (NE2213) |
| **Codename** | `taro` |
| **SoC** | Qualcomm SM8450 (Snapdragon 8 Gen 1) |
| **LineageOS** | 23.x (Android 16) |
| **Base firmware** | OxygenOS 15 (`S.12f8570_15_17`) |
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

Standard LineageOS device-tree build:

```sh
mkdir -p ~/lineage && cd ~/lineage
repo init -u https://github.com/LineageOS/android.git -b lineage-23.0
echo '<?xml version="1.0"?>
<manifest>
  <remote name="fuad00" fetch="https://github.com/fuad00" review="https://github.com"/>
  <project path="device/oneplus/taro" name="fuad00/android_device_oneplus_wly"/>
</manifest>' > .repo/local_manifests/taro-local.xml
repo sync -c -j8
source build/envsetup.sh
lunch lineage_wly-userdebug
mka bacon
```

Proprietary blobs are extracted with `extract-files.py` from a stock OxygenOS 15 image.

## Credits

- [pjgowtham](https://github.com/pjgowtham) — original device tree and builds
- [LineageOS](https://lineageos.org) team
