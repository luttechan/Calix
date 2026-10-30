"""Build-only dependency: pip install holidays==0.107. No runtime dependency."""
from pathlib import Path
import json
import holidays

root=Path(__file__).resolve().parents[1];target=root/'asset/calendar';target.mkdir(parents=True,exist_ok=True)
def display_name(name):
    for before,after in (('설날 전날','설날 연휴'),('설날 다음날','설날 연휴'),('추석 전날','추석 연휴'),('추석 다음날','추석 연휴'),('기독탄신일','크리스마스'),('신정연휴','신정')):name=name.replace(before,after)
    return name.replace('; ',' / ').replace('·',' / ')
years={str(year):{day.isoformat():display_name(name) for day,name in sorted(holidays.KR(years=year,language='ko').items())} for year in range(2020,2051)}
assert years['2026']['2026-05-01']=='노동절' and years['2026']['2026-07-17']=='제헌절'
assert '2027-05-03' in years['2027'] and '2027-07-19' in years['2027']
value=dict(version=1,as_of='2026-10-27',generator='holidays '+holidays.__version__,official_source='https://www.data.go.kr/data/15012690/openapi.do',years=years)
(target/'kr_public_holidays.json').write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'{len(years)} years / {sum(map(len,years.values()))} holiday dates')
