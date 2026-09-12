"""Runtime diagnostics and supported regression-suite entry points."""
from .command_output import Output, add_output
import importlib.util
from pathlib import Path
import platform
import shutil
import sys

from . import __version__
from .asset_commands import asset_tool
from .scene_runtime import require_node

def add_parsers(sub):
    q=sub.add_parser('test',help='Run local regression checks without paid providers');add_output(q, Output.REPORT, type=Path)
    q.add_argument('--artifacts',type=Path,help='Fresh directory for bounded JSON/JUnit/log diagnostics')
    q.add_argument('--require-native',action='store_true',help='Fail on unavailable native media capability or any skipped required test')


def doctor(root):
    from . import rendering, audio
    render_caps=rendering.capabilities();audio_caps=audio.capabilities()
    render_caps['preparation_workbench']=importlib.util.find_spec('PIL') is not None and bool(shutil.which('node'))
    pillow=importlib.util.find_spec('PIL') is not None
    return {'version':__version__,'root':str(root),'python':platform.python_version(),'python_executable':sys.executable,
        'node':shutil.which('node'),'pillow':pillow,'ffmpeg':shutil.which('ffmpeg'),'ffprobe':shutil.which('ffprobe'),
        'capabilities':{'project_and_reviews':True,'revision_binding':True,'production_inventory':True,'asset_preparation':pillow,'art_regions':{'local':pillow,'scene_sizing':pillow and bool(shutil.which('node'))},'asset_preflight_and_crop_return':pillow,'edge_inspection_and_repair':pillow,'finishing_and_look_packages':render_caps['frame_render'],'cel_motion':{'manual':pillow,'tracking':'pillow-patch-ncc' if pillow else None,'version':'1.0.0'},'asset_proofs':pillow,'scene_operations':bool(shutil.which('node')),'scene_tracks':bool(shutil.which('node')),'saved_views':bool(shutil.which('node')),'source_placement_and_reparent':bool(shutil.which('node')),'scene_timing':bool(shutil.which('node')),'preview':bool(shutil.which('node')),'final_video_export':render_caps['final_video_export'],'audio_arrangement':audio_caps['audio_arrangement'],'rendering':render_caps,'audio':audio_caps},
        'note':'Optional dependency availability does not imply a renderer or provider adapter is implemented.'}


def test(args):
    require_node()
    asset_tool()
    from .checks import run_suite
    return run_suite(args.artifacts, args.require_native)
