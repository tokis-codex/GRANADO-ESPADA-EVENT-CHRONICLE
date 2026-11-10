"""Dependency-free unit checks for v17's SQLite annotation helpers."""
import ast
import sqlite3
import tempfile
from pathlib import Path

source=Path(__file__).with_name('main.py').read_text(encoding='utf-8')
tree=ast.parse(source)
functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in ('save_event_highlight','remove_event_highlights_in_range')]
assert len(functions)==2
module=ast.Module(body=functions,type_ignores=[])
namespace={'HIGHLIGHT_COLORS':{'yellow':'#f7e48d','green':'#cce9ae','pink':'#f1bfd0'}}
exec(compile(ast.fix_missing_locations(module),'<annotation-functions>','exec'),namespace)
with tempfile.TemporaryDirectory() as d:
 conn=sqlite3.connect(Path(d)/'test.db')
 conn.execute('CREATE TABLE event_highlights (highlight_id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL,start_pos INTEGER NOT NULL,end_pos INTEGER NOT NULL,selected_text TEXT NOT NULL,color TEXT NOT NULL)')
 save=namespace['save_event_highlight'];erase=namespace['remove_event_highlights_in_range']
 save(conn,'event-1',20,27,'테스트 강조','#f7e48d')
 save(conn,'event-1',32,39,'별도 강조','#cce9ae')
 save(conn,'event-2',20,27,'다른 행사','#f1bfd0')
 conn.close()
 conn=sqlite3.connect(Path(d)/'test.db')
 assert conn.execute('SELECT COUNT(*) FROM event_highlights').fetchone()[0]==3
 assert erase(conn,'event-1',23,24)==1
 assert conn.execute('SELECT selected_text FROM event_highlights WHERE event_id="event-1"').fetchall()==[('별도 강조',)]
 assert conn.execute('SELECT COUNT(*) FROM event_highlights WHERE event_id="event-2"').fetchone()[0]==1
 try:save(conn,'event-1',3,3,'','#f1bfd0')
 except ValueError:pass
 else:raise AssertionError('Missing validation')
 conn.close()
print('PASS: highlight persistence, scoped erase, validation')
