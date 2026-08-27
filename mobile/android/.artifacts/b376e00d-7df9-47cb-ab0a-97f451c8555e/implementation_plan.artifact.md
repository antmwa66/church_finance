# Implementation Plan - Resolve C++20 Compilation Errors by Upgrading NDK

The project is using React Native 0.76.1, which requires C++20. The current NDK version (25.1.8937393) has incomplete support for C++20 concepts and standard library features like `std::identity`, `std::floating_point`, etc. This plan upgrades the NDK version to the recommended `26.1.10909125` and reverts manual workarounds.

## Proposed Changes

### Android Build Configuration

#### [MODIFY] [build.gradle](file:///C:/Projects/church_finance/mobile/android/build.gradle)
- Update `ndkVersion` from `25.1.8937393` to `26.1.10909125`.

#### [MODIFY] [gradle.properties](file:///C:/Projects/church_finance/mobile/android/gradle.properties)
- Update `android.ndkVersion` from `25.1.8937393` to `26.1.10909125`.

### React Native Source Workarounds

#### [MODIFY] [hash_combine.h](file:///C:/Projects/church_finance/mobile/node_modules/react-native/ReactCommon/react/utils/hash_combine.h)
- Revert the simplification of the `Hashable` concept. The newer compiler in NDK 26 should handle the original definition correctly.

## Verification Plan

### Automated Tests
- Run `:expo-modules-core:externalNativeBuildDebug` to verify that the C++ compilation succeeds.
- Run a full build of the app: `./gradlew :app:assembleDebug`.

### Manual Verification
- Verify that the app starts on an Android device/emulator if the build succeeds.
