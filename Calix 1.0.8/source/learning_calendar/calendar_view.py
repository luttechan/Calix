"""Qt's native calendar, with a fixed pool of native QLabel count badges."""
from datetime import date,datetime,timedelta
from PySide6.QtCore import Qt,QDate,QLocale,QTimer,Signal,QEvent,QRectF
from PySide6.QtGui import QColor,QFont,QTextCharFormat,QFontMetrics,QPen
from PySide6.QtWidgets import QCalendarWidget,QTableView,QLabel,QSizePolicy,QWidget,QHeaderView
from .design import colors,type_tokens,category_colors
from .models import KST

class DayBadges(QWidget):
    details_requested=Signal(object,object,object)
    def __init__(self,parent=None):
        super().__init__(parent);self.day=None;self.events=[];self.filters={}
        self.assignment=QLabel(self);self.assignment.setObjectName('assignmentBadge')
        self.assignment_done=QLabel(self);self.assignment_done.setObjectName('assignmentBadge')
        self.movie=QLabel(self);self.movie.setObjectName('movieBadge')
        self.custom=[QLabel(self) for _ in range(3)]
        for label in (self.assignment,self.assignment_done,self.movie,*self.custom):
            label.setTextFormat(Qt.TextFormat.PlainText);label.setAlignment(Qt.AlignmentFlag.AlignCenter);label.setCursor(Qt.CursorShape.PointingHandCursor);label.installEventFilter(self)
            font=QFont(label.font());font.setPixelSize(12);label.setFont(font)
        self.hide()
    def set_events(self,day,events):self.day=day;self.events=list(events)
    def matching(self,obj):
        group=self.filters.get(obj)
        if group in ('assignment','assignment_done'):return [e for e in self.events if e.kind=='assignment' and e.type_id is None and e.completed==(group=='assignment_done')]
        if group=='movie':return [e for e in self.events if e.kind=='movie' and e.type_id is None]
        if isinstance(group,tuple):
            name,color,done=group
            return [e for e in self.events if (e.type_label,e.type_color)==(name,color) and (e.kind=='assignment' and e.completed)==done]
        return self.events
    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.MouseButtonPress and event.button()==Qt.MouseButton.LeftButton:
            rows=self.matching(obj)
            if rows and self.day:self.details_requested.emit(self.day,rows,event.globalPosition().toPoint())
            event.accept();return True
        return super().eventFilter(obj,event)
    def mousePressEvent(self,event):
        if self.day and self.events and event.button()==Qt.MouseButton.LeftButton:self.details_requested.emit(self.day,self.events,event.globalPosition().toPoint());event.accept()
        else:super().mousePressEvent(event)
    def configure(self,assignment,movie,width,height,custom=(),*,assignment_done=0):
        custom=[tuple(row) if len(row)==4 else (*row,False) for row in custom]
        raw=[(self.assignment,'과제',assignment,None,False),(self.assignment_done,'완료',assignment_done,None,True),(self.movie,'영상',movie,None,False)]+[(self.custom[i],name,count,color,done) for i,(name,count,color,done) in enumerate(custom[:3])]
        active=[entry for entry in raw if entry[2]]
        self.filters={self.assignment:'assignment',self.assignment_done:'assignment_done',self.movie:'movie'}
        for i,(name,count,color,done) in enumerate(custom[:3]):self.filters[self.custom[i]]=(name,color,done)
        all_labels=' / '.join([f'{"완료 과제" if label is self.assignment_done else name} {count}건'+(' (완료)' if done and label is not self.assignment_done else '') for label,name,count,_,done in active]+[f'{name} {count}건'+(' (완료)' if done else '') for name,count,color,done in custom[3:]])
        total=sum(entry[2] for entry in active)+sum(count for name,count,color,done in custom[3:])
        compact=height<18 or width<60
        capacity=min(3,max(1,(width+4)//48)) if not compact else 3
        if len(active)>capacity or len(custom)>3:
            hidden=len(active)-capacity+1+len(custom[3:])
            active=active[:capacity-1]+[(self.custom[2],f'+{hidden}',0,colors()['muted'],False)] if capacity>1 else [(self.custom[2],'일정',total,colors()['muted'],False)]
            self.filters[self.custom[2]]=None
        for label in (self.assignment,self.assignment_done,self.movie,*self.custom):label.hide()
        for label,title,count,color,done in active:
            label.show()
            c=category_colors();prefix='movie' if label is self.movie else 'assignment';t=type_tokens(color) if color else {key:c[prefix+'_'+key] for key in ('ink','bg','line')}
            if done:
                base=QColor(colors()['surface'])
                t={key:QColor(*[round(QColor(value).getRgb()[i]*.38+base.getRgb()[i]*.62) for i in range(3)]).name() for key,value in t.items()}
            # Opaque pre-composited colors preserve native GDI text rendering.
            label.setProperty('calendarOpacity',.38 if done else 1.);label.setProperty('completed',done)
            radius=2 if compact else 6;padding=0 if compact else 3
            style=f'QLabel {{color:{t["ink"]};background:{t["bg"]};border:1px solid {t["line"]};border-radius:{radius}px;padding:0 {padding}px;font-size:12px;font-weight:600;}}'
            if label.styleSheet()!=style:label.setStyleSheet(style)
            if label.property('compact')!=compact:label.setProperty('compact',compact);label.style().unpolish(label);label.style().polish(label)
        if compact:
            badge_height=8;gap=4;badge_width=min(22,max(12,(width-4*len(active))//max(1,len(active))));total=len(active)*badge_width+max(0,len(active)-1)*gap;left=max(0,(width-total)//2)
            for i,(label,title,count,color,done) in enumerate(active):label.setText('');label.setGeometry(left+i*(badge_width+gap),0,badge_width,badge_height)
        else:
            badge_height=18;gap=4;left=0;maximum=max(24,(width-gap*max(0,len(active)-1))//max(1,len(active)))
            for i,(label,title,count,color,done) in enumerate(active):
                value=f'{title} {count}' if count else title
                chip_width=min(maximum,max(38,min(100,QFontMetrics(label.font()).horizontalAdvance(value)+12)))
                label.setText(label.fontMetrics().elidedText(value,Qt.TextElideMode.ElideRight,max(1,chip_width-8)));label.setGeometry(left,0,chip_width,badge_height);left+=chip_width+gap
        self.setAccessibleName(all_labels);self.setToolTip(all_labels)
        return badge_height

class MonthCanvas(QCalendarWidget):
    selected=Signal(object)
    create_requested=Signal(object)
    details_requested=Signal(object,object,object)
    def __init__(self,parent=None):
        super().__init__(parent);self.buckets={};self._formatted=set();self.holidays={};self.feasts={};self.feast_labels=[]
        self.setLocale(QLocale(QLocale.Language.Korean));self.setFirstDayOfWeek(Qt.DayOfWeek.Sunday)
        self.setNavigationBarVisible(False);self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.setGridVisible(False);self.setMinimumSize(260,230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self.setAccessibleName('월간 달력')
        self.clicked.connect(lambda d:self.selected.emit(d.toPython()))
        self.activated.connect(lambda d:self.create_requested.emit(d.toPython()))
        self.currentPageChanged.connect(lambda y,m:self.selected.emit(date(y,m,1)))
        self.view=self.findChild(QTableView)
        self.view.verticalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Fixed);self.view.verticalHeader().resizeSection(0,34)
        self.badges=[];self.date_labels=[];self.holiday_labels=[]
        for _ in range(42):
            badges=DayBadges(self.view.viewport());badges.details_requested.connect(self.details_requested);self.badges.append(badges)
            number=QLabel(self.view.viewport());number.setObjectName('dateNumber');number.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter);number.setTextFormat(Qt.TextFormat.PlainText);number.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);self.date_labels.append(number)
            holiday=QLabel(self.view.viewport());holiday.setObjectName('holidayName');holiday.setTextFormat(Qt.TextFormat.PlainText);holiday.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);self.holiday_labels.append(holiday)
        self.badge_timer=QTimer(self);self.badge_timer.setSingleShot(True);self.badge_timer.timeout.connect(self._layout_badges)
        self.selectionChanged.connect(lambda:self.selected.emit(self.selectedDate().toPython()))
        self._badge_viewport=self.view.viewport();self._badge_viewport.installEventFilter(self)

    def set_month(self,month,selected,buckets,holidays=None,feasts=None):
        self.buckets=buckets;self.holidays=holidays or {};self.feasts=feasts or {}
        if self.feasts and not self.feast_labels:
            for _ in range(42):
                label=QLabel(self.view.viewport());label.setObjectName('feastName');label.setTextFormat(Qt.TextFormat.PlainText);label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);self.feast_labels.append(label)
        if not self.feasts:
            for label in self.feast_labels:label.hide();label.clear();label.setToolTip('')
        self.blockSignals(True)
        self.setCurrentPage(month.year,month.month);self.setSelectedDate(QDate(selected.year,selected.month,selected.day))
        self.blockSignals(False)
        for old in self._formatted:self.setDateTextFormat(old,QTextCharFormat())
        self._formatted=set();c=colors()
        for weekday in (Qt.DayOfWeek.Monday,Qt.DayOfWeek.Tuesday,Qt.DayOfWeek.Wednesday,Qt.DayOfWeek.Thursday,Qt.DayOfWeek.Friday):
            fmt=QTextCharFormat();fmt.setForeground(QColor(c['ink']));self.setWeekdayTextFormat(weekday,fmt)
        for weekday,color in ((Qt.DayOfWeek.Sunday,'#D890A4' if c['bg']=='#11151D' else '#AC4265'),(Qt.DayOfWeek.Saturday,c['accent'])):
            fmt=QTextCharFormat();fmt.setForeground(QColor(color));self.setWeekdayTextFormat(weekday,fmt)
        for day in set(buckets)|set(self.holidays)|set(self.feasts):
            if not -7<=(day-month.replace(day=1)).days<45:continue
            rows=buckets.get(day,[])
            q=QDate(day.year,day.month,day.day);fmt=QTextCharFormat()
            fmt.setFontWeight(QFont.Weight.DemiBold);fmt.setForeground(QColor('#BE607C' if day in self.holidays else c['accent']))
            fmt.setToolTip('\n'.join(([self.holidays[day]] if day in self.holidays else [])+([self.feasts[day]] if day in self.feasts else [])+[e.title for e in rows[:6]]));self.setDateTextFormat(q,fmt);self._formatted.add(q)
        self.badge_timer.start(0);self.updateCells()

    def paintCell(self,painter,rect,day):
        # Shapes only. The fixed QLabel pool renders date text natively.
        c=colors();selected=day==self.selectedDate();painter.save();painter.setRenderHint(painter.RenderHint.Antialiasing)
        edge=QColor(c['accent'] if selected else c['line']);edge.setAlpha(190 if selected else 135);painter.setPen(QPen(edge,1));painter.setBrush(QColor(c['soft']) if selected else Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(rect).adjusted(3,3,-3,-3),12,12);painter.restore()

    def eventFilter(self,obj,event):
        if obj is getattr(self,'_badge_viewport',None) and event.type() in (QEvent.Type.Resize,QEvent.Type.Show):self.badge_timer.start(0)
        return super().eventFilter(obj,event)

    def _layout_badges(self):
        if not self.view:return
        first=date(self.yearShown(),self.monthShown(),1)
        # QCalendarWidget includes a complete preceding week when the first
        # falls on the first weekday. Derive the anchor from its actual model
        # instead of assuming the first row always contains this month's 1st.
        try:
            native_first=int(self.view.model().data(self.view.model().index(1,0),Qt.ItemDataRole.DisplayRole))
            start=first if native_first==1 else (first-timedelta(days=1)).replace(day=native_first)
        except (TypeError,ValueError):
            for badge in self.badges:badge.hide()
            for number in self.date_labels:number.hide()
            for holiday in self.holiday_labels:holiday.hide()
            for feast in self.feast_labels:feast.hide()
            return
        for i,badges in enumerate(self.badges):
            rect=self.view.visualRect(self.view.model().index(i//7+1,i%7))
            day=start+timedelta(days=i);rows=self.buckets.get(day,[])
            number=self.date_labels[i];number.setText(str(day.day));number.setGeometry(rect.left()+12,rect.top()+8,max(24,rect.width()-24),22)
            name=self.holidays.get(day,'');state='outside' if day.month!=self.monthShown() else 'holiday' if name else 'selected' if day==self.selectedDate().toPython() else 'today' if day==datetime.now(KST).date() else 'sunday' if day.weekday()==6 else 'saturday' if day.weekday()==5 else 'normal'
            if number.property('dayState')!=state:number.setProperty('dayState',state);number.style().unpolish(number);number.style().polish(number)
            number.show();number.raise_()
            feast_name=self.feasts.get(day,'');tooltip='\n'.join(filter(None,(name,feast_name)))
            number.setToolTip(tooltip);number.setAccessibleName(day.isoformat()+(' / '+tooltip if tooltip else ''))
            holiday=self.holiday_labels[i];holiday.setProperty('calendarDate',day.isoformat());holiday.setGeometry(rect.left()+12,rect.top()+31,max(1,rect.width()-24),17);holiday.setToolTip(name);holiday.setAccessibleName(name)
            text_bottom=rect.bottom()-(26 if rows else 8)
            holiday.setText(holiday.fontMetrics().elidedText(name,Qt.TextElideMode.ElideRight,max(1,rect.width()-24)));holiday.setVisible(bool(name) and day.month==self.monthShown() and holiday.geometry().bottom()<text_bottom)
            if self.feast_labels:
                feast=self.feast_labels[i];feast.setProperty('calendarDate',day.isoformat());feast.setGeometry(rect.left()+12,rect.top()+(49 if name else 31),max(1,rect.width()-24),17);feast.setToolTip(feast_name);feast.setAccessibleName(feast_name)
                feast.setText(feast.fontMetrics().elidedText(feast_name,Qt.TextElideMode.ElideRight,max(1,rect.width()-24)));feast.setVisible(bool(feast_name) and day.month==self.monthShown() and feast.geometry().bottom()<text_bottom)
            badges.setProperty('calendarDate',day.isoformat())
            badges.set_events(day,rows)
            if day.month!=self.monthShown() or not rows:badges.hide();continue
            a=sum(e.kind=='assignment' and e.type_id is None and not e.completed for e in rows);done=sum(e.kind=='assignment' and e.type_id is None and e.completed for e in rows);v=sum(e.kind=='movie' and e.type_id is None for e in rows)
            groups={}
            for event in rows:
                if event.type_id is not None:
                    key=(event.type_label,event.type_color,event.kind=='assignment' and event.completed);groups[key]=groups.get(key,0)+1
            custom=[(name,count,color,completed) for (name,color,completed),count in groups.items()]
            available=max(1,rect.height()-25)
            height=badges.configure(a,v,max(18,rect.width()-16),available,custom,assignment_done=done)
            badges.setGeometry(rect.left()+8,rect.bottom()-height-8,max(18,rect.width()-16),height)
            badges.show()
