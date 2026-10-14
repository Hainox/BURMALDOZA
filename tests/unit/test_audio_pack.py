import json
import subprocess
from pathlib import Path

from devtools.audio import build_pack


def test_segments_keep_trailing_speech(monkeypatch):
    def run(command, **kwargs):
        if command[0] == 'ffprobe':
            return subprocess.CompletedProcess(command, 0, stdout='3.0\n')
        return subprocess.CompletedProcess(command, 0, stderr='silence_start: 0\nsilence_end: 1 | silence_duration: 1\n')

    monkeypatch.setattr(build_pack.subprocess, 'run', run)
    assert build_pack.speech_segments(Path('track.mp3'), 0.5, 4.0) == [(1.0, 3.0)]


def test_quotes_cover_the_whole_disc(monkeypatch, tmp_path):
    folder = tmp_path / 'disc'
    folder.mkdir()
    for index in range(95):
        (folder / f'{index:03}.mp3').touch()
    monkeypatch.setattr(build_pack, 'speech_segments', lambda *args: [(0.0, 1.0)])
    selected = []
    monkeypatch.setattr(build_pack, 'encode', lambda src, *args: selected.append(src.name))
    build_pack.split_quotes(folder, 'Kazuma_Kiryu', {'min': 0.5, 'max': 4, 'limit': 48, 'group': 'quip'}, tmp_path / 'out')
    assert len(selected) == 48
    assert selected[0] == '000.mp3'
    assert selected[-1] == '094.mp3'


def test_rebuilt_sample_has_a_new_cache_url(monkeypatch, tmp_path):
    selection = tmp_path / 'selection.json'
    selection.write_text(json.dumps({'music': {}, 'voices': {}, 'sfx': {'ui-tap': 'tap.wav'}}))
    monkeypatch.setattr(build_pack, 'SELECTION', selection)
    source = tmp_path / 'tap.wav'

    def encode(src, dst, *args):
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        return 1.0

    monkeypatch.setattr(build_pack, 'encode', encode)
    source.write_bytes(b'first sound')
    first_out = tmp_path / 'first'
    first = build_pack.build(tmp_path, first_out)['sfx']['ui-tap']['src']
    source.write_bytes(b'replacement sound')
    second_out = tmp_path / 'second'
    second = build_pack.build(tmp_path, second_out)['sfx']['ui-tap']['src']
    assert first != second
    assert (first_out / first).read_bytes() == b'first sound'
    assert (second_out / second).read_bytes() == b'replacement sound'
