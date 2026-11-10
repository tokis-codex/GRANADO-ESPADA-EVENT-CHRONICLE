import sys, re, sqlite3, html, unicodedata
from pathlib import Path
from datetime import date, datetime
from urllib.parse import urljoin, urlparse, parse_qs
from difflib import SequenceMatcher
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QCheckBox,QLabel,QSplitter,QTableWidget,QTableWidgetItem,QHeaderView,QTextBrowser,QStyledItemDelegate,QStyleOptionViewItem,QStyle,QPushButton)
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QTextCursor, QTextCharFormat
BASE='https://ge.hanbiton.com'
LIST=BASE+'/NewsInfo/UpdateCompleteList.aspx'
ROOT=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
DB=ROOT/'events.db'
PARSER_VERSION=9
HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36'}
ADDED=re.compile(r'\(\s*(?:추가|수정\s*/\s*추가)\s*\)')
DATE_RE=re.compile(r'(\d{1,2})월\s*(\d{1,2})일')
# Only dates in an actual event period are accepted. Independent dates can be
# reward redemption deadlines, dates mentioned in quests, or update references.
PERIOD_RE=re.compile(r'(?:(20\d{2})년\s*)?(\d{1,2})월\s*(\d{1,2})일[^\n~～]{0,90}?[~～]\s*(?:(20\d{2})년\s*)?(\d{1,2})월\s*(\d{1,2})일')
POST_YEAR=re.compile(r'(20\d{2})년')
POST_DAY=re.compile(r'(20\d{2})년\s*(\d{1,2})월\s*(\d{1,2})일')

# A range is accepted only if both endpoints are present; standalone reward
# deadlines must not be mistaken for an event end date.
DATE_TOKEN = r'(?:(?P<year>20\d{2})[.\-/년]\s*)?(?P<month>\d{1,2})[.\-/월]\s*(?P<day>\d{1,2})\s*(?:일)?'
DATE_TOKEN_NO_GROUP = r'(?:(20\d{2})[.\-/년]\s*)?(\d{1,2})[.\-/월]\s*(\d{1,2})\s*(?:일)?'
RANGE_RE = re.compile('('+DATE_TOKEN_NO_GROUP+r')(?:\s|\([^)]{0,30}\)|정기점검|점검|후|전){0,18}(?:~|～|∼|–|—|부터|에서|\bto\b)\s*('+DATE_TOKEN_NO_GROUP+r')',re.I)
THROUGH_RE = re.compile('('+DATE_TOKEN_NO_GROUP+r')\s*(?:정기점검\s*후|점검\s*후)?\s*부터.{0,95}?('+DATE_TOKEN_NO_GROUP+r')\s*(?:정기점검\s*전|점검\s*전)?\s*까지', re.S)

def parse_explicit_range(line, fallback_year):
    # Handles weekday annotations and time: 11월 5일(목) 0시 ~ 12월 17일(목) 24시
    dates=list(re.finditer(DATE_TOKEN_NO_GROUP,line))
    for i in range(len(dates)-1):
        left,right=dates[i],dates[i+1]
        between=line[left.end():right.start()]
        if len(between)>85 or not re.search(r'~|～|∼|–|—|부터',between):continue
        ay,am,ad=left.groups();by,bm,bd=right.groups()
        try:
            year=int(ay or fallback_year)
            end_year=int(by) if by else year+(int(bm)<int(am))
            a=date(year,int(am),int(ad));b=date(end_year,int(bm),int(bd))
            if b>=a:return a.isoformat(),b.isoformat()
        except ValueError:pass
    return None,None

def parse_period(body, post_title):
    year_match=POST_YEAR.search(post_title)
    default_year=int(year_match.group(1)) if year_match else date.today().year
    # Prefer the announcement's actual event period, not its later reward deadline.
    for line in body.splitlines():
        if ('진행됩니다' in line or '이벤트 기간' in line or '진행 기간' in line or '진행기간' in line):
            start,end=parse_explicit_range(line,default_year)
            if start:return start,end
    for line in body.splitlines():
        start,end=parse_explicit_range(line,default_year)
        if start:return start,end
    normalized=re.sub(r'\s+',' ',body.replace('\xa0',' '))
    for pattern in (THROUGH_RE,RANGE_RE):
        for match in pattern.finditer(normalized):
            captures=match.groups()
            sy,sm,sd=captures[1:4]
            ey,em,ed=captures[5:8]
            if not sy and default_year is None:continue
            sy=int(sy) if sy else default_year
            ey=int(ey) if ey else sy+(int(em)<int(sm))
            try:
                start,end=date(sy,int(sm),int(sd)),date(ey,int(em),int(ed))
            except ValueError:continue
            if end>=start:return start.isoformat(),end.isoformat()
    # Some event notices state the dates on separate lines, such as
    # "기간: 11월 5일 정기점검 후" / "종료: 12월 17일 점검 전".
    clean=re.sub(r'\s+',' ',body)
    labels=re.search(r'(?:이벤트\s*)?(?:진행\s*)?기간\s*[:：]\s*(.{0,180})',clean)
    if labels:
        dates=list(re.finditer(DATE_TOKEN_NO_GROUP,labels.group(1)))
        if len(dates)>=2:
            a,b=dates[:2]; ay,am,ad=a.groups();by,bm,bd=b.groups()
            try:
                sy=int(ay or default_year);ey=int(by or (sy+(int(bm)<int(am))))
                start=date(sy,int(am),int(ad));end=date(ey,int(bm),int(bd))
                if end>=start:return start.isoformat(),end.isoformat()
            except ValueError:pass
    return None,None

def parse_event_dates(body, post_title):
    start,end=parse_period(body,post_title)
    if start:return start,end
    first=next((line.strip() for line in body.splitlines() if line.strip()),'')
    if re.search(r'이벤트(?:가|의\s*기간이)?\s*종료됩니다',first):
        posted=POST_DAY.search(post_title)
        if posted:
            try:return None,date(*map(int,posted.groups())).isoformat()
            except ValueError:pass
    return None,None

def db():
 c=sqlite3.connect(DB,timeout=15)
 c.execute('PRAGMA journal_mode=WAL')
 c.execute('CREATE TABLE IF NOT EXISTS posts (post_id TEXT PRIMARY KEY,title TEXT NOT NULL,added_seen INTEGER NOT NULL DEFAULT 0,checked_at TEXT NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY,post_id TEXT NOT NULL,name TEXT NOT NULL,start_date TEXT,end_date TEXT,body_html TEXT NOT NULL,body_text TEXT NOT NULL,source_url TEXT NOT NULL,banner_url TEXT DEFAULT "")')
 cols={r[1] for r in c.execute('PRAGMA table_info(posts)')}
 if 'parser_version' not in cols:c.execute('ALTER TABLE posts ADD COLUMN parser_version INTEGER NOT NULL DEFAULT 0')
 c.execute('CREATE TABLE IF NOT EXISTS user_hidden_events (event_id TEXT PRIMARY KEY)')
 c.execute('''CREATE TABLE IF NOT EXISTS event_highlights (
  highlight_id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL, start_pos INTEGER NOT NULL, end_pos INTEGER NOT NULL,
  selected_text TEXT NOT NULL, color TEXT NOT NULL)''')
 c.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
 c.commit();return c

def fetch(session,url):
 r=session.get(url,timeout=(8,22));r.raise_for_status();r.encoding=r.apparent_encoding if r.encoding and r.encoding.lower()=='iso-8859-1' else (r.encoding or 'utf-8');return BeautifulSoup(r.text,'html.parser')

def get_posts(soup):
 out=[];seen=set()
 for a in soup.select('a[href]'):
  href=urljoin(BASE,a.get('href',''));p=urlparse(href)
  if 'UpdateCompleteView.aspx' not in p.path:continue
  key=parse_qs(p.query).get('postKey',[''])[0]
  if not key or key in seen:continue
  seen.add(key);out.append((key,a.get_text(' ',strip=True),href))
 return out

def choose_content(soup):
 # Read the actual update body rather than navigation/footer text.
 for selector in ('.view_content', '.board_view', '.view_cont', '#divContent', 'article'):
  el=soup.select_one(selector)
  if el and '이벤트에 해당하는 사항' in el.get_text(' ',strip=True):return el
 for node in soup.find_all(string=re.compile(r'이벤트에\s*해당하는\s*사항')):
  for ancestor in node.parents:
   if ancestor.name in ('html','body'):break
   content=ancestor.get_text(' ',strip=True)
   if len(content)>400 and '이벤트가 시작됩니다' in content:return ancestor
 return soup

HEADING = re.compile(r'(?m)^\s*(\d{1,2})\.\s*([^\n]{2,220}?이벤트(?:가|의\s*기간이)?\s*(?:시작됩니다|종료됩니다|연장됩니다|변경됩니다))\s*[.。]?\s*$')
SECTION_MARKER = re.compile(r'다음은\s*이벤트에\s*해당하는\s*사항입니다\s*[.。]?')
SECTION_STOP = re.compile(r'다음은\s*(?:(?:판매\s*시작|판매\s*종료|캐시|기타|신규\s*가문).*?|오탈자에\s*)해당하는\s*사항입니다\s*[.。]?')
HTML_ATTRS = {'href','title','colspan','rowspan','width','height','align','valign'}
HTML_TAGS = {'div','span','p','br','hr','table','thead','tbody','tfoot','tr','td','th','ul','ol','li','strong','b','em','i','u','font','a','h1','h2','h3','h4','blockquote','center','small'}

def _safe_attr(tag,key,value,url):
    if isinstance(value,list):value=' '.join(value)
    value=str(value)
    if key in ('href','src'):
        value=urljoin(url,value)
        if urlparse(value).scheme not in ('http','https'):return None
    if key=='style':
        # Keep only basic table appearance, not arbitrary CSS or script urls.
        parts=[]
        allow={'color','background','background-color','font-size','font-weight','font-family','text-align','vertical-align','border','border-collapse','padding','margin','width','height'}
        for decl in value.split(';'):
            if ':' not in decl:continue
            k,v=decl.split(':',1)
            if k.strip().lower() in allow and not re.search(r'url\s*\(|expression|@import',v,re.I):parts.append(k.strip()+':'+v.strip())
        value=';'.join(parts)
    return value

def render_event_html(content, start_idx, stop_idx, tokens, url):
    # Copy only the original DOM nodes located inside one event. Ancestor tags
    # are retained so original <table>/<tr>/<td> organization is not flattened.
    node_index={id(node):i for i,node in enumerate(tokens)}
    def render(node):
        if isinstance(node,NavigableString):
            index=node_index.get(id(node),-1)
            return html.escape(str(node)) if start_idx<=index<stop_idx else ''
        if not isinstance(node,Tag):return ''
        if node.name in ('script','style','iframe','form','input','button','video','audio'):return ''
        if node.name=='img':return ''  # body remains text and tables only
        inner=''.join(render(child) for child in node.children)
        if not inner or not inner.strip():return ''
        if node.name not in HTML_TAGS:return inner
        attrs=[]
        for key,value in node.attrs.items():
            if key not in HTML_ATTRS or key in ('src','alt'):continue
            sanitized=_safe_attr(node,key,value,url)
            if sanitized is not None:attrs.append(f' {key}="{html.escape(sanitized,quote=True)}"')
        if node.name=='table' and not any(a.startswith(' border=') for a in attrs):attrs.append(' border="1"')
        return f'<{node.name}{"".join(attrs)}>{inner}</{node.name}>'
    return render(content)

def split_events(soup,title,post_id,url):
    content=choose_content(soup)
    tokens=[n for n in content.descendants if isinstance(n,NavigableString) or (isinstance(n,Tag) and n.name=='img')]
    # A newline between text nodes matches BeautifulSoup's original text mode.
    parts=[str(n).strip().replace('\xa0',' ') if isinstance(n,NavigableString) else '' for n in tokens]
    joined='\n'.join(parts)
    marker=SECTION_MARKER.search(joined)
    if not marker:return []
    section_start=marker.end()
    stop_match=SECTION_STOP.search(joined,section_start)
    section_end=stop_match.start() if stop_match else len(joined)
    section=joined[section_start:section_end]
    # Headings can be split into separate number and title DOM text nodes.
    section=re.sub(r'(?m)^(\d{1,2})\.\s*\n\s*',r'\1. ',section)
    matches=list(HEADING.finditer(section))
    if not matches:return []
    # The rewritten section may have different offsets; map each title by
    # searching the unmodified joined stream in sequential order.
    offsets=[];position=section_start
    for match in matches:
        title_fragment=match.group(2).strip()
        found=joined.find(title_fragment,position,section_end)
        if found<0:continue
        # Include numbering where located directly before the title text.
        digit=re.search(r'\d{1,2}\.\s*$',joined[max(section_start,found-35):found])
        begin=max(section_start,found-35)+digit.start() if digit else found
        offsets.append((begin,match))
        position=found+len(title_fragment)
    if not offsets:return []
    token_start=[];p=0
    for item in parts:
        token_start.append(p);p+=len(item)+1
    import bisect
    result=[]
    for i,(begin,match) in enumerate(offsets):
        end=offsets[i+1][0] if i+1<len(offsets) else section_end
        first=max(0,bisect.bisect_right(token_start,begin)-1)
        last=min(len(tokens),bisect.bisect_left(token_start,end))
        body=joined[begin:end].strip()
        # Remove announcement verbs only. The word '이벤트' belongs to the title.
        name=re.sub(r'(?:가|의\s*기간이)\s*(?:시작됩니다|종료됩니다|연장됩니다|변경됩니다)[.。]?\s*$','',match.group(2)).strip()
        start,finish=parse_event_dates(body,title)
        body_html=render_event_html(content,first,last,tokens,url)
        if re.search(r'이벤트(?:가|의\s*기간이)?\s*종료됩니다',match.group(2)):
            continue  # Closing notices must not create an event row.
        result.append(dict(event_id=f'{post_id}:{match.group(1)}',post_id=post_id,name=name,start=start,end=finish,body=body,body_html=body_html,url=url))
    return result


def repair_saved_dates(c):
 # Repair legacy entries without deleting event data or re-downloading old posts.
 # A one-time migration avoids repeating this work at every startup.
 c.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
 row=c.execute("SELECT value FROM meta WHERE key='date_parser_version'").fetchone()
 if row and int(row[0])>=5:return
 with c:
  entries=c.execute('''SELECT e.event_id,e.body_text,p.title
                       FROM events e LEFT JOIN posts p ON e.post_id=p.post_id''').fetchall()
  for event_id,body,title in entries:
   if not title:continue
   start,end=parse_event_dates(body,title)
   c.execute('UPDATE events SET start_date=?,end_date=? WHERE event_id=?',(start,end,event_id))
  c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('date_parser_version','5')")

def event_key(name):
    """Canonical comparison key, preserving events with different actual periods."""
    name=unicodedata.normalize('NFKC', name)
    name=re.sub(r'[\s\u200b\u00a0]+','',name)
    name=re.sub(r'[‘’“”\"\'「」『』]', '',name)
    return name.casefold()

# The official Events listing is an independent source for event dates.
# Update announcements often contain no date range (e.g. postKey=670919).
OFFICIAL_PERIOD_RE = re.compile(r'(20\d{2})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})\s*[~～∼–—]\s*(20\d{2})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})')

def catalog_event_key(name):
    name = re.sub(r'^\s*서머\s*이벤트\s*[-:：]\s*', '', name, flags=re.I)
    # The event-specific name is usually quoted inside a broader announcement heading.
    quoted = re.findall(r'[‘\\"「『]([^’\\"」』]{2,100})[’\\"」』]', name)
    if quoted:
        name = quoted[-1]
    name = re.sub(r'\s*이벤트\s*$', '', name)
    return event_key(name)

def is_official_event_url(value):
    """EventView.aspx is the actual link on the official event catalog.

    Some campaigns use /event/ or /event-2/ instead. Ignore general site,
    image and catalog links; only return a real campaign destination.
    """
    if not value:return False
    parsed=urlparse(urljoin(BASE,value))
    if parsed.scheme not in ('https','http') or (parsed.hostname or '').lower()!='ge.hanbiton.com':return False
    path=parsed.path.lower()
    if path.endswith('/newsinfo/eventview.aspx'):
        return bool(parse_qs(parsed.query).get('eid',[''])[0])
    return path.startswith(('/event/','/event-2/')) and not path.endswith(('.png','.gif','.jpg','.jpeg','.webp','.ico'))


def _event_link_from_click_handler(value):
    """Resolve only an event ID/URL actually present in the official page markup.

    The GE event listing may wrap an image hyperlink around a thumbnail while
    using onclick on the card for the *real* event detail. A thumbnail href
    must never be mistaken for the event destination.
    """
    if not value:
        return ''
    from urllib.parse import unquote
    decoded=html.unescape(unquote(str(value))).replace('\\/', '/')
    # Explicit URLs in onclick/location/javascript/data attributes.
    for match in re.finditer(r'(?:https?://ge\.hanbiton\.com)?/?(?:NewsInfo/)?EventView\.aspx\?[^\\\"\'<>\s)]+',decoded,re.I):
        candidate=match.group(0).rstrip(';,')
        if is_official_event_url(candidate):
            return urljoin(BASE+'/',candidate.lstrip('/')) if not candidate.startswith('http') else candidate
    for match in re.finditer(r'(?:https?://ge\.hanbiton\.com)?/event(?:-2)?/[^\\\"\'<>\s)]+',decoded,re.I):
        candidate=match.group(0).rstrip(';,')
        if is_official_event_url(candidate):
            return urljoin(BASE+'/',candidate.lstrip('/')) if not candidate.startswith('http') else candidate
    # Event ID used as a parameter in Javascript (not image IDs or page IDs).
    m=re.search(r'\b(?:eid|event[_-]?id)\s*[:=]\s*[\"\']?(\d{3,9})\b',decoded,re.I)
    if not m:
        m=re.search(r'\b(?:go|open|view|fn|show)[_\w]*(?:event|evt)[_\w]*\s*\(\s*[\"\']?(\d{3,9})\b',decoded,re.I)
    if not m:
        m=re.search(r'\b(?:event|evt)[_\w]*(?:go|open|view|detail)[_\w]*\s*\(\s*[\"\']?(\d{3,9})\b',decoded,re.I)
    if m:
        return BASE+'/NewsInfo/EventView.aspx?eid='+m.group(1)+'&etype=0'
    return ''


def _find_card_event_link(card):
    """Find a verifiable landing-page URL, not a linked thumbnail."""
    for node in [card]+list(card.find_all(True)):
        if node.name == 'a' and is_official_event_url(node.get('href','')):
            return urljoin(BASE,node['href'])
        for key,value in node.attrs.items():
            if key in ('href','src','alt','style','class','title') or key.startswith('aria-'):
                continue
            if key=='data-eid' or key=='data-event-id':
                if re.fullmatch(r'\d{3,9}',str(value)):
                    return BASE+'/NewsInfo/EventView.aspx?eid='+str(value)+'&etype=0'
            raw=' '.join(value) if isinstance(value,list) else str(value)
            if key.startswith('on') or key in ('data-url','data-href','data-link','data-onclick','data-event-url'):
                link=_event_link_from_click_handler(raw)
                if link:return link
    return ''


def parse_official_event_list(soup):
    """Extract card title/date/actual URL (also supports JS-clickable cards).

    GE's official listing often exposes thumbnail anchors pointing to .jpg.
    In that case the actual event detail can be in the containing card's
    onclick/data-url, not the image href. Never use the image as a link.
    """
    entries=[];seen=set()
    for period_node in soup.find_all(string=re.compile(r'이벤트\s*기간')):
        if not isinstance(period_node,NavigableString):continue
        candidate=None
        for parent in period_node.parents:
            if parent.name in ('body','html'):break
            text=parent.get_text(' ',strip=True)
            ranges=list(OFFICIAL_PERIOD_RE.finditer(text))
            if len(ranges)!=1 or len(text)>900:continue
            # Don't choose a tiny date-only div; need image title or a heading.
            names=[img.get('alt','').strip() for img in parent.find_all('img') if img.get('alt','').strip()]
            if not names:
                names=[a.get('title','').strip() for a in parent.find_all('a',title=True) if a.get('title','').strip()]
            if not names:
                continue
            candidate=(parent,ranges[0],names)
            break
        if candidate is None:continue
        parent,period,names=candidate
        try:
            start=date(*map(int,period.groups()[:3]));end=date(*map(int,period.groups()[3:]))
            if end<start:continue
        except ValueError:continue
        names=[n for n in names if n and n not in ('이벤트 기간','자세히 보기')]
        if not names:continue
        name=max(names,key=lambda n:('..' not in n and '…' not in n,len(n)))
        link=_find_card_event_link(parent)
        # Preserve verified card records even if the website does not expose
        # a detail URL; NEVER make up an eid from its position or title.
        key=(catalog_event_key(name),start.isoformat(),end.isoformat())
        if not key[0] or key in seen:continue
        seen.add(key)
        entries.append((name,start.isoformat(),end.isoformat(),link))
    return entries


def _link_name_keys(name):
    """Recognize campaign name in brackets, without changing stored titles."""
    raw=unicodedata.normalize('NFKC',name or '')
    candidates=[raw]
    candidates+=re.findall(r'\[([^\]]{3,100})\]',raw)
    candidates+=re.findall(r'[‘\"「『]([^’\"」』]{3,100})[’\"」』]',raw)
    raw=re.sub(r'^\s*서머\s*이벤트\s*[-:：]\s*','',raw,flags=re.I)
    candidates.append(raw)
    result=[]
    for v in candidates:
        v=re.sub(r'\s*이벤트\s*$','',v)
        key=event_key(v)
        # Fuzzy link matching disregards title punctuation; event dedup does not.
        key=re.sub(r'[^\w가-힣]','',key)
        if key and key not in result:result.append(key)
    return result


def event_name_match_score(name,official_name):
    akeys,bkeys=_link_name_keys(name),_link_name_keys(official_name)
    scores=[]
    for a in akeys:
        for b in bkeys:
            if a==b:
                scores.append(1.0)
            elif min(len(a),len(b))>=5 and min(len(a),len(b))/max(len(a),len(b))>=0.40 and (a in b or b in a):
                scores.append(0.91)
            else:
                scores.append(SequenceMatcher(None,a,b).ratio())
    return max(scores,default=0.0)


def choose_official_entry(name,start,end,post_title,catalog):
    """Unique high-confidence match; explicit period guards repeated editions."""
    posted=date_of_post_title(post_title)
    candidates=[]
    for n,s,e,link in catalog:
        score=event_name_match_score(name,n)
        if score<0.74:continue
        if start and start!=s:continue
        # A dated update notice can have a shorter campaign redemption period
        # than the umbrella event landing page. Same *start* + strong title is
        # sufficient, but an unrelated different-start event is never used.
        if end and end!=e and not (start==s and score>=0.80):continue
        try:
            sd=date.fromisoformat(s)
        except ValueError:continue
        gap=abs((posted-sd).days) if posted else 9999
        if posted and gap>45:continue
        # A shared campaign label (e.g. [Black Out]) alone must not link a
        # different sub-event. Without a close full-title match, a bracket-only
        # match needs the start to coincide with the update announcement.
        if posted and gap>2 and re.match(r'^\s*\[[^\]]+\]\s*\S',name):
            full_keys=_link_name_keys(name)[0],_link_name_keys(n)[0]
            if SequenceMatcher(None,*full_keys).ratio()<0.70:continue
        if not posted and (not start or not end) and score<0.99:continue
        candidates.append((score,gap,s,e,link))
    candidates.sort(key=lambda r:(-r[0],r[1]))
    if not candidates:return None
    best=candidates[0]
    # Reject ambiguous same-name editions rather than attach a wrong URL.
    if len(candidates)>1 and best[0]-candidates[1][0]<0.07 and abs(best[1]-candidates[1][1])<=7:
        return None
    return best[2],best[3],best[4]

def date_of_post_title(title):
    match = POST_DAY.search(title or '')
    if not match:
        return None
    try:
        return date(*map(int, match.groups()))
    except ValueError:
        return None

def choose_official_period(name,post_title,catalog):
    return choose_official_entry(name,None,None,post_title,catalog)

def backfill_dates_from_official(c, session, progress=None):
    """Fill missing endpoints and resolve real event links, preserving descriptions and tables.

    Fetch current and ended event listing pages only when unresolved records exist.
    Network or parser failures are nonfatal, and old rows are never erased.
    """
    c.execute('CREATE TABLE IF NOT EXISTS official_event_periods (name TEXT NOT NULL,start_date TEXT NOT NULL,end_date TEXT NOT NULL,PRIMARY KEY(name,start_date,end_date))')
    cols={r[1] for r in c.execute('PRAGMA table_info(official_event_periods)')}
    if 'event_url' not in cols:c.execute("ALTER TABLE official_event_periods ADD COLUMN event_url TEXT NOT NULL DEFAULT ''")
    pending=c.execute('''SELECT e.event_id,e.name,e.start_date,e.end_date,COALESCE(p.title,''),e.body_html
                         FROM events e LEFT JOIN posts p ON p.post_id=e.post_id''').fetchall()
    if not pending:return 0,0
    catalog=c.execute('SELECT name,start_date,end_date,event_url FROM official_event_periods').fetchall()
    def unresolved(rows):
        missing=[]
        for eid,name,start,end,title,fragment in rows:
            chosen=choose_official_entry(name,start,end,title,catalog)
            if (not start or not end) and chosen is None:
                missing.append(eid)
            elif not event_url_for_record(c,name,start,end,fragment,title):
                missing.append(eid)
        return missing
    # Check website each startup while unknown periods remain; use bounded pages.
    # Ended events may not be on the current-events tab.
    if unresolved(pending):
        for ing,max_pages in ((0,2),(1,10)):
            seen_pages=set()
            for page in range(1,max_pages+1):
                if not unresolved(pending):
                    break
                try:
                    soup=fetch(session,BASE+'/NewsInfo/EventList.aspx?ing='+str(ing)+'&page='+str(page))
                    found=parse_official_event_list(soup)
                except (requests.RequestException,ValueError,OSError) as exc:
                    if progress:progress('공식 이벤트 목록 확인 실패: '+str(exc)[:80])
                    break
                if not found:
                    break
                fingerprint=tuple((n,st,en) for n,st,en,_ in found)
                if fingerprint in seen_pages:
                    break
                seen_pages.add(fingerprint)
                new=0;repaired_links=0
                with c:
                    existing={(n,st,en) for n,st,en,_ in catalog}
                    for entry in found:
                        if entry[:3] not in existing:
                            c.execute('INSERT OR IGNORE INTO official_event_periods(name,start_date,end_date,event_url) VALUES (?,?,?,?)',entry)
                            catalog.append(entry);existing.add(entry[:3]);new+=1
                        elif entry[3]:
                            cursor=c.execute('UPDATE official_event_periods SET event_url=? WHERE name=? AND start_date=? AND end_date=? AND (event_url IS NULL OR event_url="")',(entry[3],*entry[:3]))
                            repaired_links+=cursor.rowcount
                            if cursor.rowcount:
                                catalog=[(n,st,en,entry[3]) if (n,st,en)==entry[:3] else (n,st,en,old_link) for n,st,en,old_link in catalog]
                # Continue even when an entire page is already cached: a missing
                # link can belong to an older page beyond that cached page.
    catalog=c.execute('SELECT name,start_date,end_date,event_url FROM official_event_periods').fetchall()
    updated=0
    with c:
        for eid,name,start,end,title,fragment in pending:
            picked=choose_official_entry(name,start,end,title,catalog)
            if picked is None:
                continue
            official_start,official_end,_link=picked
            # Preserve known date if it exists; do not overwrite conflicting facts.
            if start and start!=official_start:continue
            if end and end!=official_end:continue
            if start and end:continue
            c.execute('UPDATE events SET start_date=?,end_date=? WHERE event_id=?',
                      (start or official_start,end or official_end,eid))
            updated+=1
    return updated,len(catalog)

def event_url_for_record(c,name,start,end,body_html="",post_title=""):
    # Prefer a verified destination linked from the specific event section.
    for a in BeautifulSoup(body_html or "", "html.parser").find_all('a',href=True):
        href=a.get('href','')
        if is_official_event_url(href):return urljoin(BASE,href)
    try:
        rows=c.execute('SELECT name,start_date,end_date,event_url FROM official_event_periods WHERE event_url<>""').fetchall()
    except sqlite3.OperationalError:return ''
    candidates=[r for r in rows if is_official_event_url(r[3])]
    chosen=choose_official_entry(name,start,end,post_title,candidates)
    return chosen[2] if chosen else ''

def is_closing_notice(name, body):
    first=body[:min(len(body),240)]
    return bool(re.search(r'이벤트(?:가|의\s*기간이)?\s*종료됩니다',first))

def restyle_html(fragment):
    """Reader-mode styling, preserving merged cells, rows and quantities."""
    soup=BeautifulSoup(fragment or '', 'html.parser')
    for img in list(soup.find_all('img')):img.decompose()
    for tag in soup.find_all(True):
        for key in ('style','bgcolor','color','face','size','border','cellpadding','cellspacing','class'):
            tag.attrs.pop(key,None)
        if tag.name=='table':
            tag['width']='100%';tag['cellspacing']='0';tag['cellpadding']='7';tag['border']='0'
            tag['style']='border-collapse:collapse;margin-top:15px;margin-bottom:18px;background-color:#fffcf4;'
        elif tag.name in ('td','th'):
            parent=tag.find_parent('tr')
            row_i=0
            if parent:
                group=parent.parent
                rows=group.find_all('tr',recursive=False)
                if parent in rows:row_i=rows.index(parent)
            first=tag.name=='th' or row_i==0
            bg='#e4decc' if first else ('#fffcf4' if row_i%2 else '#f3eedf')
            tag['style']=f'border-bottom:1px solid #bcb09a;border-right:1px solid #ded5c4;padding:9px;background-color:{bg};color:#312d29;vertical-align:middle;'
            if first:tag['style']+='font-weight:bold;'
        elif tag.name in ('h1','h2','h3','h4'):
            tag['style']='color:#302b24;font-weight:bold;margin-top:16px;margin-bottom:9px;'
        elif tag.name=='p':
            tag['style']='margin-top:8px;margin-bottom:11px;'
    return str(soup)

def migrate_remove_images(c):
    """Drop legacy event images without discarding text, tables or event rows."""
    row=c.execute("SELECT value FROM meta WHERE key='images_removed_v8'").fetchone()
    if row:return
    with c:
        c.execute('DROP TABLE IF EXISTS event_banners')
        c.execute("UPDATE events SET banner_url='' WHERE COALESCE(banner_url,'')<>''")
        for event_id,fragment in c.execute('SELECT event_id,body_html FROM events').fetchall():
            if fragment and '<img' in fragment.lower():
                clean=BeautifulSoup(fragment,'html.parser')
                for image in clean.find_all('img'):image.decompose()
                c.execute('UPDATE events SET body_html=? WHERE event_id=?',(str(clean),event_id))
        c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('images_removed_v8','1')")
    # Reclaim space formerly occupied by image BLOBs; only once on migration.
    try:
        c.execute('VACUUM')
        c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    except sqlite3.OperationalError:
        pass

def clean_existing_events(c):
    """Keep verified duplicate suppressions stable when event dates are backfilled.

    Earlier versions removed every hidden_events record on every scan. Once a
    previously undated event received dates from the official catalogue, the
    new grouping could miss it and the old duplicate reappeared. Persist
    duplicate flags across scans. Do not alter user_hidden_events, which is an
    independent user-controlled choice.
    """
    c.execute('CREATE TABLE IF NOT EXISTS hidden_events (event_id TEXT PRIMARY KEY,reason TEXT NOT NULL)')
    entries=c.execute('SELECT event_id,name,start_date,end_date,body_text FROM events').fetchall()
    ids={row[0] for row in entries}
    with c:
        # Entries deleted when a (추가) notice is reparsed can leave stale flags.
        # Prune only those orphaned flags, not flags for existing event records.
        c.execute('DELETE FROM hidden_events WHERE event_id NOT IN (SELECT event_id FROM events)')
        previously_hidden={eid for (eid,) in c.execute("SELECT event_id FROM hidden_events WHERE reason IN ('duplicate','closing_notice')")}
        groups={}
        for eid,name,start,end,body in entries:
            if is_closing_notice(name,body or ''):
                c.execute('INSERT OR REPLACE INTO hidden_events VALUES (?,?)',(eid,'closing_notice'))
                continue
            groups.setdefault(event_key(name),[]).append((eid,start,end,len(body or '')))
        for items in groups.values():
            # The same named event may be held in multiple editions. Compare
            # only fully known, equal periods, or multiple undated records.
            # Previously suppressed events remain suppressed even if their
            # date changes; newly dated separate editions stay visible.
            buckets={}
            for item in items:
                eid,start,end,_=item
                bucket=(start,end) if start and end else ('unknown',end)
                buckets.setdefault(bucket,[]).append(item)
            for candidates in buckets.values():
                if len(candidates)<2:continue
                # Prefer a survivor that was already visible; ensure a newly
                # re-grouped legacy duplicate cannot replace its original.
                winner=max(candidates,key=lambda x:(x[0] not in previously_hidden,bool(x[1]),x[3],x[0]))[0]
                for eid,_,_,_ in candidates:
                    if eid!=winner:
                        c.execute('INSERT OR REPLACE INTO hidden_events VALUES (?,?)',(eid,'duplicate'))

class Worker(QThread):
 progress=Signal(str);finished_ok=Signal(int,int);failed=Signal(str)
 def run(self):
  c=None
  try:
   c=db();migrate_remove_images(c);repair_saved_dates(c);s=requests.Session();s.headers.update(HEADERS)
   posts=get_posts(fetch(s,LIST));self.progress.emit(f'목록 {len(posts)}개 확인')
   count=0;evcount=0
   for pid,title,url in posts:
    if self.isInterruptionRequested():break
    row=c.execute('SELECT added_seen,parser_version FROM posts WHERE post_id=?',(pid,)).fetchone()
    added=bool(ADDED.search(title))
    if row and row[1]>=PARSER_VERSION and (row[0] or not added):continue
    self.progress.emit(f'본문 확인: {title[:42]}')
    soup=fetch(s,url);events=split_events(soup,title,pid,url)
    for e in events:
     e['body_html']=restyle_html(e['body_html'])
    with c:
     # On an (추가) pass, replace entries for the post only after successful parsing.
     # If parsing unexpectedly returns nothing, preserve previously saved events.
     if row and events:c.execute('DELETE FROM events WHERE post_id=?',(pid,))
     for e in events:
      c.execute('INSERT OR REPLACE INTO events(event_id,post_id,name,start_date,end_date,body_html,body_text,source_url,banner_url) VALUES(?,?,?,?,?,?,?,?,?)',(e['event_id'],pid,e['name'],e['start'],e['end'],e['body_html'],e['body'],url,''))
     c.execute('INSERT INTO posts(post_id,title,added_seen,checked_at,parser_version) VALUES(?,?,?,?,8) ON CONFLICT(post_id) DO UPDATE SET title=excluded.title,added_seen=excluded.added_seen,checked_at=excluded.checked_at,parser_version=8',(pid,title,int(added),datetime.now().isoformat(timespec='seconds')))
    count+=1;evcount+=len(events)
   corrected,catalog_count=backfill_dates_from_official(c,s,self.progress.emit)
   clean_existing_events(c)
   self.progress.emit(f'공식 이벤트 기간 보완 {corrected}개 · 목록 기록 {catalog_count}개')
   self.finished_ok.emit(count,evcount)
  except Exception as e:self.failed.emit(f'{type(e).__name__}: {e}')
  finally:
   if c:c.close()

def status_icon(state):
    """Small D-style symbol: icon only, with no status words in the cell."""
    pix=QPixmap(23,23);pix.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    tone={'active':'#547d54','ended':'#99665a','today':'#a78846','future':'#7e7c9f','unknown':'#999087'}[state]
    painter.setPen(QPen(QColor(tone),1.6))
    painter.setBrush(QBrush(QColor('#fffaf0')))
    painter.drawRoundedRect(3,3,17,17,5,5)
    painter.setPen(QPen(QColor(tone),2.2))
    if state in ('active','future'):
        painter.setBrush(QBrush(QColor(tone)))
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF
        painter.drawPolygon(QPolygonF([QPointF(9,7),QPointF(9,16),QPointF(16,11.5)]))
    elif state in ('ended','today'):
        painter.drawLine(8,8,15,15);painter.drawLine(15,8,8,15)
    else:
        painter.drawText(7,17,'?')
    painter.end()
    return QIcon(pix)

class EventRowDelegate(QStyledItemDelegate):
 """Paint table item selection without a per-cell focus rectangle."""
 def paint(self, painter, option, index):
  opt=QStyleOptionViewItem(option)
  opt.state &= ~QStyle.StateFlag.State_HasFocus
  super().paint(painter,opt,index)

class HideCheckBox(QCheckBox):
 """Actual clickable checkbox widget with a theme-independent indicator.

 Unlike a QTableWidgetItem check state, QWidget mouse handling is independent
 of QTableWidget's NoEditTriggers and item delegate/editorEvent dispatch.
 """
 def __init__(self, parent=None):
  super().__init__(parent)
  self.setFixedSize(26,26)
  self.setCursor(Qt.CursorShape.PointingHandCursor)
  self.setToolTip('이 이벤트 숨기기 / 다시 클릭하면 해제')
  self.setStyleSheet('background:transparent;')

 def paintEvent(self, event):
  painter=QPainter(self)
  painter.setRenderHint(QPainter.RenderHint.Antialiasing)
  painter.setPen(QPen(QColor('#604a2c'),1.5))
  painter.setBrush(QBrush(QColor('#6d5839') if self.isChecked() else QColor('#fffaf0')))
  painter.drawRoundedRect(5,5,16,16,3,3)
  if self.isChecked():
   painter.setPen(QPen(QColor('#ffffff'),2.2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
   painter.drawLine(9,13,12,16)
   painter.drawLine(12,16,18,9)
  painter.end()


def set_manual_hidden(conn, event_id, checked):
 """Save the checkbox state by stable event ID, never by visible row index."""
 with conn:
  if checked:
   conn.execute('INSERT OR IGNORE INTO user_hidden_events(event_id) VALUES(?)',(event_id,))
  else:
   conn.execute('DELETE FROM user_hidden_events WHERE event_id=?',(event_id,))

def valid_complete_period(start, end):
 """A visible event must have two valid ISO dates in chronological order."""
 if not isinstance(start,str) or not isinstance(end,str):return False
 try:
  a=date.fromisoformat(start)
  b=date.fromisoformat(end)
 except (ValueError,TypeError):return False
 return a<=b and a.isoformat()==start and b.isoformat()==end

def filter_visible_events(rows, hidden, hide_ended, today, deferred_hidden=()):
 """Always exclude unknown/incomplete dates; optionally hide ended/checked rows."""
 # The global checkbox affects ended/manual hiding only. It must never reveal
 # incomplete dates, even on restart or when users toggle the filter off.
 complete=[r for r in rows if valid_complete_period(r[2],r[3])]
 if not hide_ended:
  return complete
 return [r for r in complete if not (r[3]<today or (r[0] in hidden and r[0] not in deferred_hidden))]

HIGHLIGHT_COLORS = {'yellow':'#f7e48d', 'green':'#cce9ae', 'pink':'#f1bfd0'}

def save_event_highlight(conn, event_id, start, end, selected_text, color):
 """Persist user annotations separately from the scraped HTML."""
 if not event_id or not selected_text or start >= end or color not in HIGHLIGHT_COLORS.values():
  raise ValueError('Invalid highlight')
 with conn:
  conn.execute('INSERT INTO event_highlights(event_id,start_pos,end_pos,selected_text,color) VALUES(?,?,?,?,?)',
               (event_id,start,end,selected_text,color))

def remove_event_highlights_in_range(conn, event_id, start, end):
 """Erase annotations that intersect the selected text, without altering the original event."""
 with conn:
  return conn.execute('DELETE FROM event_highlights WHERE event_id=? AND start_pos<? AND end_pos>?',
                      (event_id,end,start)).rowcount

def clear_event_highlights(conn, event_id):
 """Delete only this event's saved annotations; preserve all other events."""
 if not event_id:
  return 0
 with conn:
  return conn.execute('DELETE FROM event_highlights WHERE event_id=?',
                      (event_id,)).rowcount

def find_annotation_range(document, old_start, old_end, selected_text):
 """Use the saved Qt document offsets, falling back to a nearby exact text match."""
 if not selected_text:return None
 cursor=QTextCursor(document)
 upper=max(0,document.characterCount()-1)
 if 0<=old_start<old_end<=upper:
  cursor.setPosition(old_start)
  cursor.setPosition(old_end,QTextCursor.MoveMode.KeepAnchor)
  if cursor.selectedText()==selected_text:return old_start,old_end
 text=document.toPlainText().replace('\n','\u2029')
 # Qt QTextDocument positions use UTF-16 code units, unlike Python indices.
 found=[];position=text.find(selected_text)
 while position>=0:
  qt_start=len(text[:position].encode('utf-16-le'))//2
  found.append((abs(qt_start-old_start),qt_start))
  position=text.find(selected_text,position+1)
 if not found:return None
 qt_start=min(found)[1]
 qt_end=qt_start+len(selected_text.encode('utf-16-le'))//2
 if qt_end>upper:return None
 return qt_start,qt_end

class Main(QMainWindow):
 def __init__(self):
  super().__init__();self.setWindowTitle('GRANADO ESPADA · EVENT CHRONICLE');self.resize(1120,720)
  ico=ROOT/'ge.ico'
  if not ico.exists() and getattr(sys,'frozen',False):ico=Path(getattr(sys,'_MEIPASS',ROOT))/'ge.ico'
  if ico.exists():self.setWindowIcon(QIcon(str(ico)))
  self.worker=None;self.rows=[];self.updating_table=False;self.deferred_hidden=set();self.current_event_id=None
  root=QWidget();self.setCentralWidget(root);lay=QVBoxLayout(root);lay.setContentsMargins(16,16,16,12);lay.setSpacing(12)
  top=QHBoxLayout();title=QLabel('GRANADO ESPADA · EVENT CHRONICLE');title.setStyleSheet('font-size:23px;font-weight:700');top.addWidget(title);top.addStretch()
  self.hide=QCheckBox('종료된 이벤트 숨기기');self.hide.setChecked(True);self.hide.toggled.connect(self.on_hide_toggled);top.addWidget(self.hide)
  lay.addLayout(top)
  split=QSplitter(Qt.Orientation.Horizontal);lay.addWidget(split,1)
  self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['','이벤트','기간',''])
  self.table.setItemDelegate(EventRowDelegate(self.table))
  self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
  self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
  self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
  self.table.setShowGrid(False)
  self.table.setAlternatingRowColors(True)
  self.table.verticalHeader().setVisible(False)
  self.table.verticalHeader().setDefaultSectionSize(35)
  self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Fixed)
  self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
  self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents)
  self.table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Fixed)
  self.table.setColumnWidth(0,34);self.table.setColumnWidth(3,46)
  self.table.horizontalHeader().setMinimumSectionSize(28)
  self.table.itemSelectionChanged.connect(self.show_detail)
  
  split.addWidget(self.table)
  right=QWidget()
  right_layout=QVBoxLayout(right)
  right_layout.setContentsMargins(0,0,0,0)
  right_layout.setSpacing(6)
  tools=QHBoxLayout()
  tools.setContentsMargins(4,0,4,0)
  heading=QLabel('형광펜')
  heading.setStyleSheet('font-weight:700;color:#63452b;')
  tools.addWidget(heading)
  for name,color in [('노랑','#f7e48d'),('연두','#cce9ae'),('분홍','#f1bfd0')]:
   btn=QPushButton('')
   btn.setFixedSize(31,29)
   btn.setToolTip(name+' 형광펜 — 본문에서 텍스트를 선택한 뒤 누르세요')
   btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
   btn.setStyleSheet(f'QPushButton{{background:{color};border:1px solid #aa926f;border-radius:5px;}} QPushButton:hover{{border:2px solid #79562c;}}')
   btn.clicked.connect(lambda _=False, c=color:self.apply_highlight(c))
   tools.addWidget(btn)
  separator=QLabel('│')
  tools.addWidget(separator)
  eraser=QPushButton('지우개')
  eraser.setToolTip('현재 이벤트 설명의 모든 형광펜을 제거합니다')
  eraser.setFocusPolicy(Qt.FocusPolicy.NoFocus)
  eraser.setStyleSheet('QPushButton{background:#f4e9d6;border:1px solid #baa382;border-radius:5px;padding:5px 9px;color:#513c2c;} QPushButton:hover{background:#ebddc4;}')
  eraser.clicked.connect(self.erase_highlight)
  tools.addWidget(eraser)
  tools.addStretch()
  right_layout.addLayout(tools)
  self.detail=QTextBrowser();self.detail.setOpenExternalLinks(True)
  self.detail.setStyleSheet('QTextBrowser{background:#f8f3e7;color:#302820;border:1px solid #bdaa87;border-radius:7px;padding:16px;}')
  right_layout.addWidget(self.detail,1)
  split.addWidget(right);split.setSizes([450,670])
  self.status=QLabel('저장된 이벤트 불러오는 중');lay.addWidget(self.status)
  self.setStyleSheet("""
   QMainWindow,QWidget{background:#e9e0ce;color:#3b3027;font-size:13px}
   QLabel,QCheckBox{background:transparent;color:#443426}
   QTableWidget{background:#fbf7ec;alternate-background-color:#f2e9d8;selection-background-color:#e9d9b8;selection-color:#493522;border:1px solid #bdad91;border-radius:7px;gridline-color:transparent}
   QTableWidget::item:selected{background:#e9d9b8;color:#493522;border:none;outline:none}
   QTableWidget::item:focus{border:none;outline:none}
   QHeaderView::section{background:#d8c9aa;color:#3d3026;padding:9px;border:0;border-bottom:1px solid #ad9a79;font-weight:bold}
   QScrollBar:vertical{background:#e8decd;width:11px;margin:3px 2px;border:0;border-radius:5px}
   QScrollBar::handle:vertical{background:#ab9573;min-height:32px;border-radius:4px}
   QScrollBar::handle:vertical:hover{background:#846b4c}
   QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;border:0}
   QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:transparent}
   QScrollBar:horizontal{background:#e8decd;height:11px;margin:2px 3px;border:0;border-radius:5px}
   QScrollBar::handle:horizontal{background:#ab9573;min-width:32px;border-radius:4px}
   QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0;border:0}
   QScrollBar::add-page:horizontal,QScrollBar::sub-page:horizontal{background:transparent}
  """)
  c=db();migrate_remove_images(c);repair_saved_dates(c);clean_existing_events(c);c.close()
  self.populate();self.start_scan()
 def on_hide_toggled(self,*args):
  # Applying the global filter commits all checkmarks to visibility.
  self.deferred_hidden.clear()
  self.populate()
 def populate(self,*args):
  selected=self.visible[self.table.currentRow()][0] if getattr(self,'visible',None) and 0<=self.table.currentRow()<len(self.visible) else None
  c=db()
  self.rows=c.execute("SELECT event_id,name,start_date,end_date,body_text,source_url,body_html FROM events WHERE event_id NOT IN (SELECT event_id FROM hidden_events) ORDER BY COALESCE(end_date,'9999') DESC,name").fetchall()
  self.post_titles={eid:(title or '') for eid,title in c.execute("SELECT e.event_id,p.title FROM events e LEFT JOIN posts p ON p.post_id=e.post_id").fetchall()}
  hidden={r[0] for r in c.execute('SELECT event_id FROM user_hidden_events')};c.close()
  today=date.today().isoformat()
  # Incomplete event periods never appear; the global filter additionally hides ended/checked events.
  self.visible=filter_visible_events(self.rows,hidden,self.hide.isChecked(),today,self.deferred_hidden)
  self.updating_table=True
  self.table.setRowCount(len(self.visible))
  target=-1
  for i,r in enumerate(self.visible):
   if r[0]==selected:target=i
   start,end=r[2],r[3]
   state='ended' if end and end<today else 'future' if start and start>today else 'today' if end==today else 'active' if start and end and start<=today<=end else 'unknown'
   texts=[r[1],f'{start or "?"} ~ {end or "?"}']
   for j,value in enumerate(texts):
    item=QTableWidgetItem(value);item.setToolTip(value);self.table.setItem(i,j+1,item)
   icon_item=QTableWidgetItem();icon_item.setIcon(status_icon(state));icon_item.setToolTip({'ended':'종료','future':'진행 예정','today':'오늘 종료','active':'진행 중','unknown':'기간 미확인'}[state])
   icon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter);self.table.setItem(i,0,icon_item)
   # Set a neutral item beneath the child widget so row-selection shading
   # still spans the entire row including the checkbox column.
   self.table.setItem(i,3,QTableWidgetItem())
   holder=QWidget(self.table)
   holder.setStyleSheet('background:transparent;')
   place=QHBoxLayout(holder);place.setContentsMargins(0,0,0,0)
   place.setSpacing(0);place.setAlignment(Qt.AlignmentFlag.AlignCenter)
   check=HideCheckBox(holder)
   check.setChecked(r[0] in hidden)
   check.toggled.connect(lambda checked,eid=r[0]: self.on_check_toggled(eid,checked))
   place.addWidget(check)
   self.table.setCellWidget(i,3,holder)
  self.updating_table=False
  if self.visible:self.table.selectRow(target if target>=0 else 0)
  else:
   self.current_event_id=None
   self.detail.setHtml('<h3>표시할 이벤트가 없습니다.</h3>')
 def on_check_toggled(self, event_id, checked):
  # A real checkbox widget emits toggled on each click. Its captured event_id
  # remains correct even if the table is sorted or the user changes filters.
  if self.updating_table:return
  c=db()
  try:set_manual_hidden(c,event_id,checked)
  finally:c.close()
  self.deferred_hidden.discard(event_id)
  # When the global filter is active, checking a box hides the row immediately.
  # Turning it off reveals all hidden rows so the same box can be unchecked.
  if self.hide.isChecked():
   QTimer.singleShot(0,self.populate)

 def show_detail(self):
  row=self.table.currentRow()
  if row<0 or row>=len(getattr(self,'visible',[])):return
  r=self.visible[row]
  self.current_event_id=r[0]
  body=restyle_html(r[6]) if r[6] else html.escape(r[4]).replace('\n','<br>')
  c=db();event_link=event_url_for_record(c,r[1],r[2],r[3],r[6],self.post_titles.get(r[0],''));c.close()
  secondary=(' &nbsp; │ &nbsp; <a href="'+html.escape(event_link,quote=True)+'">이벤트 페이지 열기 ↗</a>') if event_link else ''
  article=f"""<html><body style="background-color:#f8f3e7;color:#28241e;font-family:Batang,Georgia,serif;font-size:14px;">
  <div style="text-align:center;color:#625946;font-family:Georgia,Batang,serif;font-size:11px;">GRANADO ESPADA &nbsp; · &nbsp; EVENT CHRONICLE</div>
  <hr style="color:#534b3e;" />
  <div style="text-align:center;font-family:Georgia,Batang,serif;font-size:23px;font-weight:bold;margin:15px 8px;">{html.escape(r[1])}</div>
  <div style="text-align:center;color:#685d4d;font-size:12px;margin-bottom:14px;">{html.escape(r[2] or '시작일 미확인')} &nbsp; — &nbsp; {html.escape(r[3] or '종료일 미확인')}</div>
  <hr style="color:#b9ad97;" />
  <div style="font-family:Batang,Georgia,serif;font-size:14px;line-height:1.9;color:#302b24;">{body}</div>
  <hr style="color:#b9ad97;" />
  <p style="text-align:center;font-size:11px;color:#655b4b;"><a href="{html.escape(r[5],quote=True)}">원본 업데이트 공지 보기 ↗</a>{secondary}</p>
  </body></html>"""
  self.detail.setHtml(article)
  self.restore_highlights()

 def restore_highlights(self):
  if not self.current_event_id:return
  c=db()
  annotations=c.execute('SELECT highlight_id,start_pos,end_pos,selected_text,color FROM event_highlights WHERE event_id=? ORDER BY highlight_id',
                        (self.current_event_id,)).fetchall()
  c.close()
  doc=self.detail.document()
  for _,start,end,text,color in annotations:
   if color not in HIGHLIGHT_COLORS.values():continue
   location=find_annotation_range(doc,start,end,text)
   if location is None:continue
   cursor=QTextCursor(doc)
   cursor.setPosition(location[0]);cursor.setPosition(location[1],QTextCursor.MoveMode.KeepAnchor)
   fmt=QTextCharFormat();fmt.setBackground(QColor(color))
   cursor.mergeCharFormat(fmt)
  self.detail.moveCursor(QTextCursor.MoveOperation.Start)

 def apply_highlight(self,color):
  if not self.current_event_id:return
  cursor=self.detail.textCursor()
  if not cursor.hasSelection():
   self.status.setText('형광펜: 먼저 이벤트 설명에서 글자를 선택해 주세요.')
   return
  start,end=cursor.selectionStart(),cursor.selectionEnd()
  selected=cursor.selectedText()
  if not selected.strip():return
  c=db()
  try:save_event_highlight(c,self.current_event_id,start,end,selected,color)
  finally:c.close()
  fmt=QTextCharFormat();fmt.setBackground(QColor(color))
  cursor.mergeCharFormat(fmt)
  self.detail.setTextCursor(cursor)
  self.status.setText('형광펜 표시를 저장했습니다.')

 def erase_highlight(self):
  """Clear every highlight on the displayed event, without text selection."""
  event_id=self.current_event_id
  if not event_id:return
  c=db()
  try:
   removed=clear_event_highlights(c,event_id)
  finally:c.close()
  # Reload the unmodified source HTML, which also clears applied char formats.
  self.show_detail()
  self.status.setText(f'현재 이벤트의 형광펜 {removed}개를 모두 제거했습니다.' if removed else '현재 이벤트에는 저장된 형광펜이 없습니다.')

 def start_scan(self):
  if self.worker and self.worker.isRunning():return
  self.worker=Worker();self.worker.progress.connect(self.status.setText);self.worker.finished_ok.connect(self.done);self.worker.failed.connect(self.error);self.worker.start()
 def done(self,n,e):
  self.status.setText(f'수집 완료 · 새로 확인한 게시글 {n}개 · 추출 이벤트 {e}개');self.populate()
 def error(self,msg):
  self.status.setText('수집 오류: '+msg);self.populate()
 def closeEvent(self,event):
  if self.worker and self.worker.isRunning():
   self.worker.requestInterruption();self.worker.wait(28000)
   if self.worker.isRunning():event.ignore();self.status.setText('네트워크 요청 종료 대기 중입니다. 잠시 후 다시 닫아주세요.');return
  event.accept()

if __name__=='__main__':
 app=QApplication(sys.argv);app.setApplicationName('GE 이벤트');w=Main();w.show();sys.exit(app.exec())
