"""Build the branded startup bitmap from the existing SVG and bundled font."""
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from learning_calendar.bootstrap import configure_runtime
configure_runtime()
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRectF,Qt
from PySide6.QtGui import QImage,QPainter,QColor,QRadialGradient,QLinearGradient,QFont,QPen
from PySide6.QtSvg import QSvgRenderer
from learning_calendar.fonts import apply_korean_font

app=QApplication.instance() or QApplication([]);family=apply_korean_font(app)
image=QImage(1280,720,QImage.Format.Format_RGB32);image.fill(QColor('#F2F5FC'));p=QPainter(image);p.scale(2,2);p.setRenderHint(QPainter.RenderHint.Antialiasing)
for x,y,r,color,alpha in ((80,50,420,'#B2B9EF',165),(610,50,320,'#E7BDDB',140),(450,360,360,'#A4DBD0',150)):
    gradient=QRadialGradient(x,y,r);tint=QColor(color);tint.setAlpha(alpha);gradient.setColorAt(0,tint);tint.setAlpha(0);gradient.setColorAt(1,tint);p.fillRect(QRectF(0,0,640,360),gradient)
p.setPen(QPen(QColor('#FFFFFF'),1));p.setBrush(QColor(255,255,255,155));p.drawRoundedRect(QRectF(30,28,580,304),26,26)
QSvgRenderer(str(root/'asset/icons/calix.svg')).render(p,QRectF(199,108,76,76))
font=QFont(family);font.setPixelSize(44);font.setWeight(QFont.Weight.Bold);p.setFont(font);p.setPen(QColor('#263552'));p.drawText(QRectF(290,106,180,80),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,'Calix')
font.setPixelSize(17);font.setWeight(QFont.Weight.Medium);p.setFont(font);p.setPen(QColor('#546687'));p.drawText(QRectF(40,217,560,38),Qt.AlignmentFlag.AlignCenter,'시작하는 중')
p.end();assert image.save(str(root/'asset/startup.png'));assert image.convertToFormat(QImage.Format.Format_RGB888).save(str(root/'asset/startup.bmp'))
print('asset/startup.png and startup.bmp created from the Calix SVG and Pretendard.')
