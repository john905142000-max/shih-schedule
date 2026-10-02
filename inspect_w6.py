import sys
sys.stdout.reconfigure(encoding='utf-8')
from crawler import SchoolCrawler

crawler = SchoolCrawler()
crawler.login()
w6 = crawler.fetch_week('2026-10-10') # 06週
print(f"週次: {w6['week_str']}, 週別: {w6['week_num']}")
print("日期對應:", w6['day_dates'])

print("\n--- 校網 06 週所有課程 ---")
for c in w6['courses']:
    print(f"  週{c['day']} ({c['date']}) 第{c['period']}節: {c['subject']} ({c['class_name']}) -> {c['raw_text']}")
