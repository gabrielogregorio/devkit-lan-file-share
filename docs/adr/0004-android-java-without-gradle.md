# 4. Android app in Java, built without Gradle

**Status:** accepted

The app is one share target, a foreground service and a scanner. Java against the platform API needs no framework: the
APK is under 300 KB and `android/build.sh` builds it with the SDK tools alone. A cross-platform framework would add a
build chain and a runtime for a share target, which is native code anyway.

**Consequences:** no AndroidX, so the scanner uses the old `android.hardware.Camera`, a fraction of the code of
camera2. The classes free of the Android API (`PcClient`, `PairLink`, `KeyRing`, `Failure`, `PairingPlan`) run on a
plain JVM against the real server, so the network code under test is the code that ships.
