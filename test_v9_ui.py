"""Static layout check for v12 real-widget checkbox implementation."""
from pathlib import Path
s=(Path(__file__).parent/'main.py').read_text(encoding='utf-8')
assert "self.table.setHorizontalHeaderLabels(['','이벤트','기간',''])" in s
assert 'check=HideCheckBox(holder)' in s
assert 'self.table.setCellWidget(i,3,holder)' in s
assert 'self.table.setItem(i,0,icon_item)' in s
assert 'self.table.itemChanged.connect' not in s
assert 'opt.state &= ~QStyle.StateFlag.State_HasFocus' in s
print('PASS: status icon left, actual clickable checkbox right, no focus outline')
