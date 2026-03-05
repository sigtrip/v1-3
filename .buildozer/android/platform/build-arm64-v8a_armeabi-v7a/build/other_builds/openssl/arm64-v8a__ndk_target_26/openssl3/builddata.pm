package OpenSSL::safe::installdata;

use strict;
use warnings;
use Exporter;
our @ISA = qw(Exporter);
our @EXPORT = qw($PREFIX
                  $BINDIR $BINDIR_REL
                  $LIBDIR $LIBDIR_REL
                  $INCLUDEDIR $INCLUDEDIR_REL
                  $APPLINKDIR $APPLINKDIR_REL
                  $ENGINESDIR $ENGINESDIR_REL
                  $MODULESDIR $MODULESDIR_REL
                  $PKGCONFIGDIR $PKGCONFIGDIR_REL
                  $CMAKECONFIGDIR $CMAKECONFIGDIR_REL
                  $VERSION @LDLIBS);

our $PREFIX             = '/home/jovyan/v1-3/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/build/other_builds/openssl/arm64-v8a__ndk_target_26/openssl3';
our $BINDIR             = '/home/jovyan/v1-3/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/build/other_builds/openssl/arm64-v8a__ndk_target_26/openssl3/apps';
our $BINDIR_REL         = 'apps';
our $LIBDIR             = '/home/jovyan/v1-3/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/build/other_builds/openssl/arm64-v8a__ndk_target_26/openssl3';
our $LIBDIR_REL         = '.';
our $INCLUDEDIR         = '/home/jovyan/v1-3/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/build/other_builds/openssl/arm64-v8a__ndk_target_26/openssl3/include';
our $INCLUDEDIR_REL     = 'include';
our $APPLINKDIR         = '/home/jovyan/v1-3/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/build/other_builds/openssl/arm64-v8a__ndk_target_26/openssl3/ms';
our $APPLINKDIR_REL     = 'ms';
our $ENGINESDIR         = '/home/jovyan/v1-3/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/build/other_builds/openssl/arm64-v8a__ndk_target_26/openssl3/engines';
our $ENGINESDIR_REL     = 'engines';
our $MODULESDIR         = '/home/jovyan/v1-3/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/build/other_builds/openssl/arm64-v8a__ndk_target_26/openssl3/providers';
our $MODULESDIR_REL     = 'providers';
our $PKGCONFIGDIR       = '';
our $PKGCONFIGDIR_REL   = '';
our $CMAKECONFIGDIR     = '';
our $CMAKECONFIGDIR_REL = '';
our $VERSION            = '3.3.1';
our @LDLIBS             =
    # Unix and Windows use space separation, VMS uses comma separation
    split(/ +| *, */, '-ldl -pthread -lm');

1;
