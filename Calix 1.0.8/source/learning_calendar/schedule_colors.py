"""Stable course accents; persisted values are portable hex colors."""
import re
PALETTE=(('#7582E6','퍼플'),('#459CD4','스카이'),('#3AA68E','민트'),('#CF779A','로즈'),
         ('#CA9A46','앰버'),('#D48560','코랄'),('#86A85A','올리브'),('#778BA7','슬레이트'))
def course_color(course_id):return PALETTE[int(course_id)%len(PALETTE)][0]
def normalize_color(value):
    value=str(value or '').strip().upper()
    if value and not re.fullmatch(r'#[0-9A-F]{6}',value):raise ValueError('색상은 #RRGGBB 형식으로 입력하세요.')
    return value
def minutes(value):
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',str(value)):raise ValueError('시간을 HH:mm 형식으로 입력하세요.')
    h,m=map(int,value.split(':'));return h*60+m
def clock(value):return f'{int(value)//60:02d}:{int(value)%60:02d}'
