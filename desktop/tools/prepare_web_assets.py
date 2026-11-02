"""Build web font derivatives from the user's bundled Pretendard assets."""

from pathlib import Path
import shutil
import json
import re
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]


def main():
    output = ROOT / "desktop/public/assets"
    fonts = output / "fonts"
    fonts.mkdir(parents=True, exist_ok=True)
    for source, name in [
        ("PretendardVariable.ttf", "CalixVariable.woff2"),
        ("CalixSans-Italic.ttf", "CalixItalic.woff2"),
        ("CalixSans-BoldItalic.ttf", "CalixBoldItalic.woff2"),
    ]:
        path = ROOT / "asset/style" / source
        target = fonts / name
        if target.exists() and target.stat().st_mtime >= path.stat().st_mtime:
            continue
        font = TTFont(path)
        font.flavor = "woff2"
        font.save(target)
        font.close()
    (output / "icons").mkdir(exist_ok=True)
    for source, target in [
        ("asset/icons/calix.svg", "icons/calix.svg"),
        ("asset/profile-avatar.png", "profile-avatar.png"),
        ("asset/style/Pretendard-OFL.txt", "fonts/Pretendard-OFL.txt"),
    ]:
        shutil.copy2(ROOT / source, output / target)
    alarm = output / "alarm"
    alarm.mkdir(exist_ok=True)
    tracks = []
    for source in (ROOT / "asset/alarm").glob("*.mp3"):
        if re.fullmatch(r"(?:[1-9]|10|crit)\.mp3", source.name):
            shutil.copy2(source, alarm / source.name)
            if source.stem != "crit":
                tracks.append(int(source.stem))
    (alarm / "catalog.json").write_text(
        json.dumps(dict(tracks=sorted(tracks), critical=(alarm / "crit.mp3").exists())),
        encoding="utf-8",
    )
    sound=output/'sound'
    sound.mkdir(exist_ok=True)
    shutil.copy2(ROOT/'asset/sound/notify.mp3',sound/'notify.mp3')
    print("Local web fonts and assets ready")


if __name__ == "__main__":
    main()
