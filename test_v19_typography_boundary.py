"""Regression for v19 event cutoff and displayed title; no network or Qt imports."""
from pathlib import Path
import ast, re, html, unicodedata, bisect
from datetime import date
from urllib.parse import urljoin,urlparse,parse_qs
from bs4 import BeautifulSoup,NavigableString,Tag
from difflib import SequenceMatcher
src=Path(__file__).with_name('main.py').read_text(encoding='utf-8')
tree=ast.parse(src)
funcs={'choose_content','render_event_html','split_events','_safe_attr','parse_event_dates','parse_period','parse_explicit_range'}
ns={'re':re,'html':html,'unicodedata':unicodedata,'date':date,'urljoin':urljoin,'urlparse':urlparse,'parse_qs':parse_qs,'SequenceMatcher':SequenceMatcher,'BeautifulSoup':BeautifulSoup,'NavigableString':NavigableString,'Tag':Tag}
for node in tree.body:
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'HEADING','SECTION_MARKER','SECTION_STOP','POST_YEAR','POST_DAY','DATE_TOKEN_NO_GROUP','THROUGH_RE','RANGE_RE','HTML_TAGS','HTML_ATTRS'} for t in node.targets):
  exec(compile(ast.Module(body=[node],type_ignores=[]),'globals','exec'),ns)
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in funcs],type_ignores=[]),'parser','exec'),ns)
page='''<div class="view_content"><p>다음은 이벤트에 해당하는 사항입니다.</p>
<p>1. 할로윈 이벤트 ‘트릭 오어 트릿!’ 이벤트가 시작됩니다.</p>
<p>이벤트 참여 방법입니다.</p><table><tr><td>보상 아이템</td><td>3개</td></tr></table>
<p>다음은 오탈자에 해당하는 사항입니다.</p><p>일반 업데이트 오탈자 정정입니다.</p>
<p>2. 다른 이벤트가 시작됩니다.</p><p>이벤트 밖 내용입니다.</p></div>'''
events=ns['split_events'](BeautifulSoup(page,'html.parser'),'2026년 10월 29일 업데이트','test19','https://ge.hanbiton.com/test')
assert len(events)==1,events
assert events[0]['name']=='할로윈 이벤트 ‘트릭 오어 트릿!’ 이벤트',events[0]['name']
for field in ('body','body_html'):
 assert '보상 아이템' in events[0][field]
 assert '다음은 오탈자' not in events[0][field]
 assert '오탈자 정정' not in events[0][field]
 assert '다른 이벤트' not in events[0][field]
assert '<table' in events[0]['body_html']
assert "self.setWindowTitle('GRANADO ESPADA · EVENT CHRONICLE')" in src
assert "title=QLabel('GRANADO ESPADA · EVENT CHRONICLE')" in src
assert "--name GE_Event" in Path(__file__).with_name('build_windows.bat').read_text()
print('PASS: event boundary, no post-event data, table retention, UI titles, executable name unchanged')
