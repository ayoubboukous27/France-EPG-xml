import os
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import xml.dom.minidom as minidom

# مسار ملفات البيانات
DATA_DIR = "data"
CHANNELS_FILE = os.path.join(DATA_DIR, "programme-tv.net.channels.xml")
EPG_DIR = "epg"

# قراءة القنوات من XML
tree = ET.parse(CHANNELS_FILE)
root = tree.getroot()

channels = []
for ch in root.findall('channel'):
    channels.append({
        'name': ch.text,
        'site_id': ch.attrib['site_id'],
        'xmltv_id': ch.attrib.get('xmltv_id') or ch.attrib['site_id']
    })

# إنشاء مجلد epg إذا لم يكن موجود
if not os.path.exists(EPG_DIR):
    os.makedirs(EPG_DIR)

# إعداد اليوم الحالي
today = datetime.now()
date_str = today.strftime("%Y-%m-%d")

# إعداد XMLTV root
tv = ET.Element("tv")

# إضافة القنوات إلى XML
for ch in channels:
    channel_elem = ET.SubElement(tv, "channel", id=ch['xmltv_id'])
    ET.SubElement(channel_elem, "display-name").text = ch['name']

# وظيفة لتحويل الوقت إلى صيغة XMLTV
def xmltv_time(dt):
    return dt.strftime("%Y%m%d%H%M%S +0100")  # Paris timezone +01:00

# دالة لتحويل مدة نصية إلى دقائق
def parse_duration(duration_text):
    hours = minutes = 0
    duration_text = duration_text.lower().replace(" ", "")
    if 'h' in duration_text:
        parts = duration_text.split('h')
        try:
            hours = int(parts[0])
        except ValueError:
            hours = 0
        if len(parts) > 1:
            min_part = parts[1].replace('mn','').replace('min','')
            try:
                minutes = int(min_part)
            except ValueError:
                minutes = 0
    elif 'mn' in duration_text or 'min' in duration_text:
        min_part = duration_text.replace('mn','').replace('min','')
        try:
            minutes = int(min_part)
        except ValueError:
            minutes = 0
    return hours, minutes

# سحب EPG لكل قناة
for ch in channels:
    print(f"جارٍ سحب EPG للقناة: {ch['name']}")
    url = f"https://www.programme-tv.net/programme/chaine/{date_str}/programme-{ch['site_id']}.html"
    headers = {'cookie': 'authId=b7154156fe4fb8acdb6f38e1207c6231'}
    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
    except Exception as e:
        print(f"خطأ في تحميل {ch['name']}: {e}")
        continue

    soup = BeautifulSoup(r.text, 'html.parser')
    cards = soup.select('.mainBroadcastCard')
    for card in cards:
        title_tag = card.select_one('.mainBroadcastCard-title')
        subtitle_tag = card.select_one('.mainBroadcastCard-subtitle')
        start_tag = card.select_one('.mainBroadcastCard-startingHour')
        duration_tag = card.select_one('.mainBroadcastCard-durationContent')

        if not title_tag or not start_tag or not duration_tag:
            continue

        title = title_tag.get_text(strip=True)
        subtitle = subtitle_tag.get_text(strip=True) if subtitle_tag else None
        start_time = start_tag.get_text(strip=True).replace('h', ':')
        duration_text = duration_tag.get_text(strip=True)

        # تحويل وقت البدء ومدة البرنامج إلى datetime
        start_dt = datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %H:%M")
        hours, minutes = parse_duration(duration_text)
        end_dt = start_dt + timedelta(hours=hours, minutes=minutes)

        # إضافة البرنامج إلى XML
        prog = ET.SubElement(tv, "programme", {
            'start': xmltv_time(start_dt),
            'stop': xmltv_time(end_dt),
            'channel': ch['xmltv_id']
        })
        ET.SubElement(prog, "title").text = title
        if subtitle:
            ET.SubElement(prog, "sub-title").text = subtitle

# حفظ ملف XML
xml_file = os.path.join(EPG_DIR, f"epg-{date_str}.xml")
# تنسيق XML
xml_str = minidom.parseString(ET.tostring(tv)).toprettyxml(indent="  ")
with open(xml_file, "w", encoding="utf-8") as f:
    f.write(xml_str)

print(f"تم إنشاء ملف EPG: {xml_file}")
