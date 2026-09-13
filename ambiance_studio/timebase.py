"""Exact frame/sample conversion boundaries shared by picture and audio adapters.

This is arithmetic only; editor/clock.mjs owns evaluated scene time. Fractions
larger than JSON's safe integer range use decimal integer strings in reports.
Residual is rounded minus exact, in the destination unit.
"""
from fractions import Fraction
import math

MAX_SAFE = 2**53 - 1


def integer(value):
    if type(value) is not int or abs(value) > MAX_SAFE:
        raise ValueError('Expected a safe integer')
    return value


def fraction(value):
    if isinstance(value, dict):
        if set(value) != {'numerator', 'denominator'}:
            raise ValueError('Expected numerator/positive denominator')
        def component(v):
            if isinstance(v, str) and len(v) <= 401 and v.lstrip('-').isdigit() and str(int(v)) == v:
                return int(v)
            return integer(v)
        n, d = component(value['numerator']), component(value['denominator'])
        if d <= 0:
            raise ValueError('Rational denominator must be positive')
        return Fraction(n, d)
    if type(value) not in [int, float] or not math.isfinite(value) or abs(value) > MAX_SAFE:
        raise ValueError('Time must be finite and safe')
    return Fraction(str(value))


def rational(value):
    f = value if isinstance(value, Fraction) else fraction(value)
    def part(n):
        return n if abs(n) <= MAX_SAFE else str(n)
    return {'numerator': part(f.numerator), 'denominator': part(f.denominator)}


def positive(value):
    value = fraction(value)
    if value <= 0:
        raise ValueError('Rate/period must be positive')
    return value


def round_rational(value, rounding='exact'):
    value = value if isinstance(value, Fraction) else fraction(value)
    if rounding == 'exact':
        if value.denominator != 1:
            raise ValueError('Exact conversion falls between integer samples/frames')
        result = value.numerator
    elif rounding == 'floor':
        result = math.floor(value)
    elif rounding == 'ceil':
        result = math.ceil(value)
    elif rounding == 'nearest-half-away-from-zero':
        result = math.floor(abs(value) + Fraction(1, 2)) * (-1 if value < 0 else 1)
    else:
        raise ValueError('Unknown rounding policy')
    integer(result)
    return {'value': result, 'exact': rational(value), 'rounding': rounding,
            'residual': rational(result - value)}


def frame_to_seconds(frame, fps):
    return rational(integer(frame) / positive(fps))


def frames_to_samples(frame, fps, rate, rounding='exact'):
    return round_rational(integer(frame) * positive(rate) / positive(fps), rounding)


def samples_to_frames(sample, rate, fps, rounding='exact'):
    return round_rational(integer(sample) * positive(fps) / positive(rate), rounding)


def seconds_to_frames(seconds, fps, rounding='exact'):
    return round_rational(fraction(seconds) * positive(fps), rounding)
