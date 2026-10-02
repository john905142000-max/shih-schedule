import sys
sys.stdout.reconfigure(encoding='utf-8')
from crawler import SchoolCrawler

c = SchoolCrawler()
c.login()
weeks = c.fetch_current_semester('2026-09-19')

print("=== 壽山國中校網各週【週四】的排課狀況 ===")
for w_str in sorted(weeks.keys()):
    w_data = weeks[w_str]
    d_map = w_data['day_dates']
    thu_date = d_map.get(4, '')
    thu_courses = [c for c in w_data['courses'] if c['day'] == 4]
    
    c_desc = []
    for tc in sorted(thu_courses, key=lambda x: x['period']):
        c_desc.append(f"P{tc['period']}:{tc['subject']}({tc['class_name']})")
    
    print(f"[{w_data['week_num']}] 週四日期: {thu_date} | 課表: {', '.join(c_desc) if c_desc else '無課'}")
