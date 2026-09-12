"""Small HTTP mechanics for the captured-artifact draft workbenches.

Handlers own routes, MIME selection, JSON encoding, errors and evaluation locks.
Body validation and reading stay separate because motion validates its length
before taking the lock, while preparation and region take the lock first.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class BodyPolicy:
    maximum: int
    missing_length: str
    bounds_error: str
    reject_transfer_encoding: bool
    timeout: float | None
    incomplete_error: str | None


class BodyBoundsError(ValueError):
    """Parsed length or transfer encoding violates a handler's body policy."""


def local_origin_violation(handler):
    """Return the violated header name; absent Origin remains valid locally."""
    expected = f'127.0.0.1:{handler.server.server_port}'
    if handler.headers.get('Host') != expected:
        return 'Host'
    origin = handler.headers.get('Origin')
    if origin is not None and origin != f'http://{expected}':
        return 'Origin'
    return None


def respond(handler, data, mime, *, csp, status=200, disposition=None):
    """Send already-encoded bytes without changing each workbench's wire format."""
    handler.send_response(status)
    handler.send_header('Content-Type', mime)
    handler.send_header('Content-Length', str(len(data)))
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('X-Content-Type-Options', 'nosniff')
    if disposition is not None:
        handler.send_header('Content-Disposition', disposition)
    handler.send_header('Content-Security-Policy', csp)
    handler.end_headers()
    handler.wfile.write(data)


def body_length(handler, policy):
    # Preserve int() parsing errors separately from a parsed out-of-bounds length.
    length = int(handler.headers.get('Content-Length', policy.missing_length))
    if not 0 < length <= policy.maximum or (
            policy.reject_transfer_encoding and handler.headers.get('Transfer-Encoding')):
        raise BodyBoundsError(policy.bounds_error)
    return length


def read_body(handler, length, policy):
    if policy.timeout is not None:
        handler.connection.settimeout(policy.timeout)
    body = handler.rfile.read(length)
    if policy.incomplete_error is not None and len(body) != length:
        raise ValueError(policy.incomplete_error)
    return body


def serve_until_interrupt(server):
    """Common run/close lifecycle; callers retain construction and startup JSON."""
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
