"""Generate runtime derivatives from the single set of source assets."""
from pathlib import Path
import os,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]


def build(script,inputs,outputs):
    inputs=[ROOT/'tools'/script,*[ROOT/path for path in inputs]]
    outputs=[ROOT/path for path in outputs]
    if all(path.is_file() for path in outputs) and min(path.stat().st_mtime_ns for path in outputs)>=max(path.stat().st_mtime_ns for path in inputs):return
    env=os.environ.copy();env['QT_QPA_PLATFORM']='offscreen'
    subprocess.run([sys.executable,'-B','-u',str(inputs[0])],cwd=ROOT,env=env,check=True)
    assert all(path.is_file() for path in outputs)


def main():
    fonts=[f'asset/style/CalixSans-{style}.ttf' for style in ('Regular','Medium','SemiBold','Bold')]
    build('build_fonts.py',['asset/style/PretendardVariable.ttf'],fonts)
    build('build_italic_fonts.py',[fonts[0],fonts[3]],[f'asset/style/CalixSans-{style}.ttf' for style in ('Italic','BoldItalic')])
    icons=['github','github-dark','paypal','paypal-dark']
    build('build_credit_assets.py',['asset/profile.png',*[f'asset/icons/{name}.svg' for name in icons]],['asset/profile-avatar.png',*[f'asset/icons/{name}.png' for name in icons]])
    build('render_startup.py',['asset/icons/calix.svg',*fonts,'learning_calendar/fonts.py'],['asset/startup.bmp','asset/startup.png'])


if __name__=='__main__':main()
