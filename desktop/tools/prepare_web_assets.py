"""Build web font derivatives from the user's bundled Pretendard assets."""
from pathlib import Path
import shutil
from fontTools.ttLib import TTFont
ROOT=Path(__file__).resolve().parents[2]
def main():
    output=ROOT/'desktop/public/assets';fonts=output/'fonts';fonts.mkdir(parents=True,exist_ok=True)
    for source,name in [('PretendardVariable.ttf','CalixVariable.woff2'),('CalixSans-Italic.ttf','CalixItalic.woff2'),('CalixSans-BoldItalic.ttf','CalixBoldItalic.woff2')]:
        path=ROOT/'asset/style'/source;target=fonts/name
        if target.exists() and target.stat().st_mtime>=path.stat().st_mtime:continue
        font=TTFont(path);font.flavor='woff2';font.save(target);font.close()
    (output/'icons').mkdir(exist_ok=True)
    for source,target in [('asset/icons/calix.svg','icons/calix.svg'),('asset/profile-avatar.png','profile-avatar.png'),('asset/style/Pretendard-OFL.txt','fonts/Pretendard-OFL.txt')]:shutil.copy2(ROOT/source,output/target)
    print('Local web fonts and assets ready')
if __name__=='__main__':main()
