[app]
title = PDF阅读器
package.name = pdfreader
package.domain = org.example

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json

version = 1.0
requirements = python3,kivy==2.1.0,pillow,pyzmq,cython

orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2

# Android配置
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33
android.arch = arm64-v8a

# 权限
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# 添加额外的gradle依赖
android.gradle_dependencies = implementation 'androidx.core:core:1.9.0'

presplash.filename = %(source.dir)s/presplash.png
icon.filename = %(source.dir)s/icon.png
