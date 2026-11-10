"""Run parser checks without requiring PySide6 or network."""
from pathlib import Path
import ast,re,html,unicodedata,bisect
from datetime import date
from urllib.parse import urljoin,urlparse,parse_qs
from difflib import SequenceMatcher
from bs4 import BeautifulSoup,NavigableString,Tag
source=Path(__file__).with_name('main.py').read_text(encoding='utf-8')
module=ast.parse(source)
# Import only pure parser functions and their module constants.
functions={'choose_official_entry','event_name_match_score','is_official_event_url','choose_content','render_event_html','split_events','_safe_attr','parse_event_dates','parse_period','parse_explicit_range','restyle_html','event_key','catalog_event_key','choose_official_period','date_of_post_title','parse_official_event_list','_find_card_event_link','_event_link_from_click_handler','_link_name_keys'}
lines=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name in functions]
code=compile(ast.Module(body=lines,type_ignores=[]),'parser','exec')
ns={'re':re,'html':html,'unicodedata':unicodedata,'date':date,'urljoin':urljoin,'urlparse':urlparse,'parse_qs':parse_qs,'SequenceMatcher':SequenceMatcher,'BeautifulSoup':BeautifulSoup,'NavigableString':NavigableString,'Tag':Tag,'BASE':'https://ge.hanbiton.com'}
exec(code,ns)
for name in ('HEADING','SECTION_MARKER','SECTION_STOP','POST_YEAR','POST_DAY','DATE_TOKEN_NO_GROUP','THROUGH_RE','RANGE_RE','OFFICIAL_PERIOD_RE','HTML_TAGS','HTML_ATTRS'):
 node=next(n for n in module.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
 exec(compile(ast.Module(body=[node],type_ignores=[]),'constants','exec'),ns)
page='''<html><body><div class="view_content"><p>다음은 이벤트에 해당하는 사항입니다.</p>
<p>1. 서머 이벤트 - ‘기간떼 달리기 대회’ 이벤트가 시작됩니다.</p>
<p><img src="/images/gigante.jpg" alt="banner"/></p>
<p>일일 보상을 획득할 수 있습니다.</p>
<table><tr><th>아이템명</th><th>수량</th></tr><tr><td>프랜스펄 앰플</td><td>3</td></tr></table>
<p>2. ‘바다를 지켜줘’ 이벤트가 종료됩니다.</p>
<p>다음은 판매 시작에 해당하는 사항입니다.</p></div></body></html>'''
events=ns['split_events'](BeautifulSoup(page,'html.parser'),'2026년 8월 6일 업데이트','670919','https://ge.hanbiton.com/NewsInfo/UpdateCompleteView.aspx?postKey=670919')
assert len(events)==1,events
one=events[0]
assert one['name']=='서머 이벤트 - ‘기간떼 달리기 대회’ 이벤트',one['name']
assert 'banner' not in one,one
assert '<table' in one['body_html'] and '프랜스펄 앰플' in one['body_html']
assert '<img' not in one['body_html']
assert '<img' not in ns['restyle_html']('<table><tr><td><img src="old.png"/>보상</td></tr></table>')
assert ns['catalog_event_key']('서머 이벤트 - ‘기간떼 달리기 대회’ 이벤트')==ns['catalog_event_key']('기간떼 달리기 대회')
period=ns['choose_official_period']('서머 이벤트 - ‘기간떼 달리기 대회’ 이벤트','2026년 8월 6일 업데이트', [('기간떼 달리기 대회','2026-08-06','2026-08-27','https://ge.hanbiton.com/event/summer')])
assert period==('2026-08-06','2026-08-27','https://ge.hanbiton.com/event/summer'),period
assert ns['parse_event_dates']('11월 5일(목) 0시 ~ 12월 17일(목) 24시','2026년 11월 5일 공지')==('2026-11-05','2026-12-17')
assert not ns['split_events'](BeautifulSoup(page.replace('시작됩니다','종료됩니다'),'html.parser'),'2026년 8월 6일 업데이트','670919','https://ge.hanbiton.com/test')
assert '이벤트' in one['name']
print('PASS: 9 parser checks; full title, quotes, no banner, closing notices, tables, image stripping, official date and date ranges')
