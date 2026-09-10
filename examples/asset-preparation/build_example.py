#!/usr/bin/env python3
"""Create a fresh independent fixture; no active project dependencies."""
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ambiance_studio import asset_prep as prep
from tools import asset_tool


def main():
    if len(sys.argv)!=2: raise ValueError('Pass a fresh output project directory')
    project=Path(sys.argv[1]).resolve();project.mkdir()
    prep.write(project/'ambiance-project.json',{'version':1})
    image=Image.new('RGB',(64,96),'#13243a');d=ImageDraw.Draw(image)
    for y in range(12,76,8): d.rectangle((8,y,47,y+3),fill='#b79043')
    d.ellipse((18,25,37,55),fill='#d8caae');image.save(project/'reference.png')
    original=(project/'reference.png').read_bytes()
    prep.preflight(project/'reference.png',project/'preflight')
    prep.write(project/'crop-recipe.json',{'version':1,'crop_xyxy':[8,12,48,76],'export_size':[160,256],'resampling':'nearest'})
    prep.crop(project,project/'reference.png',project/'crop-recipe.json',project/'crop')
    mapping=prep.load(project/'crop/return-template.json');mapping['registration']={'edit_to_export':[1,0,0,1,0,0],'note':'Fixture uses the exact exported image; identity registration is known.'};prep.write(project/'return.json',mapping)
    prep.return_edit(project,project/'crop/crop.png',project/'return.json',project/'returned')
    assert Image.open(project/'returned/composite.png').convert('RGB').tobytes()==image.tobytes()
    assert (project/'reference.png').read_bytes()==original
    prep.write(project/'compile.json',{'version':1,'id':'mapped-native-fixture-v1','input':{'frames':['returned/patch.png'],'allow_opaque':True},'source_mapping':{'file':'returned/source-mapping.json','sha256':prep.sha((project/'returned/source-mapping.json').read_bytes())},'registration':{'mode':'fixed','point':[20,32],'target':[.5,.5]},'output':{'cell_size':[48,72],'columns':1,'padding':2}})
    print(json.dumps(asset_tool.build(project/'compile.json',project/'pack'),indent=2))


if __name__=='__main__':main()
