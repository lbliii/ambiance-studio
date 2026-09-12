"""Shared ordered polygon rasterization. Coordinates are source pixel centers."""
import math


def rasterize(spec, size, base=None):
    from PIL import Image, ImageDraw
    mask = base.copy() if base is not None else Image.new('L', size)
    draw = ImageDraw.Draw(mask)
    for poly in spec['polygons']:
        points = [(math.floor(x+.5), math.floor(y+.5)) for x, y in poly['points']]
        draw.polygon(points, fill=255 if poly['operation'] == 'add' else 0)
    return mask


def projected(spec, size, source_to_export, base=None, supersample=2):
    """Rasterize vector edges at output density; imported alpha remains raster data."""
    from PIL import Image, ImageDraw
    from . import asset_prep as ap
    a,b,c,d,e,f = source_to_export
    s = supersample
    target = (size[0]*s, size[1]*s)
    transform = [a*s,b*s,c*s,d*s,e*s,f*s]
    if base is None:
        mask = Image.new('L', target)
    else:
        rgba = Image.new('RGBA', base.size, 'white'); rgba.putalpha(base)
        mask = ap.resample(rgba, target, transform, 'bicubic').getchannel('A')
    draw = ImageDraw.Draw(mask)
    for poly in spec['polygons']:
        # Pixel-center vertices become centers of transformed source pixels.
        points = [((a*(x+.5)+c*(y+.5)+e)*s-.5,
                   (b*(x+.5)+d*(y+.5)+f)*s-.5) for x,y in poly['points']]
        draw.polygon(points, fill=255 if poly['operation']=='add' else 0)
    return mask.resize(size, Image.Resampling.LANCZOS) if s != 1 else mask
