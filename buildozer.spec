[app]
title = PDF阅读器
package.name = pdfreader
package.domain = org.example

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 1.0
requirements = python3,kivy,pygments,pymupdf,android

orientation = portrait

[buildozer]
log_level = 2

[android]
api = 33
minapi = 21
ndk = 25b
android.sdk_path = /usr/local/lib/android/sdk
android.accept_sdk_license = True  # 关键配置！

[android:activity_launch_mode]
singleTask = True

[android:meta-data]
android.app.uses_cleartext_traffic = true

[android:grant_permissions]
android.permission.READ_EXTERNAL_STORAGE = true
android.permission.WRITE_EXTERNAL_STORAGE = true
