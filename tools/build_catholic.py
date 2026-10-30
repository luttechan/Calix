"""Keep only public calendar facts: dates and feast/memorial names, not readings."""
import json,re,urllib.request
from html.parser import HTMLParser
from datetime import date
from pathlib import Path

SOURCE='https://missa.cbck.or.kr/MissaLoad'
class Text(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[]
    def handle_data(self,data):self.parts.append(data)
    def handle_starttag(self,tag,attrs):
        if tag=='br':self.parts.append(' ')
def titles(raw):
    parser=Text();parser.feed(raw);value=' '.join(''.join(parser.parts).split());value=value.replace('·',' / ')
    if '전야' in value:return []
    value=re.sub(r'\[(?:백|홍|녹|자|흑|장미|금)\]\s*','',value)
    value=re.sub(r'\s+[-–]\s+.*$','',value)
    output=[]
    for index,part in enumerate(value.split('또는')):
        part=part.strip()
        if index>0 or any(word in part for word in ('축일','기념일','재의 수요일','주님 만찬','주님 수난','파스카 성야','위령의 날','대림 제1주일')) or re.search(r'(?:^|\s)(성(?:녀)?\s|복(?:자|녀)\s|복되신|티 없이|지극히)',part):
            if 1<=len(part)<=300:output.append(part)
    return output

root=Path(__file__).resolve().parents[1];years={}
for year in range(2020,2028):
    with urllib.request.urlopen(f'{SOURCE}?start={year}-01-01&end={year+1}-01-01',timeout=20) as response:items=json.load(response)
    days={}
    for item in items:
        day=date.fromisoformat(item['start'][:10])
        if day.year!=year:continue
        for name in titles(item.get('title_html') or item['title']):
            row=days.setdefault(day.isoformat(),[])
            if name not in row:row.append(name)
    if len(days)<150:raise ValueError(f'Incomplete official feast table for {year}: {len(days)}')
    years[str(year)]={day:' / '.join(names) for day,names in sorted(days.items())};print(year,len(days))
target=root/'asset/calendar/catholic_feasts.json'
target.write_text(json.dumps(dict(version=1,as_of='2026-10-27',source='https://missa.cbck.or.kr/Liturgy',years=years),ensure_ascii=False,separators=(',',':')),encoding='utf-8')
