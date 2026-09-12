"""Shared edition lifecycle and typed media jobs for production operators.

CLI namespaces stop at execute_media. Iteration jobs use immutable requests and
an injectable executor; their saved argv is diagnostic, never parsed to run work.
"""
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, Protocol

from . import rendering, revisions


@dataclass(frozen=True, kw_only=True)
class PictureRequest:
    revision: str
    edition: str
    view: str | None = None
    width: int | None = None
    height: int | None = None
    supersample: int = 1
    start: float = 0
    seconds: float | None = None
    repeats: int = 1
    bitrate: int | None = None
    audio: Path | None = None
    audio_session: str | None = None
    audio_run: str | None = None
    audio_provenance: str | None = None
    command: ClassVar[str] = 'render'
    action: ClassVar[str] = 'video'
    report_name: ClassVar[str] = 'render-report.json'
    positionals: ClassVar[tuple[str, ...]] = ()


@dataclass(frozen=True, kw_only=True)
class ComposeRequest:
    revision: str
    edition: str
    picture: Path
    picture_receipt: str
    audio: Path
    view: str | None = None
    repeats: int = 1
    audio_session: str | None = None
    audio_run: str | None = None
    audio_provenance: str | None = None
    command: ClassVar[str] = 'media'
    action: ClassVar[str] = 'compose'
    report_name: ClassVar[str] = 'compose-report.json'
    positionals: ClassVar[tuple[str, ...]] = ('picture',)


MediaRequest = PictureRequest | ComposeRequest


class MediaExecutor(Protocol):
    """Execute one job, including input validation and its edition receipt.

Successful results supply output/report/verification paths and an edition
receipt. The coordinator pins these files before marking a step complete.
"""
    def __call__(self, project: Path, request: MediaRequest, out: Path) -> dict[str, Any]: ...


def request_argv(project: Path, request: MediaRequest, out: Path) -> list[str]:
    """Equivalent CLI invocation retained for inspection and manual recovery."""
    values = asdict(request)
    argv = ['--project', str(project), request.command, request.action]
    argv.extend(str(values.pop(key)) for key in request.positionals)
    for key, value in values.items():
        if value is not None:
            argv.extend(['--' + key.replace('_', '-'), str(value)])
    return [*argv, '--out', str(out)]


def execute_media(args, project):
    """One authoritative prepare → render/compose/verify → record sequence."""
    prepared = revisions.prepare_edition(project, args)
    result = rendering.run(args, project)
    return revisions.record_edition(project, prepared, result, args)


def execute_job(project: Path, request: MediaRequest, out: Path) -> dict[str, Any]:
    args = SimpleNamespace(**asdict(request), command=request.command, action=request.action, out=out)
    return execute_media(args, project)
