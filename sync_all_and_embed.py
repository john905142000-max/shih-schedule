import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import json
import sqlite3
import datetime
from crawler import SchoolCrawler
from database import init_db, save_crawled_courses, get_db

print("1. 初始化資料庫並連線學校爬取全學期最新課表...")
init_db()
crawler = SchoolCrawler()
crawler.login()
sem_data = crawler.fetch_current_semester('2026-09-19')
print(f"爬取到 {len(sem_data)} 週資料")

print("2. 儲存至 schedule.db...")
save_crawled_courses(sem_data)

conn = get_db()
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) as cnt FROM courses')
total_cnt = cursor.fetchone()['cnt']
print(f"資料庫最新課程總數: {total_cnt}")

cursor.execute('SELECT * FROM courses WHERE date = "2026-10-08"')
courses_1008 = cursor.fetchall()
print(f"\n10/8 資料庫確認 ({len(courses_1008)} 堂):")
for c in courses_1008:
    print(f"  P{c['period']}: {c['subject']} ({c['class_name']}) is_sub={c['is_substitute']} raw={c['raw_text']}")

# 3. 讀取所有最新課程轉換為 JSON，直接替換 index.html 中的 EMBEDDED_COURSES
cursor.execute('SELECT * FROM courses ORDER BY date ASC, period ASC')
all_rows = cursor.fetchall()
conn.close()

courses_list = []
for c in all_rows:
    p = c['period']
    courses_list.append({
        'id': c['id'],
        'week_str': c['week_str'],
        'week_num': c['week_num'],
        'date': c['date'],
        'day': c['day'],
        'period': p,
        'subject': c['subject'],
        'class_name': c['class_name'],
        'raw_text': c['raw_text'],
        'is_substitute': bool(c['is_substitute']),
        'is_concurrent': bool(c['is_concurrent']) or ('(兼)' in (c['raw_text'] or '')) or ('(兼)' in (c['subject'] or '')),
        'is_adjusted': bool(c['is_adjusted']),
        'note': c['adjust_note'] if c['is_adjusted'] else '',
        'is_period_8': (p == 8) or ('(輔)' in (c['raw_text'] or '')),
        'is_morning_remedial': (p == 0 and not bool(c['is_concurrent']))
    })

print(f"\n3. 將 {len(courses_list)} 堂最新課表直接寫入 static/index.html...")
html_path = r'C:\Users\user\Desktop\schedule-cloud-autoupdate\static\index.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

import re
json_str = json.dumps(courses_list, ensure_ascii=False)
new_html = re.sub(r'const EMBEDDED_COURSES\s*=\s*\[.*?\];', f'const EMBEDDED_COURSES = {json_str};', html_content, flags=re.DOTALL)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(new_html)

print("✅ schedule.db 與 index.html 已 100% 更新為學校官方最新資料！")
