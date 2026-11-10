"""Regression: a previously hidden duplicate must not reappear after date backfill."""
import ast, sqlite3, re, unicodedata
from pathlib import Path
source=(Path(__file__).parent/'main.py').read_text(encoding='utf-8')
tree=ast.parse(source)
names={'clean_existing_events','event_key','is_closing_notice'}
items=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
assert {node.name for node in items}==names
ns={'sqlite3':sqlite3,'re':re,'unicodedata':unicodedata}
exec(compile(ast.Module(body=items,type_ignores=[]),'<test_functions>','exec'),ns)
c=sqlite3.connect(':memory:')
c.execute('CREATE TABLE events(event_id TEXT PRIMARY KEY,name TEXT,start_date TEXT,end_date TEXT,body_text TEXT)')
c.execute('CREATE TABLE user_hidden_events(event_id TEXT PRIMARY KEY)')
c.executemany('INSERT INTO events VALUES(?,?,?,?,?)',[
 ('original','기간떼 달리기 대회',None,None,'시작 이벤트 안내'),
 ('duplicate','기간떼 달리기 대회',None,None,'중복 안내'),
 ('different_edition','기간떼 달리기 대회','2025-08-06','2025-08-27','다른 해 진행'),
 ('closing','기간떼 달리기 대회가 종료됩니다',None,'2026-08-27','이벤트가 종료됩니다')])
c.execute('INSERT INTO user_hidden_events VALUES(?)',('original',))
clean=ns['clean_existing_events']
clean(c)
def hidden():return dict(c.execute('SELECT event_id,reason FROM hidden_events'))
assert hidden()=={'duplicate':'duplicate','closing':'closing_notice'},hidden()
# The official site backfills a period only for the previously hidden copy.
c.execute('UPDATE events SET start_date=?,end_date=? WHERE event_id=?',('2026-08-06','2026-08-27','duplicate'))
clean(c)
assert hidden()=={'duplicate':'duplicate','closing':'closing_notice'},hidden()
assert c.execute('SELECT * FROM user_hidden_events').fetchall()==[('original',)]
# New restart/scan should be idempotent.
clean(c)
assert hidden()=={'duplicate':'duplicate','closing':'closing_notice'},hidden()
# Removed entries should not leave suppression tombstones.
c.execute('DELETE FROM events WHERE event_id=?',('duplicate',))
clean(c)
assert hidden()=={'closing':'closing_notice'},hidden()
# Ensure reappearing legitimate editions does not get hidden by name only.
assert 'different_edition' not in hidden()
print('PASS: duplicate suppression persisted across date changes, restart, and deletion; separate editions and manual flags preserved')
