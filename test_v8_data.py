"""Headless checks for image migration, real links and persistent hidden selections."""
from pathlib import Path
import ast, sqlite3, tempfile, html, re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from difflib import SequenceMatcher
from datetime import date
source=Path(__file__).with_name('main.py').read_text(encoding='utf-8')
module=ast.parse(source)
names={'date_of_post_title','choose_official_entry','event_name_match_score','is_official_event_url','migrate_remove_images','event_url_for_record','catalog_event_key','event_key'}
functions=[node for node in module.body if isinstance(node,ast.FunctionDef) and node.name in names]
ns={'BeautifulSoup':BeautifulSoup,'sqlite3':sqlite3,'html':html,'urljoin':urljoin,'urlparse':urlparse,'parse_qs':parse_qs,'SequenceMatcher':SequenceMatcher,'date':date,'POST_DAY':re.compile(r'(20\d{2})년\s*(\d{1,2})월\s*(\d{1,2})일'),'BASE':'https://ge.hanbiton.com'}
import re,unicodedata
ns.update(re=re,unicodedata=unicodedata)
exec(compile(ast.Module(body=functions,type_ignores=[]),'main.py','exec'),ns)
with tempfile.TemporaryDirectory() as folder:
    conn=sqlite3.connect(str(Path(folder)/'events.db'))
    conn.executescript('''CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
    CREATE TABLE event_banners(url TEXT PRIMARY KEY,mime TEXT,data BLOB);
    CREATE TABLE events(event_id TEXT PRIMARY KEY,body_html TEXT,banner_url TEXT);
    CREATE TABLE user_hidden_events(event_id TEXT PRIMARY KEY);
    CREATE TABLE official_event_periods(name TEXT,start_date TEXT,end_date TEXT,event_url TEXT);''')
    conn.execute('INSERT INTO events VALUES(?,?,?)',('post:1','<table><tr><td>보상<img src="x.png"/></td><td>3</td></tr></table>','https://ge.hanbiton.com/x.png'))
    conn.execute('INSERT INTO event_banners VALUES(?,?,?)',('url','image/png',b'images'*5000))
    conn.execute('INSERT INTO user_hidden_events VALUES(?)',('post:1',))
    conn.commit()
    ns['migrate_remove_images'](conn)
    assert conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='event_banners'").fetchone() is None
    body,link=conn.execute('SELECT body_html,banner_url FROM events').fetchone()
    assert '<img' not in body and '<table>' in body and '>3<' in body and not link
    assert conn.execute('SELECT event_id FROM user_hidden_events').fetchone()[0]=='post:1'
    ns['migrate_remove_images'](conn)  # safe repeated invocation
    html_body='<p><a href="/event/2026/10/blackout/event.html">공식 이벤트 페이지</a></p>'
    target=ns['event_url_for_record'](conn,'Black Out','2026-10-29','2026-12-31',html_body)
    assert target=='https://ge.hanbiton.com/event/2026/10/blackout/event.html'
    assert not ns['event_url_for_record'](conn,'no link',None,None,'<a href="https://bad.example/event/a">link</a>')
    conn.close()
print('PASS: legacy images removed, tables preserved, saved hide retained, real-only links')
