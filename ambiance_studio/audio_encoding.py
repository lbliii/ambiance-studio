"""Bounded AAC policy and backend capability check before picture production."""
from .errors import CommandError
from .native_media import json_command

DEFAULT_BITRATE = 256000
SUPPORTED_BITRATES = (256000, 320000, 384000)


def encoding_settings(bitrate=None, *, has_audio=True):
    if not has_audio:
        if bitrate is not None:
            raise CommandError('audio bitrate requires a selected PCM source')
        return None
    bitrate = DEFAULT_BITRATE if bitrate is None else bitrate
    if type(bitrate) is not int or bitrate not in SUPPORTED_BITRATES:
        raise CommandError('Supported stereo AAC audio bitrate values are 256000, 320000 and 384000 bits per second, subject to backend capability; no fallback')
    return {'codec': 'aac', 'sample_rate': 48000, 'channels': 2, 'bitrate_bps': bitrate}


def preflight(binary, settings):
    if settings is None:
        return None
    return json_command([binary, 'audio-preflight', settings['bitrate_bps']])


def preflight_iteration_audio(project, recipe, jobs, progress):
    """Only new native audio jobs need codec access before picture production.

    Saved steps/editions still go through their existing integrity/recovery owner;
    no capability probe is needed to reuse them (or reject altered evidence).
    Injected media executors retain responsibility for their own capabilities.
    """
    from . import editions, native_media
    from .media_operations import execute_job
    if progress.executor is not execute_job:
        return []
    entries = {entry['role']: entry for entry in recipe['editions']}
    pending = {encoding_settings(entries[job['role']].get('audio_bitrate'))['bitrate_bps']
               for job in jobs if job['stage'] == 'compose' and job['key'] not in progress.state['steps']
               and not editions.edition_path(project, recipe['revision'], job['edition']).exists()}
    if not pending:
        return []
    binary = native_media.native_binary(project)
    return [preflight(binary, encoding_settings(rate)) for rate in sorted(pending)]
