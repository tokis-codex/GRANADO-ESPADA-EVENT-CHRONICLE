"""v15: show only complete valid event periods, regardless of global filter."""
import ast
from datetime import date
from pathlib import Path
source=(Path(__file__).parent/'main.py').read_text(encoding='utf-8')
tree=ast.parse(source)
names={'valid_complete_period','filter_visible_events'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
assert {n.name for n in nodes}==names
ns={'date':date}
exec(compile(ast.Module(body=nodes,type_ignores=[]),'<test>','exec'),ns)
valid=ns['valid_complete_period'];filter_rows=ns['filter_visible_events']
rows=[
 ('active','Active','2026-11-01','2026-11-30'),
 ('ended','Ended','2026-08-01','2026-08-27'),
 ('future','Future','2026-12-01','2026-12-30'),
 ('no_start','No start',None,'2026-11-30'),
 ('no_end','No end','2026-11-01',None),
 ('no_both','Unknown',None,None),
 ('bad_date','Invalid','2026-02-30','2026-03-01'),
 ('reverse','Reverse','2026-12-02','2026-12-01'),
 ('bad_format','Bad format','2026/11/01','2026-11-30'),
]
assert valid('2026-11-01','2026-11-30')
assert not valid('2026-11-30','2026-11-01')
assert [r[0] for r in filter_rows(rows,set(),True,'2026-11-06')]==['active','future']
assert [r[0] for r in filter_rows(rows,set(),False,'2026-11-06')]==['active','ended','future']
assert [r[0] for r in filter_rows(rows,{'active'},True,'2026-11-06')]==['future']
assert [r[0] for r in filter_rows(rows,{'active'},False,'2026-11-06')]==['active','ended','future']
# No database mutations in filtering; backfilled dates become displayable naturally.
backfilled=[('no_start','Backfilled','2026-08-06','2026-08-27')]
assert [r[0] for r in filter_rows(backfilled,set(),False,'2026-11-06')]==['no_start']
assert filter_rows(backfilled,set(),True,'2026-11-06')==[]
print('PASS: missing, malformed, and reversed periods remain excluded regardless of hide toggle')
