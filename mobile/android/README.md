# Android APK

这是一个最小 Android WebView 壳，用来把已部署的 Web 应用打包为 APK。

默认加载：

```txt
http://96.30.199.85/index.html
```

GitHub Actions 会在每次推送 tag `v*` 时构建 debug APK，并上传为 artifact。

本地构建需要 JDK、Android SDK 和 Gradle：

```bash
cd mobile/android
gradle app:assembleDebug -PWEB_URL=http://96.30.199.85/index.html -PAPP_VERSION_NAME=0.2.0 -PAPP_VERSION_CODE=2
```

