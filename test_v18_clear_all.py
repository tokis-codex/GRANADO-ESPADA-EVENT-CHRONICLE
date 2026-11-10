"""Regression tests for v18 erase-all behavior and toolbar labels."""
import ast
import sqlite3
from pathlib import Path

path=Path(__file__).with_name('main.py')
s=path.read_text(encoding='utf-8')
assert "heading=QLabel('형광펜')" in s
assert "eraser=QPushButton('지우개')" in s
assert "eraser.setToolTip('현재 이벤트 설명의 모든 형광펜을 제거합니다')" in s
assert "removed=clear_event_highlights(c,event_id)" in s
start=s.index(' def erase_highlight(self):')
end=s.index(' def start_scan(self):',start)
assert 'hasSelection' not in s[start:end]
assert 'self.show_detail()' in s[start:end]
module=ast.parse(s)
func=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='clear_event_highlights')
ns={}
exec(compile(ast.fix_missing_locations(ast.Module(body=[func],type_ignores=[])),'<helper>','exec'),ns)
c=sqlite3.connect(':memory:')
c.execute('CREATE TABLE event_highlights (event_id TEXT, selected_text TEXT)')
c.executemany('INSERT INTO event_highlights VALUES (?,?)', [('a','one'),('a','two'),('b','three')])
assert ns['clear_event_highlights'](c,'a')==2
assert c.execute('SELECT event_id,selected_text FROM event_highlights').fetchall()==[('b','three')]
assert ns['clear_event_highlights'](c,'a')==0
assert ns['clear_event_highlights'](c,None)==0
print('PASS v18 clear-all scope, no-selection click, plain labels')
