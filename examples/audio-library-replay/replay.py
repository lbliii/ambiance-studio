#!/usr/bin/env python3
"""Public LIB-01 replay with local tones and no claimed listening/acceptance."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from ambiance_studio.file_identity import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); base = args.out.resolve()
    if base.exists(): raise ValueError('Replay output must be fresh')
    base.mkdir(parents=True); origin = base/'origin'; destination = base/'destination'; config = base/'library-config.json'
    media = base/'shared-media'; steps = []
    def write(path, data): path.write_text(json.dumps(data, indent=2)+'\n')
    def cli(*argv, project=None, expected=0):
        command = [str(ROOT/'ambiance'), *(['--project', str(project)] if project else []), *map(str,argv)]
        result = subprocess.run(command, capture_output=True, text=True)
        data = json.loads(result.stdout)
        steps.append({'argv':command,'exit_code':result.returncode,'result':data,'stderr':result.stderr})
        write(base/'replay.json',{'ok':False,'steps':steps})
        if result.returncode != expected: raise ValueError(f'Expected {expected}, got {result.returncode}: {result.stdout}')
        return data.get('data',{})
    # Library root is a separate fresh local directory, never a worktree-dependent default.
    cli('audio','library','configure','--config',config,'--media-root',media,'--library-id','lib01-replay')
    for project in [origin,destination]: cli('project','init',project,'--template','blank')
    source = origin/'tone.wav'
    with wave.open(str(source),'wb') as output:
        output.setnchannels(2); output.setsampwidth(2); output.setframerate(48000)
        output.writeframes(b''.join(((i%101-50)*(ch+1)*20).to_bytes(2,'little',signed=True) for i in range(4800) for ch in range(2)))
    source_hash = digest(source)
    write(origin/'provenance.json', {'origin_kind':'synthesized','entitlement':'unknown','audition':'not performed',
                                   'prior_processing':'Deterministic locally generated 100ms technical tone; not a natural recording'})
    candidate = cli('audio','library','import','tone','--config',config,'--version','original-v1','--kind','event',
        '--source','tone.wav','--sha256',source_hash,'--backend','pcm','--provenance','provenance.json',project=origin)
    cli('audio','library','search','tone','--config',config,'--state','candidate')
    prepared = cli('audio','source-prepare','tone.wav','--backend','pcm','--source-sha256',source_hash,
        '--preparation-id','working-v1','--provenance','provenance.json',project=origin)
    receipt = 'audio/preparations/working-v1/receipt.json'
    selected = cli('audio','library','import','tone','--config',config,'--version','prepared-v1','--kind','event',
        '--preparation',receipt,'--sha256',prepared['receipt_sha256'],'--parent-version','original-v1','--parent-sha256',candidate['sha256'],project=origin)
    cli('audio','library','inspect','tone','--version','prepared-v1','--config',config)
    excerpt = cli('audio','library','audition','tone','--version','prepared-v1','--config',config,
        '--expect-version',selected['sha256'],'--audition-id','region-v1','--start-frame','480','--frames','2400')
    # An actual rendered file is insufficient for promotion. No synthetic listening record is supplied.
    cli('audio','library','promote','tone','--version','prepared-v1','--config',config,'--expect-state',selected['state_sha256'],
        '--event-id','unperformed','--decision','accepted','--by','LIB-01 replay','--note','No listening performed',expected=2)
    cli('audio','library','import','duplicate','--config',config,'--version','v1','--kind','event','--preparation',receipt,
        '--sha256',prepared['receipt_sha256'],project=origin,expected=2)
    materialized = cli('audio','library','materialize','tone','--version','prepared-v1','--config',config,
        '--expect-version',selected['sha256'],'--expect-state',selected['state_sha256'],
        '--materialization-id','tone-use-v1','--allow-unaccepted',project=destination)
    old_receipt_hash = prepared['receipt_sha256']; working_hash = prepared['working']['sha256']
    # Keep read-only evidence but remove the original locations, making every stored external address unavailable.
    origin.rename(base/'origin-unavailable'); media.rename(base/'library-unavailable')
    config.rename(base/'config-unavailable.json')
    local_receipt = 'audio/library/tone-use-v1/receipt.json'
    checked = cli('audio','library','check',local_receipt,project=destination)
    for item, expected_hash in [(checked['original'],source_hash),(checked['working'],working_hash)]:
        if digest(destination/item['path']) != expected_hash: raise ValueError('Portable bytes differ')
    data = json.loads((destination/local_receipt).read_text())
    if digest(destination/data['files']['source_receipt']['path']) != old_receipt_hash: raise ValueError('Prior sealed receipt was rewritten')
    session = {'format':'ambiance-audio-session','schema_version':1,'id':'portable-source-use','sample_rate':48000,'frames':4800,
        'sources':[materialized['source']],'stems':[{'id':'tone'}],
        'clips':[{'id':'tone','source':'tone','stem':'tone','frames':4800,'at_frame':0}]}
    write(destination/'session.json',session)
    cli('audio','inspect','session.json',project=destination)
    cli('audio','check',checked['working']['path'],project=destination)
    write(destination/'selection.json',{'format':'ambiance-revision-selection','schema_version':1,
        'scene':'scene/scene.json','catalog':'assets/catalog.json','audio':{'session':'session.json','preparations':[local_receipt]}})
    cli('revision','capture','portable-v1','--selection',destination/'selection.json',project=destination)
    cli('revision','check','portable-v1',project=destination)
    # Package the full selected project bytes; revision handoff itself is a review summary, not a media copier.
    handoff = base/'portable-handoff'; shutil.copytree(destination,handoff); destination.rename(base/'destination-unavailable')
    cli('audio','library','check',local_receipt,project=handoff)
    cli('audio','inspect','session.json',project=handoff)
    cli('revision','check','portable-v1',project=handoff)
    artifacts = {str(p.relative_to(base)):{'sha256':digest(p),'bytes':p.stat().st_size} for p in sorted(base.rglob('*'))
                 if p.is_file() and p.name != 'replay.json' and '.ambiance' not in p.parts}
    implementations = {str(p.relative_to(ROOT)):digest(p) for p in [ROOT/'ambiance_studio'/name for name in
        ['audio_library.py','audio_library_records.py','audio_materialization.py','audio_sources.py','audio.py','revision_dependencies.py','cli.py']]}
    report = {'ok':True,'steps':steps,'artifacts':artifacts,'implementation_sha256':implementations,
        'source':{'original_sha256':source_hash,'working_sha256':working_hash,'prior_receipt_sha256':old_receipt_hash,
                  'library_version_sha256':selected['sha256'],'frames':4800,'sample_rate':48000,'channels':2},
        'portable_project':str(handoff),'listening':'not performed','promotion':'correctly rejected without actual observation',
        'observations':['Decoded exact stereo source/excerpt frame counts and compared byte identities.',
                        'Source use, revision capture/check and a second copied handoff passed with original library/project paths absent.'],
        'limits':['Technical generated-local tones only; no listening, curation, new mix or artistic acceptance.',
                  'Unit tests separately exercise simulated observation/promotion transitions; this replay claims no audition.']}
    write(base/'replay.json',report)
    print(json.dumps({'ok':True,'report':str(base/'replay.json'),'report_sha256':digest(base/'replay.json'),
                      'portable_project':str(handoff),'working':str(handoff/checked['working']['path']),
                      'listening':'not performed'}))


if __name__ == '__main__': main()
