import sys
sys.stdout.reconfigure(encoding='utf-8')
import urllib.request
import json
import sqlite3
import re
from crawler import SchoolCrawler

print("=== 1. 連線壽山校網抓取 10/8 所在週次 ===")
crawler = SchoolCrawler()
crawler.login()

resp = crawler.opener.open('https://hanshin-test.ischool.com.tw/ssjh/termRT')
html = resp.read().decode('utf-8', errors='ignore')
week_options = re.findall(r'<option[^>]*value=[\'"]([^\'"]+)[\'"][^>]*>([^<]+)</option>', html)

courses_1008_school = []
for val, label in week_options:
    data = crawler.fetch_week(val)
    for c in data.get('courses', []):
        if c.get('date') == '2026-10-08':
            courses_1008_school.append(c)

print(f"校網 10/8 課程數: {len(courses_1008_school)}")
for c in courses_1008_school:
    print(f"  節次: {c['period']}, 科目: {c['subject']}, 班級: {c['class_name']}, 原始: {c['raw_text']}")

print("\n=== 2. 檢查本地 schedule.db 10/8 課程 ===")
conn = sqlite3.connect('schedule.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM courses WHERE date = "2026-10-08" ORDER BY period ASC')
db_1008 = cursor.fetchall()
print(f"資料庫 10/8 課程數: {len(db_1008)}")
for r in db_1008:
    print(f"  ID:{r[0]} 節次:{r[5]} 科目:{r[6]} 班級:{r[7]} 原始:{r[8]} 調課:{r[10]} 筆記:{r[11]}")
conn.close()

print("\n=== 3. 檢查 Render 雲端伺服器 10/8 API ===")
try:
    req = urllib.request.Request('https://shih-schedule.onrender.com/api/schedule/week?date=2026-10-08', headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        cloud_data = json.loads(r.read().decode('utf-8'))
        print(f"Render 週次: {cloud_data.get('week_str')}, 週數: {cloud_data.get('week_num')}")
        grid = cloud_data.get('grid', {})
        print("Render 10/8 (週四 day=4) 各節課:")
        for p in range(0, 9):
            cell = grid.get(str(p), {}).get('4')
            if cell:
                print(f"  第 {p} 節: {cell.get('subject')} ({cell.get('class_name')}) raw={cell.get('raw_text')} adj={cell.get('is_adjusted')} note={cell.get('adjust_note')}")
except Exception as e:
    print("Render API error:", e)
