"""Native discovery/build and tracked JSON process transport for media jobs.

Capability discovery is not an encode/decode test. Builds identify every native
source/header plus platform/compiler and install a binary with a hard link.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

from .errors import CommandError
from .native_sources import compilation_sources, source_identity as native_source_identity

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / 'tools/render-scene.mjs'
NATIVE_SOURCE = ROOT / 'native/media/media.m'


def capabilities():
    """Discovery only: availability is not a performed native encode/decode test."""
    node = shutil.which('node')
    canvas = {'ok': False, 'error': 'Node is unavailable'}
    if node:
        try:
            result = subprocess.run([node, str(RENDERER), '--probe'], capture_output=True, text=True, timeout=20)
            canvas = json.loads(result.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            canvas = {'ok': False, 'error': str(error)}
    override = os.environ.get('AMBIANCE_MEDIA_BINARY')
    native = {'platform': platform.system(), 'supported_platform': platform.system() == 'Darwin',
              'compiler': shutil.which('xcrun'), 'override': override,
              'available': platform.system() == 'Darwin' and (bool(Path(override).is_file() and os.access(override, os.X_OK)) if override else bool(shutil.which('xcrun'))),
              'media_services_tested': False}
    return {'raster': canvas, 'native_media': native,
            'frame_render': bool(canvas.get('ok')), 'motion_proof': bool(canvas.get('ok')),
            'named_view_render': bool(canvas.get('ok')), 'views_proof': bool(canvas.get('ok')),
            'final_video_export': bool(canvas.get('ok') and native['available']),
            'media_verify': native['available'], 'media_compose': native['available'], 'rig_proof': bool(canvas.get('ok')), 'look_proof': bool(canvas.get('ok')), 'supersampled_render': bool(canvas.get('ok'))}


def json_command(command, request=None, allow_check_failure=False):
    """Run a tracked process with strict JSON input and existing failure codes.

    Verification may return a failed check as data. Broken process transport
    still raises a runtime error, and cancellation propagates to run_control.
    """
    from .run_control import execute, ACTIVE
    tracker = ACTIVE.get()
    if tracker and len(command) > 1 and str(command[1]) in ['compose', 'verify', 'probe']:
        tracker.update({'phase': 'media-'+str(command[1])})
    result = execute(list(map(str, command)), json.dumps(request, allow_nan=False) if request is not None else None)
    try:
        data = json.loads(result.stdout)
    except ValueError:
        raise CommandError('Renderer/media runtime failed: '+(result.stderr.strip() or result.stdout.strip()), 'runtime_error', 3)
    if (result.returncode or not data.get('ok', True)) and not allow_check_failure:
        raise CommandError(data.get('error') or result.stderr.strip() or 'Renderer/media operation failed', 'runtime_error', 3)
    return data


def native_binary(project):
    """Resolve an explicit backend or atomically install the cached native build."""
    if platform.system() != 'Darwin':
        raise CommandError('Native video encode/verify requires macOS AVFoundation. Raster frame and HTML proofs are available with Node Canvas.', 'missing_dependency', 3)
    override = os.environ.get('AMBIANCE_MEDIA_BINARY')
    if override:
        binary = Path(override).resolve()
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise CommandError('AMBIANCE_MEDIA_BINARY must point to an executable native media backend.', 'missing_dependency', 3)
        return binary
    compiler = shutil.which('xcrun')
    if not compiler:
        raise CommandError('Native media requires Xcode command-line tools (xcrun clang).', 'missing_dependency', 3)
    version = subprocess.run([compiler, 'clang', '--version'], capture_output=True).stdout
    sources = native_source_identity(NATIVE_SOURCE.parent)
    identity = hashlib.sha256(sources['sha256'].encode()+platform.platform().encode()+version).hexdigest()
    cache = project / '.ambiance/native' / identity
    binary = cache / 'media'
    if not binary.exists():
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='build-', dir=cache) as temp:
            output = Path(temp)/'media'
            command = [compiler, 'clang', '-O2', '-fobjc-arc', '-Wno-deprecated-declarations']
            for framework in ['Foundation', 'AVFoundation', 'CoreMedia', 'CoreVideo', 'ImageIO', 'CoreGraphics']:
                command += ['-framework', framework]
            command += [*map(str, compilation_sources(NATIVE_SOURCE.parent)), '-o', str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode:
                raise CommandError('Native media build failed: '+result.stderr.strip(), 'runtime_error', 3)
            try:
                os.link(output, binary)
            except FileExistsError:
                pass
    return binary
