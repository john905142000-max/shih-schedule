import sys
sys.stdout.reconfigure(encoding='utf-8')
import re
import json

with open(r'C:\Users\user\Desktop\schedule-cloud-autoupdate\static\index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract EMBEDDED_COURSES from index.html
m = re.search(r'const EMBEDDED_COURSES\s*=\s*(\[.*?\]);', content, re.DOTALL)
if m:
    courses_json = m.group(1)
    courses = json.loads(courses_json)
    print(f"Total EMBEDDED_COURSES: {len(courses)}")
    
    # Check 10/8 courses
    c_1008 = [c for c in courses if c.get('date') == '2026-10-08']
    print(f"\n10/8 在 EMBEDDED_COURSES 中的課程 ({len(c_1008)} 堂):")
    for c in c_1008:
        print(f"  P{c.get('period')}: {c.get('subject')} ({c.get('class_name')}) raw={c.get('raw_text')}")
        
    # Check Week 6 courses (all)
    w6_courses = [c for c in courses if c.get('week_str') == '2026-10-10' or c.get('week_num') == '06週' or (c.get('date') and '2026-10-05' <= c.get('date') <= '2026-10-09')]
    print(f"\n第 06 週所有課程 ({len(w6_courses)} 堂):")
    for c in sorted(w6_courses, key=lambda x: (x.get('date',''), x.get('period',0))):
        print(f"  日期: {c.get('date')} (週{c.get('day')}) P{c.get('period')}: {c.get('subject')} ({c.get('class_name')})")
else:
    print("Could not find EMBEDDED_COURSES in index.html")
