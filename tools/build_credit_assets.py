"""Build small credit images once, instead of decoding large sources on open."""
from pathlib import Path
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QImage,QPainter
from PySide6.QtSvg import QSvgRenderer

root=Path(__file__).resolve().parents[1]/'asset'
image=QImage(str(root/'profile.png'));assert not image.isNull()
image=image.scaled(384,384,Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation)
image=image.copy((image.width()-384)//2,(image.height()-384)//2,384,384)
assert image.save(str(root/'profile-avatar.png'))
for name in ('github','github-dark','paypal','paypal-dark'):
    renderer=QSvgRenderer(str(root/'icons'/f'{name}.svg'));assert renderer.isValid()
    target=QImage(128,128,QImage.Format.Format_ARGB32_Premultiplied);target.fill(Qt.GlobalColor.transparent)
    painter=QPainter(target);renderer.render(painter,QRectF(0,0,128,128));painter.end()
    assert target.save(str(root/'icons'/f'{name}.png'))
