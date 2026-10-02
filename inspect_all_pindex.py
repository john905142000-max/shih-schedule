import sys
sys.stdout.reconfigure(encoding='utf-8')
import xml.etree.ElementTree as ET
from crawler import SchoolCrawler

crawler = SchoolCrawler()
crawler.login()
url = 'https://hanshin-test.ischool.com.tw/ssjh/teacherRTAjax?teacherNo=154&thisWeek=2026-10-10&classNo=0'
resp = crawler.opener.open(url)
xml_str = resp.read().decode('utf-8', errors='ignore')
root = ET.fromstring(xml_str)

print("--- 所有 pIndex 元素 ---")
for p in root.findall('pIndex'):
    pid = p.get('id')
    txt = p.text or ''
    if txt.strip():
        print(f"ID={pid} -> {txt}")
