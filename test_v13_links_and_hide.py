"""Parser and data regression (no Qt, internet, or Windows required)."""
import ast, sqlite3, html
from pathlib import Path
from datetime import date
from urllib.parse import urljoin, urlparse,parse_qs
from bs4 import BeautifulSoup,NavigableString
from difflib import SequenceMatcher
import re,unicodedata
src=(Path(__file__).parent/'main.py').read_text(encoding='utf-8')
root=ast.parse(src)
functions={'event_key','catalog_event_key','date_of_post_title','is_official_event_url','parse_official_event_list','_find_card_event_link','_event_link_from_click_handler','_link_name_keys','event_name_match_score','choose_official_entry','event_url_for_record','set_manual_hidden','filter_visible_events','valid_complete_period'}
sel=[n for n in root.body if isinstance(n,ast.FunctionDef) and n.name in functions]
assert {n.name for n in sel}==functions
ns=dict(html=html,re=re,sqlite3=sqlite3,date=date,urlparse=urlparse,urljoin=urljoin,parse_qs=parse_qs,BeautifulSoup=BeautifulSoup,NavigableString=NavigableString,SequenceMatcher=SequenceMatcher,unicodedata=unicodedata,BASE='https://ge.hanbiton.com',POST_DAY=re.compile(r'(20\d{2})년\s*(\d{1,2})월\s*(\d{1,2})일'),OFFICIAL_PERIOD_RE=re.compile(r'(20\d{2})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})\s*[~～∼–—]\s*(20\d{2})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})'))
exec(compile(ast.Module(body=sel,type_ignores=[]),'<selected_functions>','exec'),ns)
fixture='''<html><body>
<div class="card"><span>이벤트 기간</span><div>2026.11.05 ~ 2026.12.24</div><a href="/NewsInfo/EventView.aspx?eid=7207&amp;etype=0"><img alt="Black Out 기념 이벤트" src="/thumbnail.jpg"/>Black Out 기념 이벤..</a></div>
<div class="card"><span>이벤트 기간</span><div>2026.10.29 ~ 2026.12.31</div><a href="/NewsInfo/EventView.aspx?eid=7206&amp;etype=0"><img alt="Black Out" />Black Out</a></div>
</body></html>'''
entries=ns['parse_official_event_list'](BeautifulSoup(fixture,'html.parser'))
assert len(entries)==2,entries
assert entries[0][3]=='https://ge.hanbiton.com/NewsInfo/EventView.aspx?eid=7207&etype=0'
assert entries[1][3].endswith('eid=7206&etype=0')
assert ns['is_official_event_url']('/event-2/2026/260723_SummerEvent/event')
assert not ns['is_official_event_url']('/NewsInfo/EventList.aspx')
assert not ns['is_official_event_url']('/images/header.jpg')
conn=sqlite3.connect(':memory:');conn.execute('CREATE TABLE official_event_periods(name TEXT,start_date TEXT,end_date TEXT,event_url TEXT)')
conn.executemany('INSERT INTO official_event_periods VALUES(?,?,?,?)',entries)
url=ns['event_url_for_record'](conn,'[Black Out] 업데이트 기념 웹 이벤트','2026-11-05','2026-12-24','','2026년 11월 5일 업데이트')
assert 'eid=7207' in url,url
assert ns['event_url_for_record'](conn,'[Black Out] 업데이트 기념 웹 이벤트','2026-10-29','2026-12-31','','2026년 11월 5일 업데이트')==''
assert ns['event_url_for_record'](conn,'아무 이벤트',None,None,'<a href="/event-2/2026/260723_SummerEvent/event">원문</a>') .endswith('/event')
# A row checked while global filter is ON vanishes without a second toggle.
conn.execute('CREATE TABLE user_hidden_events(event_id TEXT PRIMARY KEY)')
rows=[('active','A','2026-11-01','2099-01-01'),('old','B','2020-01-01','2020-01-31')]
ns['set_manual_hidden'](conn,'active',True)
hidden={x[0] for x in conn.execute('SELECT event_id FROM user_hidden_events')}
assert ns['filter_visible_events'](rows,hidden,True,'2026-11-06')==[]
assert len(ns['filter_visible_events'](rows,hidden,False,'2026-11-06'))==2
ns['set_manual_hidden'](conn,'active',False)
assert len(ns['filter_visible_events'](rows,set(),True,'2026-11-06'))==1
assert 'if self.hide.isChecked():\n   QTimer.singleShot(0,self.populate)' in src
assert '숨긴 이벤트 보기' not in src
print('PASS: official EventView links, matching, wrong-date guards, direct links, immediate hide + restore')
