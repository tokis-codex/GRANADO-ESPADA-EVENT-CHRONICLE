"""Real SQLite state/filter regression, works without Qt or internet."""
import ast,sqlite3
from datetime import date
from pathlib import Path
source=(Path(__file__).parent/'main.py').read_text(encoding='utf-8')
tree=ast.parse(source)
names={'filter_visible_events','set_manual_hidden','valid_complete_period'}
nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
assert len(nodes)==3
ns={"date":date};exec(compile(ast.Module(body=nodes,type_ignores=[]),'<test>','exec'),ns)
filter_rows=ns['filter_visible_events'];save=ns['set_manual_hidden']
c=sqlite3.connect(':memory:');c.execute('CREATE TABLE user_hidden_events(event_id TEXT PRIMARY KEY)')
rows=[('live','Example','2026-11-01','2099-01-01'),('old','Old','2020-01-01','2020-01-31')]
def hidden():return {r[0] for r in c.execute('SELECT event_id FROM user_hidden_events')}
def visible(global_on,temporary=()):return [r[0] for r in filter_rows(rows,hidden(),global_on,'2026-11-06',temporary)]
assert visible(True)==['live']
save(c,'live',True)
assert hidden()=={'live'}
assert visible(True,{'live'})==['live']  # legacy deferred mode remains optional
save(c,'live',False)
assert hidden()==set()
assert visible(True)==['live']         # unchecked item restored
save(c,'live',True)
assert visible(True)==[]              # next filter/restart hides it
assert visible(False)==['live','old'] # global filter OFF reveals ALL
save(c,'live',False)
assert visible(True)==['live']         # recheck global filter: restored live row
# durable SQLite setting across connections
import tempfile
with tempfile.TemporaryDirectory() as td:
 f=Path(td)/'events.db';a=sqlite3.connect(f)
 a.execute('CREATE TABLE user_hidden_events(event_id TEXT PRIMARY KEY)')
 save(a,'live',True);a.close()
 b=sqlite3.connect(f)
 assert b.execute('SELECT event_id FROM user_hidden_events').fetchall()==[('live',)]
 save(b,'live',False)
 assert b.execute('SELECT event_id FROM user_hidden_events').fetchall()==[]
 b.close()
assert 'self.table.itemChanged.connect' not in source
assert 'check.toggled.connect(' in source
assert 'self.table.setCellWidget(i,3,holder)' in source
assert '숨긴 이벤트 보기' not in source
print('PASS: check/uncheck, SQLite persistence, global filter reveal/re-hide, real checkbox wiring')
