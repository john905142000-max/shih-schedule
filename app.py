import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import json
import urllib.parse
import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import sqlite3
import csv
import io
import socket
import threading
import time

from database import init_db, get_db, get_setting, set_setting, save_crawled_courses
from crawler import SchoolCrawler
from calculator import get_available_months, get_monthly_calculation, DAY_NAMES

PORT = int(os.environ.get('PORT', 7860))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return '127.0.0.1'

class ScheduleAppHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            params = urllib.parse.parse_qs(parsed.query)

            # 1. Static Files
            if path == '/' or path == '/index.html':
                html_path = os.path.join(STATIC_DIR, 'index.html')
                if not os.path.exists(html_path):
                    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
                self.serve_file(html_path, 'text/html; charset=utf-8')
                return
            elif path.startswith('/static/'):
                filepath = os.path.join(STATIC_DIR, path[8:])
                if os.path.exists(filepath):
                    ext = filepath.split('.')[-1].lower()
                    mime_map = {'css': 'text/css', 'js': 'application/javascript', 'html': 'text/html', 'png': 'image/png', 'svg': 'image/svg+xml'}
                    self.serve_file(filepath, mime_map.get(ext, 'text/plain'))
                    return

            # 2. API: Live Live Crawler Sync
            if path == '/api/sync/live':
                try:
                    crawler = SchoolCrawler()
                    sem_data = crawler.fetch_current_semester('2026-09-19')
                    save_crawled_courses(sem_data)
                    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    set_setting('last_sync_time', now_str)
                    self.send_json({
                        'status': 'ok',
                        'message': '校網全學期課表已自動連線即時更新完成！',
                        'last_sync_time': now_str,
                        'total_courses': 543
                    })
                except Exception as e:
                    self.send_json({'status': 'error', 'message': f'同步錯誤: {e}'}, status=500)
                return

            # 3. API: Available Months
            if path == '/api/months':
                months = get_available_months()
                self.send_json({'status': 'ok', 'months': months})
                return

            # 4. API: Monthly Calculation
            if path == '/api/monthly':
                ym = params.get('ym', [datetime.date.today().strftime('%Y-%m')])[0]
                calc_data = get_monthly_calculation(ym)
                self.send_json({'status': 'ok', 'data': calc_data})
                return

            # 5. API: Week Schedule
            if path == '/api/schedule/week':
                date_param = params.get('date', [datetime.date.today().strftime('%Y-%m-%d')])[0]
                
                conn = get_db()
                cursor = conn.cursor()
                
                cursor.execute('SELECT week_str, week_num FROM courses WHERE date = ? LIMIT 1', (date_param,))
                row = cursor.fetchone()
                if not row:
                    cursor.execute('SELECT week_str, week_num FROM courses ORDER BY ABS(julianday(date) - julianday(?)) ASC LIMIT 1', (date_param,))
                    row = cursor.fetchone()
                    
                if not row:
                    conn.close()
                    self.send_json({'status': 'error', 'message': '尚無課表資料，請先同步校網！'}, status=404)
                    return
                    
                week_str = row['week_str']
                week_num = row['week_num']

                # Get distinct dates of this week
                cursor.execute('SELECT DISTINCT day, date FROM courses WHERE week_str = ? ORDER BY day ASC', (week_str,))
                day_dates = {r['day']: r['date'] for r in cursor.fetchall()}

                # Determine prev and next week dates
                cursor.execute('SELECT DISTINCT date FROM courses WHERE date < ? ORDER BY date DESC LIMIT 1', (min(day_dates.values()) if day_dates else date_param,))
                prev_row = cursor.fetchone()
                prev_w = prev_row['date'] if prev_row else None

                cursor.execute('SELECT DISTINCT date FROM courses WHERE date > ? ORDER BY date ASC LIMIT 1', (max(day_dates.values()) if day_dates else date_param,))
                next_row = cursor.fetchone()
                next_w = next_row['date'] if next_row else None

                # Get all courses for this week
                cursor.execute('SELECT * FROM courses WHERE week_str = ?', (week_str,))
                courses = cursor.fetchall()
                conn.close()

                # Build 9x5 grid (Periods 0-8, Days 1-5)
                grid = {p: {d: None for d in range(1, 6)} for p in range(0, 9)}
                for c in courses:
                    p = c['period']
                    d = c['day']
                    if p in grid and d in grid[p]:
                        grid[p][d] = {
                            'id': c['id'],
                            'subject': c['subject'],
                            'class_name': c['class_name'],
                            'raw_text': c['raw_text'],
                            'is_substitute': bool(c['is_substitute']),
                            'is_concurrent': bool(c['is_concurrent']) or ('(兼)' in (c['raw_text'] or '')) or ('(兼)' in (c['subject'] or '')),
                            'is_adjusted': bool(c['is_adjusted']),
                            'adjust_note': c['adjust_note'] if c['is_adjusted'] else '',
                            'is_period_8': (p == 8) or ('(輔)' in (c['raw_text'] or '')),
                            'is_morning_remedial': (p == 0 and not bool(c['is_concurrent']))
                        }

                self.send_json({
                    'status': 'ok',
                    'week_str': week_str,
                    'week_num': week_num,
                    'target_date': date_param,
                    'day_dates': day_dates,
                    'prev_week': prev_w,
                    'next_week': next_w,
                    'grid': grid
                })
                return

            # 6. API: Today's Schedule
            if path == '/api/schedule/today':
                today_str = datetime.date.today().strftime('%Y-%m-%d')
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM courses WHERE date = ? ORDER BY period ASC', (today_str,))
                courses = cursor.fetchall()
                conn.close()

                res_courses = []
                for c in courses:
                    p = c['period']
                    res_courses.append({
                        'id': c['id'],
                        'period': p,
                        'subject': c['subject'],
                        'class_name': c['class_name'],
                        'is_substitute': bool(c['is_substitute']),
                        'is_concurrent': bool(c['is_concurrent']) or ('(兼)' in (c['raw_text'] or '')) or ('(兼)' in (c['subject'] or '')),
                        'is_adjusted': bool(c['is_adjusted']),
                        'adjust_note': c['adjust_note'] if c['is_adjusted'] else '',
                        'is_period_8': (p == 8) or ('(輔)' in (c['raw_text'] or '')),
                        'is_morning_remedial': (p == 0 and not bool(c['is_concurrent']))
                    })

                self.send_json({
                    'status': 'ok',
                    'today': today_str,
                    'courses': res_courses
                })
                return

            # 7. API: Settings
            if path == '/api/settings':
                sub_rate = get_setting('substitute_rate', '455')
                p8_rate = get_setting('period_8_rate', '540')
                remedial_rate = get_setting('morning_remedial_rate', '455')
                concurrent_rate = get_setting('concurrent_rate', '455')
                remedial_days = get_setting('morning_remedial_days', '1,3,4')
                remedial_start = get_setting('remedial_start_date', '')
                remedial_end = get_setting('remedial_end_date', '')
                eighth_start = get_setting('eighth_start_date', '')
                eighth_end = get_setting('eighth_end_date', '')
                last_sync = get_setting('last_sync_time', datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))
                teacher_name = get_setting('teacher_name', '施智凱')
                self.send_json({
                    'status': 'ok',
                    'settings': {
                        'substitute_rate': float(sub_rate),
                        'period_8_rate': float(p8_rate),
                        'morning_remedial_rate': float(remedial_rate),
                        'concurrent_rate': float(concurrent_rate),
                        'morning_remedial_days': remedial_days,
                        'remedial_start_date': remedial_start,
                        'remedial_end_date': remedial_end,
                        'eighth_start_date': eighth_start,
                        'eighth_end_date': eighth_end,
                        'last_sync_time': last_sync,
                        'teacher_name': teacher_name
                    }
                })
                return

            self.send_error(404, "Page Not Found")
        except Exception as e:
            print(f"[do_GET Error] {e}")
            self.send_json({'status': 'error', 'message': str(e)}, status=500)

    def do_POST(self):
        try:
            content_len = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_len)
            data = json.loads(post_body.decode('utf-8')) if post_body else {}

            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            # Save Settings
            if path == '/api/settings':
                for k in ['substitute_rate', 'period_8_rate', 'morning_remedial_rate', 'concurrent_rate', 'morning_remedial_days', 'teacher_name', 'remedial_start_date', 'remedial_end_date', 'eighth_start_date', 'eighth_end_date']:
                    if k in data:
                        set_setting(k, data[k])
                self.send_json({'status': 'ok', 'message': '設定儲存成功！'})
                return

            # Add Manual Record
            if path == '/api/manual/add':
                date = data.get('date')
                period = int(data.get('period', 0))
                class_name = data.get('class_name', '')
                subject = data.get('subject', '')
                record_type = data.get('record_type', 'substitute')
                amount = float(data.get('amount', 0))
                note = data.get('note', '')

                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO manual_records (date, period, class_name, subject, record_type, amount, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (date, period, class_name, subject, record_type, amount, note))
                conn.commit()
                conn.close()
                self.send_json({'status': 'ok', 'message': '手動課堂紀錄新增成功！'})
                return

            # Delete Manual Record
            if path == '/api/manual/delete':
                rec_id = data.get('id')
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM manual_records WHERE id = ?', (rec_id,))
                conn.commit()
                conn.close()
                self.send_json({'status': 'ok', 'message': '紀錄已刪除！'})
                return

            self.send_error(404, "Unknown API")
        except Exception as e:
            print(f"[do_POST Error] {e}")
            self.send_json({'status': 'error', 'message': str(e)}, status=500)

    def serve_file(self, filepath, content_type):
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")

def background_daily_sync_worker():
    """Cloud Auto-Sync: Automatically syncs with school once every 4 hours."""
    time.sleep(5)
    while True:
        try:
            print("[Cloud Background Worker] 正在執行例行校網課表自動同步...")
            crawler = SchoolCrawler()
            sem_data = crawler.fetch_current_semester('2026-09-19')
            save_crawled_courses(sem_data)
            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            set_setting('last_sync_time', now_str)
            print(f"[Cloud Background Worker] ✅ 自動同步完成！時間：{now_str}")
        except Exception as e:
            print(f"[Cloud Background Worker] ⚠️ 同步錯誤: {e}")
        time.sleep(4 * 3600)

def run_server(port=PORT):
    init_db()
    t = threading.Thread(target=background_daily_sync_worker, daemon=True)
    t.start()
    
    server_address = ('0.0.0.0', port)
    httpd = ThreadingHTTPServer(server_address, ScheduleAppHandler)
    httpd.allow_reuse_address = True
    print(f"🚀 施智凱老師 課表與津貼系統已啟動！(Port: {port})")
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()
