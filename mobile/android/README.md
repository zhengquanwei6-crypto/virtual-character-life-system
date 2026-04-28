# Android APK

这是一个 Android WebView 壳，用同一套 React Web UI 提供移动端体验。

默认加载：

```txt
http://96.30.199.85:8090/index.html
```

GitHub Actions 会在推送 tag `v*` 时构建 debug APK，并上传 artifact。

本地构建需要 JDK、Android SDK 和 Gradle：

```bash
cd mobile/android
gradle app:assembleDebug -PWEB_URL=http://96.30.199.85:8090/index.html -PAPP_VERSION_NAME=0.3.1 -PAPP_VERSION_CODE=5
```
