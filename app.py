import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LoudnormStats:
    input_i: str
    input_tp: str
    input_lra: str
    input_thresh: str
    target_offset: str


LOUDNORM_JSON_RE = re.compile(r"\{[\s\S]*\}")


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def ffprobe_json(inp: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(inp),
    ]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"ffprobe failed:\n{p.stderr}")
    return json.loads(p.stdout)


def pick_audio_stream(meta: dict[str, Any]) -> dict[str, Any] | None:
    for s in meta.get("streams", []):
        if s.get("codec_type") == "audio":
            return s
    return None


def build_base_filters() -> str:
    parts = [
        "highpass=f=90",
        "lowpass=f=8000",
        "anlmdn=s=0.00005:p=0.05",
        "agate=threshold=-35dB:ratio=2:attack=10:release=120",
        "acompressor=threshold=-18dB:ratio=3:attack=5:release=80:makeup=4",
        "alimiter=limit=0.98",
    ]
    return ",".join(parts)


def measure_loudnorm(inp: Path, base_filters: str, target_i: float) -> LoudnormStats:
    af = f"{base_filters},loudnorm=I={target_i}:TP=-1.5:LRA=11:print_format=json"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i",
        str(inp),
        "-map",
        "0:a:0",
        "-vn",
        "-af",
        af,
        "-f",
        "null",
        "-",
    ]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg loudnorm measure failed:\n{p.stderr}")

    m = LOUDNORM_JSON_RE.search(p.stderr)
    if not m:
        raise RuntimeError(f"Could not parse loudnorm json from ffmpeg output:\n{p.stderr}")

    data = json.loads(m.group(0))
    return LoudnormStats(
        input_i=str(data["input_i"]),
        input_tp=str(data["input_tp"]),
        input_lra=str(data["input_lra"]),
        input_thresh=str(data["input_thresh"]),
        target_offset=str(data["target_offset"]),
    )


def clean_video(
    inp: Path,
    out: Path,
    target_i: float,
    audio_bitrate: str,
) -> None:
    meta = ffprobe_json(inp)
    astream = pick_audio_stream(meta)
    if astream is None:
        raise RuntimeError("Input has no audio stream.")

    base_filters = build_base_filters()
    stats = measure_loudnorm(inp, base_filters, target_i)

    loudnorm_apply = (
        f"loudnorm=I={target_i}:TP=-1.5:LRA=11:"
        f"measured_I={stats.input_i}:measured_TP={stats.input_tp}:"
        f"measured_LRA={stats.input_lra}:measured_thresh={stats.input_thresh}:"
        f"offset={stats.target_offset}:linear=true:print_format=summary"
    )
    af = f"{base_filters},{loudnorm_apply}"

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i",
        str(inp),

        "-map",
        "0:v:0",
        "-c:v",
        "copy",

        "-map",
        "0:a:0",
        "-af",
        af,
        "-c:a",
        "aac",
        "-b:a",
        audio_bitrate,
        "-movflags",
        "+faststart",
        str(out),
    ]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg clean failed:\n{p.stderr}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--target-i", type=float, default=-16.0)
    parser.add_argument("--audio-bitrate", type=str, default="192k")
    return parser.parse_args()


def main() -> None:
    ns = parse_args()
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    clean_video(
        inp=ns.input,
        out=ns.output,
        target_i=ns.target_i,
        audio_bitrate=ns.audio_bitrate,
    )


if __name__ == "__main__":
    main()
