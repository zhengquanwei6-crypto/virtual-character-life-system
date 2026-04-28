# Android APK

这是一个 Android WebView 壳，加载同一套 React Web UI，用于移动端体验验证和安装包分发。

默认加载地址：

```txt
http://96.30.199.85:8090/index.html
```

GitHub Actions 会在推送 `v*` tag 时构建 debug APK，并上传 artifact。

本地构建需要 JDK、Android SDK 和 Gradle：

```bash
cd mobile/android
gradle app:assembleDebug -PWEB_URL=http://96.30.199.85:8090/index.html -PAPP_VERSION_NAME=0.4.0 -PAPP_VERSION_CODE=6
```
