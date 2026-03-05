[app]
title = ARGOS v1.3
package.name = argos
package.domain = org.sigtrip

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.3
requirements = python3,kivy

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
