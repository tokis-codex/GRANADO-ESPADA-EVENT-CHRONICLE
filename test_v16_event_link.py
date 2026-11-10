"""Checks event links found in official clickable cards, without network or Qt."""
import ast, html, re, unicodedata
from pathlib import Path
from datetime import date
from urllib.parse import urljoin, urlparse, parse_qs
from difflib import SequenceMatcher
from bs4 import BeautifulSoup, NavigableString
source=Path(__file__).with_name('main.py').read_text(encoding='utf-8')
tree=ast.parse(source)
names={'event_key','catalog_event_key','is_official_event_url','_event_link_from_click_handler','_find_card_event_link','parse_official_event_list','_link_name_keys','event_name_match_score','date_of_post_title','choose_official_entry'}
ns=dict(re=re, html=html, unicodedata=unicodedata,date=date,urljoin=urljoin,urlparse=urlparse,parse_qs=parse_qs,SequenceMatcher=SequenceMatcher,BeautifulSoup=BeautifulSoup,NavigableString=NavigableString,BASE='https://ge.hanbiton.com',POST_DAY=re.compile(r'(20\d{2})년\s*(\d{1,2})월\s*(\d{1,2})일'), OFFICIAL_PERIOD_RE=re.compile(r'(20\d{2})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})\s*[~～∼–—]\s*(20\d{2})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})'))
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'test_source','exec'),ns)
fixture='''<ul>
<li class="card" onclick="goEventView('7207')">
  <a href="/boarddata/event/2026/11/5/thumbnail.jpg"><img alt="Black Out 기념 이벤트" src="/thumb.jpg"/></a>
  <p>이벤트 기간</p><p>2026.11.05 ~ 2026.12.24</p>
</li>
<li class="card" data-url="/NewsInfo/EventView.aspx?eid=7107&amp;etype=0">
  <a href="/boarddata/event/2026/8/3/cover.jpg"><img alt="기간떼 달리기 대회" src="/cover.jpg"/></a>
  <p>이벤트 기간</p><p>2026.08.06 ~ 2026.08.27</p>
</li>
<li class="card">
  <a href="/boarddata/event/2026/8/3/cover.jpg"><img alt="연결 주소 없는 이벤트"/></a>
  <span>이벤트 기간</span><span>2026.08.06 ~ 2026.08.27</span>
</li></ul>'''
rows=ns['parse_official_event_list'](BeautifulSoup(fixture,'html.parser'))
assert len(rows)==3, rows
assert rows[0][3]=='https://ge.hanbiton.com/NewsInfo/EventView.aspx?eid=7207&etype=0', rows
assert rows[1][3]=='https://ge.hanbiton.com/NewsInfo/EventView.aspx?eid=7107&etype=0', rows
assert rows[2][3]=='', rows
assert ns['choose_official_entry']('[Black Out] 업데이트 기념 웹 이벤트','2026-11-05','2026-12-24','2026년 11월 5일 업데이트',rows)[2].endswith('eid=7207&etype=0')
assert ns['choose_official_entry']('[Black Out] 업데이트 기념 웹 이벤트','2026-10-29','2026-12-31','2026년 11월 5일 업데이트',rows) is None
assert ns['_event_link_from_click_handler']("location.href='/NewsInfo/EventView.aspx?eid=7201&etype=0'").endswith('eid=7201&etype=0')
print('PASS: thumbnail ignored; onclick/data-url recognized; no URL invented; Black Out matching guarded')
