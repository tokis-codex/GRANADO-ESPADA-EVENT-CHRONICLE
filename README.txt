GE 이벤트 v8 — Windows source package (not a prebuilt EXE)

[What changed]
- Event details no longer fetch, display or cache any banner or body image.
- On first launch, legacy event_banners data and banner references are removed;
  existing event descriptions, HTML tables, dates and other records are kept.
  Back up events.db before first launch.
- Event headings preserve the final word '이벤트' and quotation marks.
- Each list row has an icon-only status indicator and a per-event hide checkbox
  on the right. Checkboxes persist in events.db. When '종료된 이벤트 숨기기'
  is enabled, ended events and manually checked events are hidden together;
  switch it off to see/uncheck the latter.
- Selected rows use a single continuous champagne-gold highlight.
- '이벤트 페이지 열기' is displayed only when a real link is found in the
  source event section or official event list.
- Startup still runs the first-page update scan automatically; closing exits.

[Windows build]
1. Install a supported 64-bit Python 3.11, 3.12 or 3.13 with pip.
2. Extract the ZIP, then double-click build_windows.bat inside GE_Event.
3. The script installs dependencies, downloads the official GE favicon
   if ge.ico is missing, and builds dist\GE 이벤트.exe.
4. If favicon acquisition fails, the script stops rather than making up an icon.
5. The Python source ZIP is not a compiled EXE. Windows build was NOT
   executable-tested by the packaging environment.

[Data]
Existing event history and manual hiding are stored in events.db alongside
GE 이벤트.exe. Copy/backup the existing DB to that location before launch.
The first migration may temporarily take longer because SQLite compacts
previously cached image data.

[Limitations]
- Live scraping and Windows GUI rendering not verified in this environment.
- The requested official GE artwork as the outer GUI background has NOT yet
  been included: source/artwork use rights and asset selection remain unverified.
- Event-page links are shown only for confirmed original event links; not all
  events will have a link.

[v9 UI 변경 사항]
- 진행/종료 상태 아이콘을 이벤트 제목 바로 왼쪽 첫 열로 이동했습니다.
- 이벤트별 숨김 체크박스는 오른쪽 끝에 유지하고 진한 브라운 외곽선/체크 표시를 적용했습니다.
- 선택된 행에는 통일된 샴페인 골드 배경을 적용하며 셀 포커스 외곽선을 그리지 않습니다.
- 수집 및 DB 동작은 v8 그대로 유지합니다.
- Windows EXE 빌드/실행은 이 배포 환경에서 검증하지 못했습니다.

[v10] To restore a manually hidden event, turn on "숨긴 이벤트 보기" at the top, uncheck its rightmost checkbox, then turn off "숨긴 이벤트 보기". This recovery view also shows ended events; your existing hide-filter setting stays unchanged.

[v11 체크박스 복구 동작]
- 별도의 '숨긴 이벤트 보기' 체크박스는 없습니다.
- 항목 오른쪽 체크박스를 선택해도 그 행은 당장 사라지지 않습니다. 같은 체크박스를 다시 누르면 해제할 수 있습니다.
- 상단 '종료된 이벤트 숨기기'를 끄면 모든 항목이 표시되며, 체크된 항목을 직접 해제할 수 있습니다.
- 위 옵션을 다시 켜면 종료된 항목과 체크된 항목을 숨깁니다.
- 체크 내역은 events.db에 보존합니다. 기존 데이터베이스를 삭제하지 마세요.

[v12 체크박스 클릭 문제 수정]
- 기존 QTableWidgetItem + delegate.editorEvent 클릭 방식 대신 독립적인 실제 QCheckBox 위젯으로 교체했습니다.
- 체크/해제 때 고유 이벤트 ID로 DB를 직접 갱신하며 재실행 후에도 유지됩니다.
- 상단 종료된 이벤트 숨기기가 켜져 있어도 방금 체크한 행은 남아 있어서 같은 체크박스를 다시 클릭해 취소할 수 있습니다.
- 상단 필터를 껐다 켜거나 프로그램을 다시 실행하면 체크된 이벤트가 숨겨집니다.
- 이미 숨겨진 이벤트를 복구하려면 기존 상단 '종료된 이벤트 숨기기'를 끄고 해당 이벤트 체크를 해제한 다음 다시 켜세요.
- '숨긴 이벤트 보기' 기능은 없습니다.
- EXE 및 Windows GUI에서 마우스 클릭 동작까지 검증한 상태는 아닙니다.

[v13 수정 - 2026-11-06]
- '종료된 이벤트 숨기기'가 켜진 동안 개별 숨김 체크박스를 선택하면 즉시 목록에서 숨깁니다.
- 복구: 상단 '종료된 이벤트 숨기기' 해제 -> 개별 체크 해제 -> 상단 옵션 다시 선택.
- 별도의 '숨긴 이벤트 보기' 옵션은 추가하지 않습니다.
- 이벤트 페이지 링크: 공식 이벤트 목록의 EventView.aspx?eid=... 주소와
  /event/, /event-2/ 주소를 실제 수집된 주소에 한하여 인정합니다.
- 기존 DB의 이벤트도 실행 시 공식 이벤트 목록에서 누락 링크를 재확인합니다.
- 과거 이벤트 페이지 탐색을 위해 종료 이벤트 목록 최대 10페이지를 확인합니다.
- 이벤트 이미지 수집/DB 보관/상세 표시 기능은 계속 비활성화합니다.
- 기존 events.db는 지우지 마세요. 빌드 ZIP에는 사용자 DB가 포함되지 않습니다.
- 이 배포는 소스 및 Windows 빌드 스크립트입니다. Windows EXE 자체가 아닙니다.
- 공식 사이트 실수집 및 실제 Windows GUI 클릭 테스트는 수행되지 않았습니다.

[v14 중복 이벤트 재등장 방지 - 2026-11-06]
- 이전 버전에서 중복 또는 종료 공지로 판별되어 숨긴 이벤트가
  공식 이벤트 목록의 기간 보완 이후 다시 나타나는 문제를 수정했습니다.
- 실행하거나 새 공지를 수집할 때 hidden_events 전체 기록을 초기화하지 않고
  기존 중복 억제 상태를 유지합니다.
- DB에서 실제 삭제된 이벤트의 오래된 중복 억제 기록만 정리합니다.
- 서로 다른 연도/기간의 동일 이름 이벤트는 임의로 중복 취급하지 않습니다.
- 사용자 체크박스 숨김 상태(user_hidden_events)는 변경하지 않습니다.
- 기존 events.db를 백업 후 같은 위치에서 그대로 사용하세요.
- v14는 수정 소스 및 Windows 빌드 스크립트입니다. EXE는 포함되지 않습니다.
- Windows GUI 실사용 및 홈페이지 실수집 검증은 아직 수행되지 않았습니다.

[v15 기간 미확인 이벤트 목록 제외 - 2026-11-06]
- 시작일과 종료일이 모두 유효한 날짜로 확인된 이벤트만 목록에 표시합니다.
- 날짜 중 하나라도 누락/잘못되었거나 종료일이 시작일보다 빠르면 표시하지 않습니다.
- '종료된 이벤트 숨기기'를 해제하더라도 날짜가 불완전한 이벤트는 표시하지 않습니다.
- 기존 events.db의 데이터를 삭제하거나 수동 숨김 기록을 변경하지 않습니다.
- 추후 공지/공식 이벤트 목록에서 기간이 보완되면 정상 필터에 따라 표시됩니다.
- Windows EXE 생성 및 실사이트 데이터 수집은 검증되지 않았습니다.

[v16: 이벤트 페이지 링크만 수정]
- 공식 이벤트 목록에서 이미지 링크(.jpg)를 이벤트 페이지로 오인하지 않습니다.
- 이벤트 카드의 onclick/data-url 등에 기록된 실제 EventView.aspx(eid) 주소를 읽습니다.
- '[Black Out] 업데이트 기념 웹 이벤트'처럼 대괄호 캠페인명과 긴 제목의 연결을 보완합니다.
- 다른 시기의 하위 이벤트로 잘못 연결되지 않도록 날짜와 제목을 함께 검증합니다.
- 기존 events.db 삭제 없이, 실행 시 링크가 비어 있는 항목은 공식 이벤트 목록을 재확인합니다.
- 웹페이지에 실제 이벤트 주소/이벤트 ID가 존재하지 않으면 버튼을 숨깁니다.
- 이전 v15의 이벤트 기간 필터, UI, 체크박스 동작은 변경하지 않았습니다.


[v17] 이벤트 설명 형광펜
- 이벤트 설명에서 마우스로 글자를 선택하고 상단의 노랑·연두·분홍 색상 버튼을 클릭해 강조합니다.
- 선택된 글자에 겹치는 형광펜은 지우개 버튼으로 제거할 수 있습니다.
- 강조 표시의 위치, 텍스트, 색상은 events.db의 event_highlights 테이블에 저장됩니다.
- 원본 공지/이벤트 HTML, 보상표는 수정하지 않습니다.
- 공지가 갱신되어 선택 텍스트의 위치가 달라지면 동일 문구를 찾아 강조 표시를 복원합니다.
- 동일 문구가 여러 번 나오거나 원문이 크게 수정되면 표시 위치가 정확하지 않을 수 있습니다.
- 별도의 이미지 수집 또는 표시 기능은 추가하지 않았습니다.
- 이번 배포물은 Windows EXE 자체가 아니라 Windows EXE 빌드용 소스입니다.

[v18 형광펜 지우개 변경 - 2026-11-09]
- 형광펜 제목 왼쪽 아이콘과 지우개 아이콘을 제거했습니다.
- 지우개를 누르면 텍스트 선택 없이 현재 선택된 이벤트의 형광펜이 모두 제거됩니다.
- 변경은 즉시 events.db에 저장되고, 다른 이벤트의 강조 내용에는 영향을 주지 않습니다.
- 다른 수집/표시 기능은 v17과 동일합니다.

[v19 변경사항]
- Windows 제목 표시줄과 GUI 상단 제목을 GRANADO ESPADA · EVENT CHRONICLE 로 변경했습니다. EXE 파일명은 기존 GE 이벤트.exe를 유지합니다.
- 이벤트 본문 중 「다음은 오탈자에 해당하는 사항입니다.」 이후는 이벤트 영역에서 제외합니다.
- 파서 버전 증가로 기존 저장 공지도 새 규칙으로 한 번 재분석하도록 했습니다.
