"""Render/media command registration and compatibility entry points.

Edition lifecycle remains in media_operations; request planning, native runtime
transport and decode verification have independent public service owners.
"""
from .command_output import Output, add_output
from pathlib import Path
import json

from .errors import CommandError
from .native_media import capabilities, ROOT, RENDERER, NATIVE_SOURCE
from .render_execution import compose, execute_render
from .render_plan import plan_render
from .media_verification import requested_contacts, verify_command, verify_media

# Retain historical imports for external callers. Studio consumers use the
# public service owners; these aliases are not dependency injection boundaries.
from .file_identity import digest as _digest
from .native_media import native_binary as _native_binary, json_command as _json_command
from .media_inputs import (fresh_output as _fresh, positive_integer as _positive_integer,
                           project_input as _project_input, input_identity as _identity,
                           pcm_bytes as _pcm_bytes)
from .render_plan import render_context as _context


def add_parsers(sub):
    group = sub.add_parser('render', help='Render saved scene frames, motion proofs, or video').add_subparsers(dest='action', required=True)
    q = group.add_parser('benchmark'); q.add_argument('file', type=Path); add_output(q, Output.ARTIFACT, type=Path, required=True)
    for action in ['frame', 'proof', 'rig-proof', 'look-proof', 'video', 'views-proof']:
        q = group.add_parser(action)
        q.add_argument('--revision', help='Verified captured revision ID; never falls back to working scene')
        if action in ['rig-proof', 'look-proof']:
            q.add_argument('recipe', type=Path)
        add_output(q, Output.ARTIFACT, type=Path, required=True, help='Fresh output directory; never overwrites')
        if action == 'views-proof':
            q.add_argument('--view', action='append', dest='views', required=True, help='Saved view ID; repeat for synchronized outputs')
            q.add_argument('--long-edge', type=int, default=640, help='Maximum preview side; preserve an integer aspect ratio')
        else:
            q.add_argument('--width', type=int, default=360 if action in ['rig-proof','look-proof'] else None)
            q.add_argument('--height', type=int, help='Defaults to the selected view or authored aspect ratio')
            if action in ['frame', 'proof', 'video']:
                q.add_argument('--view', help='Saved view ID; omission preserves the full authored canvas')
        if action != 'rig-proof':
            q.add_argument('--supersample', type=int, choices=[1, 2, 4], default=1, help='Render geometry at this scale then downsample once; internal dimensions must remain <=4096')
        if action == 'frame':
            q.add_argument('--time', type=float, default=0)
        elif action not in ['rig-proof', 'look-proof']:
            q.add_argument('--start', type=float, default=0)
            q.add_argument('--seconds', type=float, help='Integer frame duration within one loop; proof default 3 seconds')
        if action == 'proof':
            q.add_argument('--disable', action='append', default=[], metavar='LAYER', help='Add a synchronized comparison with this layer hidden; repeatable')
        if action == 'video':
            _edition_arguments(q)
            q.add_argument('--bitrate', type=int)
            q.add_argument('--audio-bitrate', type=int, help='Stereo AAC bps: 256000 (default), 320000 or 384000; checked against backend; requires audio')
            q.add_argument('--repeats', type=int, default=1)
            q.add_argument('--audio', type=Path, help='Selected stereo 48 kHz PCM WAV matching the final duration exactly')
    group = sub.add_parser('media', help='Decode and inspect actual encoded deliverables').add_subparsers(dest='action', required=True)
    q = group.add_parser('verify')
    q.add_argument('file', type=Path)
    q.add_argument('--revision'); q.add_argument('--edition'); q.add_argument('--view')
    add_output(q, Output.ARTIFACT, type=Path, required=True, help='Fresh report/contact directory')
    for field in ['width', 'height', 'fps', 'frames', 'loop-frames']:
        q.add_argument('--'+field, type=int, help='Defaults to the selected scene')
    q.add_argument('--audio-tracks', type=int, choices=[0, 1])
    q.add_argument('--contact-time', type=float, action='append', default=[])
    q.add_argument('--contact-frame', type=int, action='append', default=[])
    q = group.add_parser('compose', help='Reuse encoded CFR H.264 picture with selected PCM, then verify')
    q.add_argument('picture', type=Path)
    q.add_argument('--picture-receipt', help='Project-relative existing render report binding this picture to the selected revision')
    q.add_argument('--audio', type=Path, required=True)
    q.add_argument('--audio-bitrate', type=int, help='Stereo AAC bps: 256000 (default), 320000 or 384000; checked against backend')
    q.add_argument('--repeats', type=int, default=1)
    add_output(q, Output.ARTIFACT, type=Path, required=True)
    q.add_argument('--revision')
    q.add_argument('--view', help='Assert the picture view when binding a revision edition')
    _edition_arguments(q)


def _edition_arguments(parser):
    parser.add_argument('--edition')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--audio-session', help='Project-relative executable session for edition dependency closure')
    group.add_argument('--audio-run', help='Project-relative existing CLI audio run for edition dependency closure')
    group.add_argument('--audio-provenance', help='Project-relative explicit external preparation declaration')


def run(args, project):
    project = Path(project).resolve()
    if args.command == 'media':
        if args.action == 'compose':
            return compose(args, project)
        return verify_command(args, project)
    return execute_render(plan_render(args, project))


def _verify(project, *args, **kwargs):
    """Compatibility for the former unused project argument."""
    return verify_media(*args, **kwargs)


def _scene(project):
    return json.loads(_context(project)['scene'].read_text())


def _error(message, code='invalid_input', exit_code=2):
    raise CommandError(message, code, exit_code)
