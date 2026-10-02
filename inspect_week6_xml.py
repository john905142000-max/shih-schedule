import sys
sys.stdout.reconfigure(encoding='utf-8')
import urllib.request
import re
import xml.etree.ElementTree as ET
from crawler import SchoolCrawler

crawler = SchoolCrawler()
crawler.login()

# Check what options exist in termRT
resp = crawler.opener.open('https://hanshin-test.ischool.com.tw/ssjh/termRT')
html = resp.read().decode('utf-8', errors='ignore')
pattern = re.compile(r'<option\s+value=["\']([^"\']+)["\'][^>]*>([^<]+)</option>')
options = pattern.findall(html)

print(f"找到 {len(options)} 個週次選項:")
for val, text in options[:10]:
    print(f"  {val} -> {text.strip()}")

print("\n=== 詳細檢查第 06 週 (含 10/8 週四) ===")
# Find option for 06週
target_val = None
for val, text in options:
    if '06' in text or '10-10' in val:
        target_val = val
        print(f"鎖定第 6 週: {val} ({text.strip()})")
        break

if target_val:
    url = f'https://hanshin-test.ischool.com.tw/ssjh/teacherRTAjax?teacherNo=154&thisWeek={target_val}&classNo=0'
    resp = crawler.opener.open(url)
    xml_data = resp.read().decode('utf-8', errors='ignore')
    print("\n[原始 XML 內容摘要]:")
    print(xml_data[:500])

    root = ET.fromstring(xml_data)
    print("\n[XML 解析結果]:")
    for child in root:
        text = child.text or ''
        tag = child.tag
        # Check Thursday (tag ends with 4, e.g. p04, p14, p24, etc.)
        if tag.endswith('4'):
            print(f"  節次代碼 {tag} (週四): {text}")
