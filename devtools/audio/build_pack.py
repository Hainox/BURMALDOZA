"""Собирает звуковой пакет Mini App из файлов владельца.

Что делает: по devtools/audio/selection.json пережимает музыку, звуки и голоса дилеров (ffmpeg,
AAC .m4a, выровненная громкость) и пишет manifest.json, который клиент читает с /audio/manifest.json.
Когда использовать: после изменения отбора или новых файлов в пакете; результат копируется на
сервер в /srv/burmaldoza-audio (см. docs/Deploy-Production.md, «Звуковой пакет»).
Что настроить: установлен ffmpeg; аргументы — корень пакета и пустая папка для результата.
Файлы из игр в репозиторий не кладутся — только этот скрипт и отбор.

    python -m devtools.audio.build_pack "C:/Users/<you>/Downloads/Game_Audio" <out_dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SELECTION = Path(__file__).with_name("selection.json")
# Музыка: до 4 минут с затуханием, стерео 96 кбит/с, громкость -18 LUFS (фон, не перекрывает эффекты).
MUSIC_FILTER = "loudnorm=I=-18:TP=-2:LRA=11,afade=t=in:d=1.5,afade=t=out:st=236:d=4"
# Эффекты: убрать тишину в начале, не длиннее 2,5 с, мягкий хвост.
SFX_FILTER = (
    "silenceremove=start_periods=1:start_threshold=-45dB,"
    "atrim=0:2.5,afade=t=out:st=1.9:d=0.6,loudnorm=I=-15:TP=-1.5"
)
VOICE_FILTER = "silenceremove=start_periods=1:start_threshold=-50dB,loudnorm=I=-16:TP=-1.5"
VOICE_GROUPS = {
    "greet": ("advisor_generic_phrase",),
    "dealer_win": ("advisor_notification_invasion_success",),
    "dealer_lose": ("advisor_notification_invasion_failed", "advisor_notification_invasion_enemy_won"),
}


def slug(text: str) -> str:
    # Имя файла на сервере: латиница и цифры, короткий хэш исходного пути против совпадений.
    base = "".join(ch.lower() if ch.isalnum() else "-" for ch in Path(text).stem).strip("-")
    return f"{'-'.join(filter(None, base.split('-')))[:40]}-{hashlib.sha1(text.encode()).hexdigest()[:6]}"


def encode(src: Path, dst: Path, audio_filter: str, extra: list[str]) -> float:
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn", "-af", audio_filter, *extra,
           "-c:a", "aac", "-movflags", "+faststart", str(dst)]
    subprocess.run(cmd, check=True)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(dst)],
        check=True, capture_output=True, text=True,
    )
    return round(float(probe.stdout.strip()), 2)


def build(pack: Path, out: Path) -> dict:
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    manifest: dict = {"version": 1, "music": {}, "sfx": {}, "voices": {}}

    def need(rel: str) -> Path:
        path = pack / rel
        if not path.is_file():
            raise SystemExit(f"нет файла в пакете: {rel}")
        return path

    for room, tracks in selection["music"].items():
        manifest["music"][room] = []
        for rel in tracks:
            name = f"music/{room}/{slug(rel)}.m4a"
            duration = encode(need(rel), out / name, MUSIC_FILTER, ["-t", "240", "-ac", "2", "-b:a", "96k"])
            manifest["music"][room].append({"src": name, "title": Path(rel).stem, "duration": duration})
            print("music", room, name, duration)

    for key, spec in selection["sfx"].items():
        # Эффект — путь или {"src", "max"}: длинные заставки (например, «новая глава» Yakuza) не обрезаются до 2,5 с.
        rel, limit = (spec, 2.5) if isinstance(spec, str) else (spec["src"], float(spec["max"]))
        audio_filter = SFX_FILTER.replace("atrim=0:2.5,afade=t=out:st=1.9", f"atrim=0:{limit},afade=t=out:st={limit - 0.6}")
        name = f"sfx/{key}.m4a"
        manifest["sfx"][key] = {"src": name, "duration": encode(need(rel), out / name, audio_filter, ["-ac", "2", "-b:a", "96k"])}
        print("sfx", key)

    for doll, spec in selection["voices"].items():
        groups: dict[str, list[str]] = {}
        if isinstance(spec, dict) and "split" in spec:
            # Склейки фраз (например, Ultimate Quotes Кирю): режем по паузам на короткие реплики.
            manifest["voices"][doll] = {spec["group"]: split_quotes(need_dir(pack / spec["split"]), doll, spec, out)}
            print("voice", doll, spec["group"], len(manifest["voices"][doll][spec["group"]]))
            continue
        if isinstance(spec, str):
            files = sorted(p.name for p in need_dir(pack / spec).iterdir() if p.suffix == ".wav")
            spec = {
                group: [f"{spec}/{f}" for f in files if f.startswith(prefixes)]
                for group, prefixes in VOICE_GROUPS.items()
            }
        for group, rels in spec.items():
            groups[group] = []
            for rel in rels:
                name = f"voice/{slug(doll)}/{group}-{slug(rel)}.m4a"
                encode(need(rel), out / name, VOICE_FILTER, ["-ac", "1", "-b:a", "64k"])
                groups[group].append(name)
        manifest["voices"][doll] = groups
        print("voice", doll, {g: len(v) for g, v in groups.items()})

    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def speech_segments(path: Path, low: float, high: float) -> list[tuple[float, float]]:
    # Куски между паузами (тишина ниже -35 dB дольше 0,35 с) нужной длины.
    probe = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af", "silencedetect=noise=-35dB:d=0.35", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    )
    starts, ends = [0.0], []
    for line in probe.stderr.splitlines():
        if "silence_start:" in line:
            ends.append(float(line.split("silence_start:")[1].split()[0]))
        elif "silence_end:" in line:
            starts.append(float(line.split("silence_end:")[1].split()[0]))
    return [(a, b) for a, b in zip(starts, ends) if low <= b - a <= high]


def split_quotes(folder: Path, who: str, spec: dict, out: Path) -> list[str]:
    candidates = [
        (path, start, end)
        for path in sorted(folder.glob("*.mp3"))
        for start, end in speech_segments(path, float(spec["min"]), float(spec["max"]))
    ]
    # Равномерно по всему диску, а не первые N.
    limit = int(spec["limit"])
    step = max(1, len(candidates) // limit)
    chosen = candidates[::step][:limit]
    names = []
    for index, (path, start, end) in enumerate(chosen):
        name = f"voice/{slug(who)}/{spec['group']}-{index:02d}.m4a"
        trim = f"atrim={max(0.0, start - 0.05):.2f}:{end + 0.15:.2f},asetpts=PTS-STARTPTS,"
        encode(path, out / name, trim + "loudnorm=I=-16:TP=-1.5", ["-ac", "1", "-b:a", "64k"])
        names.append(name)
    return names


def need_dir(path: Path) -> Path:
    if not path.is_dir():
        raise SystemExit(f"нет папки в пакете: {path}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pack", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        sys.exit("папка результата должна быть пустой")
    build(args.pack, args.out)


if __name__ == "__main__":
    main()
