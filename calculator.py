import sys
sys.stdout.reconfigure(encoding='utf-8')
import datetime
from database import get_db, get_setting

DAY_NAMES = {1: '週一', 2: '週二', 3: '週三', 4: '週四', 5: '週五', 6: '週六', 7: '週日'}

def get_available_months():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT substr(date, 1, 7) as ym FROM courses WHERE date != ""
        UNION
        SELECT DISTINCT substr(date, 1, 7) as ym FROM manual_records WHERE date != ""
        ORDER BY ym ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    months = [r['ym'] for r in rows if r['ym']]
    if not months:
        months = [datetime.date.today().strftime('%Y-%m')]
    return months

def get_monthly_calculation(year_month):
    """
    Calculates monthly statistics and itemized allowances for a given month (YYYY-MM).
    Includes:
      - 學習扶助 (早自修): $455/堂 (預設週一、週三、週四)
      - 代課: $455/堂
      - 第八節輔導: $540/堂
      - 調課紀錄
    """
    conn = get_db()
    cursor = conn.cursor()
    
    sub_rate = float(get_setting('substitute_rate', '455'))
    p8_rate = float(get_setting('period_8_rate', '540'))
    remedial_rate = float(get_setting('morning_remedial_rate', '455'))
    concurrent_rate = float(get_setting('concurrent_rate', '455'))
    
    # 1. Fetch system crawled courses for this month
    cursor.execute('''
        SELECT * FROM courses 
        WHERE date LIKE ? 
        ORDER BY date ASC, period ASC
    ''', (f"{year_month}%",))
    course_rows = cursor.fetchall()
    
    # 2. Fetch manual records for this month
    cursor.execute('''
        SELECT * FROM manual_records 
        WHERE date LIKE ? 
        ORDER BY date ASC, period ASC
    ''', (f"{year_month}%",))
    manual_rows = cursor.fetchall()
    conn.close()
    
    remedial_items = []
    concurrent_items = []
    substitute_items = []
    period_8_items = []
    adjusted_items = []
    regular_items = []
    
    # Process system courses
    for c in course_rows:
        d_obj = datetime.datetime.strptime(c['date'], '%Y-%m-%d').date() if c['date'] else None
        day_name = DAY_NAMES.get(d_obj.isoweekday(), '') if d_obj else ''
        
        is_remedial = bool(c['is_morning_remedial']) or (c['period'] == 0 and '學習扶助' in (c['subject'] or ''))
        raw_text_val = c['raw_text'] or ''
        subject_val = c['subject'] or ''
        is_concurrent = bool(c['is_concurrent']) if 'is_concurrent' in c.keys() else False
        if not is_concurrent:
            is_concurrent = ('(兼)' in raw_text_val or '(兼)' in subject_val or '[兼]' in raw_text_val or '[兼]' in subject_val)
        
        item = {
            'source': 'system',
            'id': c['id'],
            'date': c['date'],
            'day_name': day_name,
            'period': c['period'],
            'subject': c['subject'],
            'class_name': c['class_name'],
            'raw_text': c['raw_text'],
            'is_substitute': bool(c['is_substitute']),
            'is_adjusted': bool(c['is_adjusted']),
            'adjust_note': c['adjust_note'],
            'is_period_8': bool(c['is_period_8']),
            'is_morning_remedial': is_remedial,
            'is_concurrent': is_concurrent,
            'unit_price': 0,
            'amount': 0,
            'tag': '一般課'
        }
        
        if is_remedial:
            item['unit_price'] = remedial_rate
            item['amount'] = remedial_rate
            item['tag'] = '早自習扶助'
            remedial_items.append(item)
        elif is_concurrent:
            item['unit_price'] = concurrent_rate
            item['amount'] = concurrent_rate
            item['tag'] = '超時兼課'
            concurrent_items.append(item)
        elif c['is_substitute']:
            item['unit_price'] = sub_rate
            item['amount'] = sub_rate
            item['tag'] = '代課'
            substitute_items.append(item)
        elif c['is_period_8'] or c['period'] == 8:
            item['unit_price'] = p8_rate
            item['amount'] = p8_rate
            item['tag'] = '第八節'
            period_8_items.append(item)
        elif c['is_adjusted']:
            item['tag'] = '調課'
            adjusted_items.append(item)
        else:
            regular_items.append(item)

    # Process manual records
    for m in manual_rows:
        d_obj = datetime.datetime.strptime(m['date'], '%Y-%m-%d').date() if m['date'] else None
        day_name = DAY_NAMES.get(d_obj.isoweekday(), '') if d_obj else ''
        
        m_type = m['record_type']
        amt = m['amount']
        
        item = {
            'source': 'manual',
            'id': m['id'],
            'date': m['date'],
            'day_name': day_name,
            'period': m['period'],
            'subject': m['subject'],
            'class_name': m['class_name'],
            'raw_text': f"{m['subject']} / {m['class_name']}",
            'is_substitute': (m_type == 'substitute'),
            'is_adjusted': (m_type == 'adjusted'),
            'adjust_note': m['note'],
            'is_period_8': (m_type == 'period_8'),
            'is_morning_remedial': (m_type == 'morning_remedial'),
            'is_concurrent': (m_type == 'concurrent'),
            'unit_price': amt,
            'amount': amt,
            'tag': f"手動-{m_type}"
        }
        
        if m_type == 'morning_remedial':
            if amt == 0: amt = remedial_rate
            item['amount'] = amt
            item['tag'] = '手動學習扶助'
            remedial_items.append(item)
        elif m_type == 'concurrent':
            if amt == 0: amt = concurrent_rate
            item['amount'] = amt
            item['tag'] = '手動超時兼課'
            concurrent_items.append(item)
        elif m_type == 'substitute':
            if amt == 0: amt = sub_rate
            item['amount'] = amt
            item['tag'] = '手動代課'
            substitute_items.append(item)
        elif m_type == 'period_8':
            if amt == 0: amt = p8_rate
            item['amount'] = amt
            item['tag'] = '手動第八節'
            period_8_items.append(item)
        elif m_type == 'adjusted':
            item['tag'] = '手動調課'
            adjusted_items.append(item)
            
    # Calculate Totals
    remedial_count = len(remedial_items)
    remedial_total = sum(x['amount'] for x in remedial_items)

    concurrent_count = len(concurrent_items)
    concurrent_total = sum(x['amount'] for x in concurrent_items)

    sub_count = len(substitute_items)
    sub_total = sum(x['amount'] for x in substitute_items)
    
    p8_count = len(period_8_items)
    p8_total = sum(x['amount'] for x in period_8_items)
    
    adj_count = len(adjusted_items)
    total_allowance = remedial_total + concurrent_total + sub_total + p8_total
    
    # Combined itemized list for accounting breakdown
    breakdown_list = remedial_items + concurrent_items + substitute_items + period_8_items + adjusted_items
    breakdown_list.sort(key=lambda x: (x['date'], x['period']))
    
    return {
        'year_month': year_month,
        'rates': {
            'morning_remedial_rate': remedial_rate,
            'concurrent_rate': concurrent_rate,
            'substitute_rate': sub_rate,
            'period_8_rate': p8_rate
        },
        'summary': {
            'total_allowance': int(total_allowance),
            'morning_remedial_count': remedial_count,
            'morning_remedial_total': int(remedial_total),
            'concurrent_count': concurrent_count,
            'concurrent_total': int(concurrent_total),
            'substitute_count': sub_count,
            'substitute_total': int(sub_total),
            'period_8_count': p8_count,
            'period_8_total': int(p8_total),
            'adjusted_count': adj_count,
            'total_classes': len(course_rows) + len(manual_rows)
        },
        'breakdown_list': breakdown_list,
        'remedial_items': remedial_items,
        'concurrent_items': concurrent_items,
        'substitute_items': substitute_items,
        'period_8_items': period_8_items,
        'adjusted_items': adjusted_items
    }
