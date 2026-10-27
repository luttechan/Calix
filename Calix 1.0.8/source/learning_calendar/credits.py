"""ANV 2.0's profile hero and two-link credit composition, adapted for Calix."""
from PySide6.QtCore import Qt,QRectF,QSize,QTimer
from PySide6.QtGui import QImageReader,QImage,QPainter,QPainterPath,QPixmap,QIcon,QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QDialog,QFrame,QLabel,QPushButton,QVBoxLayout,QHBoxLayout
from .paths import asset_path
from .design import VERSION,colors
from .app_identity import app_icon

class ProfileAvatar(QLabel):
    def __init__(self,parent=None):
        super().__init__('LL',parent);self.setObjectName('creatorMark');self.setFixedSize(96,96);self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAccessibleName('Lutté Laurent 개발자 프로필');self.setProperty('profileLoaded',False)
        QTimer.singleShot(0,self._load)
    def _load(self):
        dpr=self.devicePixelRatioF();pixels=min(384,round(96*dpr));reader=QImageReader(str(asset_path('profile.png')));reader.setAutoTransform(True)
        size=reader.size()
        if not size.isValid():return
        reader.setScaledSize(size.scaled(pixels,pixels,Qt.AspectRatioMode.KeepAspectRatioByExpanding));image=reader.read()
        if image.isNull():return
        image=image.scaled(pixels,pixels,Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation)
        result=QImage(pixels,pixels,QImage.Format.Format_ARGB32_Premultiplied);result.fill(Qt.GlobalColor.transparent)
        painter=QPainter(result);painter.setRenderHint(QPainter.RenderHint.Antialiasing);clip=QPainterPath();clip.addEllipse(QRectF(0,0,pixels,pixels));painter.setClipPath(clip)
        painter.drawImage(QRectF(0,0,pixels,pixels),image,QRectF((image.width()-pixels)/2,(image.height()-pixels)/2,pixels,pixels));painter.end();result.setDevicePixelRatio(dpr)
        self.clear();self.setPixmap(QPixmap.fromImage(result));self.setProperty('profileLoaded',True)

class CreditsDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setObjectName('creditsDialog');self.setWindowTitle('Calix 크레딧');self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumWidth(530);self.resize(570,610)
        layout=QVBoxLayout(self);layout.setContentsMargins(28,26,28,24);layout.setSpacing(20)
        header=QHBoxLayout();mark=QLabel();mark.setPixmap(app_icon().pixmap(38,38));header.addWidget(mark)
        wordmark=QLabel('Calix');wordmark.setObjectName('brand');header.addWidget(wordmark);header.addStretch()
        version=QLabel(VERSION);version.setObjectName('creditVersion');header.addWidget(version);layout.addLayout(header)
        hero=QFrame();hero.setObjectName('creditHero');body=QVBoxLayout(hero);body.setContentsMargins(28,28,28,30);body.setSpacing(12)
        self.avatar=ProfileAvatar(hero);body.addWidget(self.avatar,0,Qt.AlignmentFlag.AlignHCenter)
        author=QLabel('Lutté Laurent');author.setObjectName('creatorName');author.setAlignment(Qt.AlignmentFlag.AlignCenter);body.addWidget(author)
        role=QLabel('만든 사람');role.setObjectName('creatorRole');role.setAlignment(Qt.AlignmentFlag.AlignCenter);body.addWidget(role);layout.addWidget(hero)
        links=QHBoxLayout();links.setSpacing(12);dark=colors()['bg']=='#11151D'
        for title,caption,logo,url in [('GitHub.io','홈페이지','github','https://luttechan.github.io/index.html'),('PayPal','개발자 후원','paypal','https://www.paypal.com/ncp/payment/XKVWYK7U2EAB4')]:
            button=QPushButton(title+'\n'+caption);button.setObjectName('creditLink');button.setIcon(QIcon(str(asset_path('icons/'+logo+('-dark' if dark else '')+'.svg'))));button.setIconSize(QSize(28,28))
            button.setCursor(Qt.CursorShape.PointingHandCursor);button.setToolTip(url);button.clicked.connect(lambda checked=False,u=url:QDesktopServices.openUrl(QUrl(u)));links.addWidget(button,1)
        layout.addLayout(links)
        note=QLabel('학습의 흐름을 가볍게 정리하는 Calix.');note.setObjectName('muted');layout.addWidget(note)
        legal=QLabel('Python / Qt / PySide6 / Requests\nPretendard / Kil Hyung-jin / SIL OFL 1.1\n공휴일 자료 / python-holidays / MIT');legal.setObjectName('caption');layout.addWidget(legal)
        footer=QHBoxLayout();footer.addStretch();close=QPushButton('닫기');close.clicked.connect(self.close);footer.addWidget(close);layout.addLayout(footer)
