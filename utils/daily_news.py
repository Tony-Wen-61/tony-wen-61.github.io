# /// script
# dependencies = [
#   "requests",
# ]
# ///

import requests
import xml.etree.ElementTree as ET
import json
import os
import datetime
import html
import re

# We can change the RSSHub base URL to a stable public mirror
RSSHUB_BASE = "https://rsshub.rssforever.com"

FEEDS = {
    "国际新闻": [
        {"name": "联合早报 (即时全球)", "url": f"{RSSHUB_BASE}/zaobao/realtime/world", "limit": 20},
        {"name": "华尔街日报世界新闻 (WSJ)", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml", "limit": 15},
        {"name": "纽约时报世界新闻 (NYT)", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "limit": 15},
        {"name": "华盛顿邮报世界新闻 (WaPo)", "url": "https://feeds.washingtonpost.com/rss/world", "limit": 15}
    ],
    "国内新闻": [
        {"name": "新闻联播文字版 (CCTV)", "url": f"{RSSHUB_BASE}/cctv/xwlb", "limit": 3},
        {"name": "联合早报 (即时中港台)", "url": f"{RSSHUB_BASE}/zaobao/realtime/china", "limit": 20},
        {"name": "澎湃新闻首页面精选 (The Paper)", "url": f"{RSSHUB_BASE}/thepaper/featured", "limit": 15},
        {"name": "南华早报中国新闻 (SCMP China)", "url": "https://www.scmp.com/rss/96/feed", "limit": 15},
        {"name": "新华社新闻 (Xinhua)", "url": "https://plink.anyfeeder.com/newscn/whxw"}
    ],
    "商业财经": [
        {"name": "华尔街见闻实时快讯 (WSJCN Live)", "url": f"{RSSHUB_BASE}/wallstreetcn/live/global/1", "limit": 50},
        {"name": "财新网最新 (Caixin)", "url": f"{RSSHUB_BASE}/caixin/latest", "limit": 15}
    ],
    "AI科技": [
        {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "limit": 10},
        {"name": "量子位 (QbitAI)", "url": f"{RSSHUB_BASE}/qbitai/category/%E8%B5%84%E8%AE%AF", "limit": 15},
        {"name": "机器之心 (Synced)", "url": "https://plink.anyfeeder.com/weixin/almosthuman2014"},
        {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/", "limit": 10},
        {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "limit": 10}
    ]
}

def clean_html(raw_html):
    if not raw_html:
        return ""
    # Remove script and style tags and content
    cleanr = re.compile('<script.*?>.*?</script>|<style.*?>.*?</style>', re.DOTALL | re.IGNORECASE)
    cleantext = re.sub(cleanr, '', raw_html)
    # Remove HTML tags
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', cleantext)
    # Decode XML/HTML entities
    cleantext = html.unescape(cleantext)
    # Normalize whitespaces
    cleantext = re.sub(r'\s+', ' ', cleantext)
    # Limit length of summary
    if len(cleantext) > 300:
        cleantext = cleantext[:297] + "..."
    return cleantext.strip()

def clean_xml_entities(text):
    if not text:
        return ""
    # Strip CDATA wrapper if it exists
    if text.startswith('<![CDATA[') and text.endswith(']]>'):
        text = text[9:-3]
    return html.unescape(text)

def parse_rss_date(date_str):
    if not date_str:
        return None
    from email.utils import parsedate_to_datetime
    date_str = date_str.strip()
    
    # Try RFC 822
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
        
    # Try ISO 8601
    try:
        clean_str = date_str.replace('Z', '+00:00')
        return datetime.datetime.fromisoformat(clean_str)
    except Exception:
        pass
        
    # Try common formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S%z",
        "%a, %d %b %Y %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str, fmt)
        except Exception:
            pass
    return None

def fetch_feed(url, timeout=35):
    # Set standard User-Agent to prevent bot-detection blocking
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2'
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"  [ERROR] Failed to fetch {url}: {e}")
        return None

def parse_feed_data(xml_data):
    if not xml_data:
        return []
    
    # Clean up encoding issues if any
    # requests automatically detects encoding, but here we parse raw bytes using ElementTree
    # which can handle encoding declaration in XML itself if passed as bytes.
    items = []
    try:
        root = ET.fromstring(xml_data)
        
        # Check if RSS (has channel element)
        channel = root.find('.//{*}channel')
        if channel is not None:
            for item_node in root.findall('.//{*}item'):
                title_node = item_node.find('{*}title')
                link_node = item_node.find('{*}link')
                desc_node = item_node.find('{*}description')
                date_node = item_node.find('{*}pubDate')
                if date_node is None:
                    date_node = item_node.find('{*}date')
                
                title = title_node.text if title_node is not None else ""
                link = link_node.text if link_node is not None else ""
                desc = desc_node.text if desc_node is not None else ""
                date = date_node.text if date_node is not None else ""
                
                # Check for CDATA and clean up
                title = clean_xml_entities(title)
                desc = clean_xml_entities(desc)
                
                items.append({
                    'title': title.strip(),
                    'link': link.strip(),
                    'description': clean_html(desc),
                    'pubDate': date.strip()
                })
        # Check if Atom
        else:
            for entry_node in root.findall('.//{*}entry'):
                title_node = entry_node.find('{*}title')
                link_node = entry_node.find('{*}link')
                desc_node = entry_node.find('{*}summary')
                if desc_node is None:
                    desc_node = entry_node.find('{*}content')
                date_node = entry_node.find('{*}updated')
                if date_node is None:
                    date_node = entry_node.find('{*}published')
                
                title = title_node.text if title_node is not None else ""
                
                link = ""
                if link_node is not None:
                    link = link_node.attrib.get('href', '')
                    if not link:
                        link = link_node.text or ""
                        
                desc = desc_node.text if desc_node is not None else ""
                date = date_node.text if date_node is not None else ""
                
                title = clean_xml_entities(title)
                desc = clean_xml_entities(desc)
                
                items.append({
                    'title': title.strip(),
                    'link': link.strip(),
                    'description': clean_html(desc),
                    'pubDate': date.strip()
                })
    except Exception as e:
        print(f"  [WARNING] XML Parsing failed, attempting regex extraction: {e}")
        # Fallback to Regex parsing in case XML is malformed
        try:
            xml_str = xml_data.decode('utf-8', errors='replace')
        except Exception:
            xml_str = xml_data.decode('gbk', errors='replace')
            
        item_matches = re.findall(r'<item>(.*?)</item>', xml_str, re.DOTALL)
        if item_matches:
            for item_content in item_matches:
                title = re.search(r'<title>(.*?)</title>', item_content, re.DOTALL)
                link = re.search(r'<link>(.*?)</link>', item_content, re.DOTALL)
                desc = re.search(r'<description>(.*?)</description>', item_content, re.DOTALL)
                date = re.search(r'<pubDate>(.*?)</pubDate>', item_content, re.DOTALL)
                
                title_text = clean_xml_entities(title.group(1)) if title else ""
                link_text = clean_xml_entities(link.group(1)) if link else ""
                desc_text = clean_xml_entities(desc.group(1)) if desc else ""
                date_text = clean_xml_entities(date.group(1)) if date else ""
                
                items.append({
                    'title': clean_html(title_text).strip(),
                    'link': link_text.strip(),
                    'description': clean_html(desc_text).strip(),
                    'pubDate': date_text.strip()
                })
                
    return items

def main():
    import sys
    target_date_str = None
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        # Check if argument is YYYY-MM-DD format
        if re.match(r'^\d{4}-\d{2}-\d{2}$', arg):
            target_date_str = arg

    if target_date_str:
        print(f"Starting news aggregation for target date: {target_date_str}...")
        # Parse the target date
        target_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()
    else:
        print(f"Starting news aggregation at {datetime.datetime.now().isoformat()} (last 24 hours)...")
        now = datetime.datetime.now(datetime.timezone.utc)

    scraped_data = {}
    
    for category, sources in FEEDS.items():
        print(f"\nCategory: {category}")
        scraped_data[category] = []
        
        for source in sources:
            name = source["name"]
            url = source["url"]
            print(f" - Fetching {name}...")
            
            raw_xml = fetch_feed(url)
            articles = parse_feed_data(raw_xml)
            
            # Heuristic filter to remove blog/fluff content
            filtered_articles = []
            blacklist = ["选购", "评测", "体验", "图赏", "优惠", "怎么玩", "音乐推荐", "壁纸", "家庭饮品"]
            for art in articles:
                title_lower = art["title"].lower()
                is_blacklisted = False
                for word in blacklist:
                    if word in title_lower:
                        is_blacklisted = True
                        break
                if not is_blacklisted:
                    filtered_articles.append(art)
            
            # Filter logic
            todays_articles = []
            
            for art in filtered_articles:
                pub_date_str = art.get("pubDate")
                pub_dt = parse_rss_date(pub_date_str)
                if pub_dt:
                    # Make aware if naive
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=datetime.timezone.utc)
                    else:
                        pub_dt = pub_dt.astimezone(datetime.timezone.utc)
                    
                    if target_date_str:
                        # For a specific target date, check if publication date matches target_date in Beijing time (UTC+8)
                        tz_bj = datetime.timezone(datetime.timedelta(hours=8))
                        pub_dt_bj = pub_dt.astimezone(tz_bj)
                        if pub_dt_bj.date() == target_date:
                            todays_articles.append(art)
                    else:
                        # Past 24 hours
                        time_diff = now - pub_dt
                        if -3600 <= time_diff.total_seconds() <= 24 * 3600:
                            todays_articles.append(art)
                else:
                    # If date parsing fails and we are filtering past 24 hours, keep it.
                    # But if we are filtering a specific date, we don't know, so we skip it to prevent bleed.
                    if not target_date_str:
                        todays_articles.append(art)
            
            # Fallback: if filter yields 0 articles but we had articles, keep the most recent one
            if not todays_articles and filtered_articles:
                todays_articles = [filtered_articles[0]]
                
            print(f"   Success: found {len(articles)} articles (filtered to {len(filtered_articles)}), keeping {len(todays_articles)} updated.")
            
            scraped_data[category].append({
                "source": name,
                "url": url,
                "articles": todays_articles
            })
            
    # Save the data to utils/scratch/raw_news-YYYY-MM-DD.json
    output_dir = "utils/scratch"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"\nCreated directory: {output_dir}")
        
    date_str = target_date_str if target_date_str else datetime.datetime.now().strftime("%Y-%m-%d")
    output_path = os.path.join(output_dir, f"raw_news-{date_str}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(scraped_data, f, ensure_ascii=False, indent=2)
        
    print(f"\n[SUCCESS] Aggregated news successfully saved to {output_path}!")

if __name__ == "__main__":
    main()
