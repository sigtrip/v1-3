[app]
title = Argos Universal OS
package.name = argos_v13
package.domain = org.sigtrip

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.3
# Полный список зависимостей для Android
requirements = python3,kivy,requests,psutil,urllib3,certifi,idna,charset-normalizer

orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.api = 31
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
