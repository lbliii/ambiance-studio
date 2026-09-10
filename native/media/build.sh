#!/bin/sh
set -eu
render_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
xcrun clang -O2 -fobjc-arc -Wno-deprecated-declarations -framework Foundation -framework AVFoundation -framework CoreMedia -framework CoreVideo -framework ImageIO -framework CoreGraphics "$render_dir/media.m" -o "$render_dir/media"
