#!/usr/bin/env python3
"""Validate the six source icons and create a deterministic installable pack."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "local.hexaza.custom.sdIconPack"
EXPECTED = {"melon", "claude", "antigravity", "slack", "chatgpt", "discord"}


def check_sources(tag=None):
    manifest = json.loads((PACK / "manifest.json").read_text())
    version = manifest["Version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("manifest의 버전 형식을 확인해 주세요")
    if tag and tag != "v" + version:
        raise ValueError("릴리스 태그와 manifest 버전이 다릅니다")
    entries = json.loads((PACK / "icons.json").read_text())
    paths = [entry["path"] for entry in entries]
    names = [entry["name"].casefold() for entry in entries]
    if len(entries) != 6 or set(names) != EXPECTED or len(set(paths)) != 6:
        raise ValueError("여섯 아이콘의 이름이나 파일이 누락·중복되었습니다")
    if set(paths) != {name + ".png" for name in EXPECTED}:
        raise ValueError("아이콘 파일 경로를 확인해 주세요")
    if set(paths) != {path.name for path in (PACK / "icons").iterdir()}:
        raise ValueError("icons 폴더와 아이콘 목록이 다릅니다")
    for entry in entries:
        if not entry.get("tags") or not all(isinstance(tag, str) for tag in entry["tags"]):
            raise ValueError("아이콘 검색 태그를 확인해 주세요")
        with Image.open(PACK / "icons" / entry["path"]) as icon:
            if icon.format != "PNG" or icon.size != (144, 144):
                raise ValueError("아이콘은 144×144 PNG여야 합니다")
            icon.verify()
    if manifest.get("Icon") != "icon.png" or manifest.get("License") != "license.txt":
        raise ValueError("팩 아이콘과 라이선스 경로를 확인해 주세요")
    with Image.open(PACK / manifest["Icon"]) as icon:
        icon.verify()
    if "MIT License" not in (PACK / manifest["License"]).read_text():
        raise ValueError("배경 템플릿의 라이선스를 포함해 주세요")
    return manifest, entries


def preview(entries):
    canvas = Image.new("RGB", (704, 426), "#141b20")
    # This embedded bitmap font uses no FreeType rasterizer or system fonts.
    font = ImageFont.load_default_imagefont()
    for index, entry in enumerate(entries):
        x, y = 64 + index % 3 * 216, 23 + index // 3 * 202
        with Image.open(PACK / "icons" / entry["path"]) as source:
            icon = source.convert("RGBA")
            canvas.paste(icon, (x, y), icon)
        left, top, right, bottom = font.getbbox(entry["name"])
        label = Image.new("L", (right - left, bottom - top))
        ImageDraw.Draw(label).text((-left, -top), entry["name"], font=font, fill=255)
        label = label.resize((label.width * 2, label.height * 2), Image.Resampling.NEAREST)
        canvas.paste("#e5e9ed", (x + 72 - label.width // 2, y + 156), label)
    encoded = io.BytesIO()
    canvas.save(encoded, format="PNG", optimize=False)
    return encoded.getvalue()


def package(destination):
    paths = [PACK / "manifest.json", PACK / "icons.json", PACK / "icon.png", PACK / "license.txt"]
    paths.extend((PACK / "icons").glob("*.png"))
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(paths):
            info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip():
            raise ValueError("아이콘 팩의 압축 검사가 실패했습니다")
        for path in paths:
            if archive.read(path.relative_to(ROOT).as_posix()) != path.read_bytes():
                raise ValueError("패키지와 원본 파일이 다릅니다")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="배포할 태그, 예: v1.0.1")
    parser.add_argument("--update-preview", action="store_true", help="검사한 원본으로 docs/preview.png 갱신")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    manifest, entries = check_sources(args.tag)
    image = preview(entries)
    documented = ROOT / "docs" / "preview.png"
    if args.update_preview:
        documented.write_bytes(image)
    documented_bytes = documented.read_bytes()
    # PNG encoders may emit different compressed bytes for identical pixels.
    # Validate the image, then distribute the exact reviewed repository asset.
    with Image.open(io.BytesIO(documented_bytes)) as saved, Image.open(io.BytesIO(image)) as generated:
        if saved.size != generated.size or saved.convert("RGBA").tobytes() != generated.convert("RGBA").tobytes():
            raise ValueError("미리보기가 원본과 다릅니다. --update-preview로 갱신해 주세요")
    args.output.mkdir(parents=True, exist_ok=True)
    archive = args.output / "local.hexaza.custom.streamDeckIconPack"
    package(archive)
    (args.output / "preview.png").write_bytes(documented_bytes)
    checksums = []
    for path in [archive, args.output / "preview.png"]:
        checksums.append(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name)
    (args.output / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n")
    print("Hexaza Custom " + manifest["Version"] + " · 여섯 아이콘과 미리보기 검사 완료")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
