import sys
sys.stdout.reconfigure(encoding='utf-8')
import urllib.request
import urllib.parse
import http.cookiejar
import xml.etree.ElementTree as ET
import re
import html
import datetime

BASE_URL = 'https://hanshin-test.ischool.com.tw'
LOGIN_URL = f'{BASE_URL}/ssjh/j_security_check'

class SchoolCrawler:
    def __init__(self, username='ssjhteacher', password='course', teacher_no=154):
        self.username = username
        self.password = password
        self.teacher_no = teacher_no
        self.opener = None

    def login(self):
        cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
        self.opener.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        ]
        for attempt in range(3):
            try:
                self.opener.open(f'{BASE_URL}/ssjh/termRT', timeout=20)
                login_payload = urllib.parse.urlencode({
                    'j_username': self.username,
                    'j_password': self.password
                }).encode('utf-8')
                req = urllib.request.Request(LOGIN_URL, data=login_payload)
                self.opener.open(req, timeout=20)
                return True
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(1)

    def fetch_week(self, week_str):
        if not self.opener:
            self.login()
        url = f'{BASE_URL}/ssjh/teacherRTAjax?teacherNo={self.teacher_no}&thisWeek={week_str}&classNo=0'
        raw = None
        for attempt in range(3):
            try:
                resp = self.opener.open(url, timeout=20)
                raw = resp.read()
                break
            except Exception:
                try:
                    self.login()
                    resp = self.opener.open(url, timeout=20)
                    raw = resp.read()
                    break
                except Exception as e:
                    if attempt == 2:
                        raise e
                    time.sleep(1)

        try:
            xml_str = raw.decode('utf-8')
        except:
            xml_str = raw.decode('cp950', errors='ignore')

        root = ET.fromstring(xml_str)
        
        prev_week = None
        next_week = None
        week_num = ""
        day_dates = {}

        ref_year = int(week_str.split('-')[0])

        for w in root.findall('wIndex'):
            wid = w.get('id')
            txt = html.unescape(w.text or '')
            if wid == 'wIndex1':
                m = re.search(r"(\d{4}-\d{2}-\d{2})", txt)
                if m: prev_week = m.group(1)
            elif wid == 'wIndex3':
                m = re.search(r"(\d{4}-\d{2}-\d{2})", txt)
                if m: next_week = m.group(1)
            elif wid == 'wIndex0':
                week_num = re.sub(r'<[^>]+>', '', txt).strip()
            elif wid in ['w1', 'w2', 'w3', 'w4', 'w5', 'w6']:
                m = re.search(r"(\d{2})-(\d{2})", txt)
                if m:
                    d_idx = int(wid[1])
                    mm, dd = int(m.group(1)), int(m.group(2))
                    day_dates[d_idx] = f"{ref_year:04d}-{mm:02d}-{dd:02d}"

        courses = []
        for pidx in root.findall('pIndex'):
            pid = pidx.get('id')
            m = re.match(r's(\d)(\d)H1', pid)
            if m:
                day = int(m.group(1))
                period = int(m.group(2))
                raw_html = html.unescape(pidx.text or '')
                clean_text = re.sub(r'<br\s*/?>', ' / ', raw_html)
                clean_text = re.sub(r'<[^<]+?>', '', clean_text).strip()
                
                if clean_text and day in range(1, 6) and period in range(0, 9):
                    course_date = day_dates.get(day, "")
                    
                    is_sub = '[代]' in clean_text or '代課' in clean_text or '[公代]' in clean_text or '[自代]' in clean_text
                    is_concurrent = '(兼)' in clean_text or '[兼]' in clean_text
                    is_adj = '[調' in clean_text
                    adj_m = re.search(r'\[調([^\]]+)\]', clean_text)
                    adj_note = adj_m.group(0) if adj_m else ""
                    
                    parts = [p.strip() for p in clean_text.split('/') if p.strip()]
                    subject = parts[0] if len(parts) > 0 else clean_text
                    class_name = parts[1] if len(parts) > 1 else ""
                    if '(兼)' in subject:
                        is_concurrent = True
                    
                    courses.append({
                        'week_str': week_str,
                        'week_num': week_num,
                        'date': course_date,
                        'day': day,
                        'period': period,
                        'subject': subject,
                        'class_name': class_name,
                        'raw_text': clean_text,
                        'is_substitute': is_sub,
                        'is_concurrent': is_concurrent,
                        'is_adjusted': is_adj,
                        'adjust_note': adj_note,
                        'is_period_8': (period == 8 or '理化(輔)' in clean_text)
                    })

        return {
            'week_str': week_str,
            'week_num': week_num,
            'prev_week': prev_week,
            'next_week': next_week,
            'day_dates': day_dates,
            'courses': courses
        }

    def fetch_current_semester(self, initial_week='2026-09-19'):
        """Fetches all weeks of active semester without infinite loop."""
        all_weeks_data = {}
        visited = set()
        
        # Ensure login
        self.login()

        # 1. Fetch initial week
        curr = self.fetch_week(initial_week)
        all_weeks_data[initial_week] = curr
        visited.add(initial_week)
        
        # 2. Go backwards to Week 01
        p = curr['prev_week']
        while p and p not in visited and len(visited) < 30:
            visited.add(p)
            try:
                w_data = self.fetch_week(p)
            except Exception:
                break
            if not w_data['week_num'] or '00' in w_data['week_num']:
                break
            all_weeks_data[p] = w_data
            if '01' in w_data['week_num']:
                break
            p = w_data['prev_week']
            
        # 3. Go forwards to end of semester
        n = curr['next_week']
        while n and n not in visited and len(visited) < 30:
            visited.add(n)
            try:
                w_data = self.fetch_week(n)
            except Exception:
                break
            if not w_data['week_num'] or '00' in w_data['week_num']:
                break
            all_weeks_data[n] = w_data
            n = w_data['next_week']
            
        return all_weeks_data

if __name__ == '__main__':
    crawler = SchoolCrawler()
    print("Testing crawler...")
    weeks = crawler.fetch_current_semester()
    print("Fetched weeks successfully:", len(weeks))
