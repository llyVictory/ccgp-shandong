import requests
import json
import base64
import time
from bs4 import BeautifulSoup
import pandas as pd
import threading
from concurrent.futures import ThreadPoolExecutor

import random

class Shandong(object):
    def __init__(self):
        self.list_url = "http://www.ccgp-shandong.gov.cn:8087/api/website/site/getListByCode"
        self.detail_url = "http://www.ccgp-shandong.gov.cn:8087/api/website/site/getDetail"
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        ]
        self.colCode = "2500" # 政采意向
        # Clash 默认代理配置 (127.0.0.1:7890)
        # 如果需要关闭代理，将 self.proxies 设为 None
        # self.proxies = {
        #     "http": "http://127.0.0.1:7897",
        #     "https": "http://127.0.0.1:7897",
        # }
        self.log_func = None

    def _log(self, msg):
        if self.log_func:
            self.log_func(msg)
        else:
            print(msg)

    def get_headers(self):
        return {
            "Content-Type": "application/json;charset=utf-8",
            "User-Agent": random.choice(self.user_agents),
            "Referer": "http://www.ccgp-shandong.gov.cn/xxgk"
        }
    def get_list(self, page, title="", start_time="", end_time="", area="370000"):
        # Date format must be YYYY-MM-DD HH:mm:ss
        if start_time and len(start_time) == 10:
            start_time += " 00:00:00"
        if end_time and len(end_time) == 10:
            end_time += " 23:59:59"
            
        data = {
            "colCode": self.colCode,
            "area": area,
            "currentPage": page,
            "pageSize": 10,
            "title": title,
            "projectCode": "",
            "buyKind": "",
            "buyType": "",
            "startTime": start_time if start_time else "",
            "oldData": 0,
            "endTime": end_time if end_time else "",
            "homePage": 0,
            "mergeType": 0
        }
        try:
            self._log(f"Requesting List: {self.list_url} (Page {page}, Area {area}, Range {start_time}~{end_time})")
            # Rate limiting: random sleep between 1.5 to 3.5 seconds
            time.sleep(random.uniform(1.5, 3.5))
            resp = requests.post(self.list_url, json=data, headers=self.get_headers(), timeout=15, proxies=self.proxies)
            if resp.status_code == 200:
                j = resp.json()
                # Assuming structure: j['data']['data']['records'] based on investigation
                # But test_api.py output showed j['data']['data'] has 'records'
                # Let's handle both just in case or stick to what we saw.
                if j.get("data") and j["data"].get("data") and j["data"]["data"].get("records"):
                    return j["data"]["data"]["records"], j["data"]["data"].get("pages", 0)
                else:
                    self._log("Debug - API JSON structure: " + json.dumps(j, indent=2, ensure_ascii=False))
            else:
                self._log(f"List error page {page}, status {resp.status_code}: {resp.text}")
        except Exception as e:
            self._log(f"List exception page {page}: {e}")
        return [], 0

    def get_detail_html(self, id_val, colCode):
        params = {
            "id": id_val,
            "colCode": colCode,
            "oldData": 0
        }
        try:
            # Rate limiting for detail pages as well
            time.sleep(random.uniform(1.0, 2.5))
            resp = requests.get(self.detail_url, params=params, headers=self.get_headers(), timeout=15, proxies=self.proxies)
            if resp.status_code == 200:
                j = resp.json()
                if j.get("data") and j["data"].get("data") and j["data"]["data"].get("body"):
                    body = j["data"]["data"]["body"]
                    try:
                        return base64.b64decode(body).decode('utf-8')
                    except:
                        try:
                            return base64.b64decode(body).decode('gb18030')
                        except:
                            return None
        except Exception as e:
            self._log(f"Detail exception {id_val}: {e}")
        return None

    def parse_html_table(self, html):
        if not html:
            return []
        soup = BeautifulSoup(html, 'lxml')
        tables = soup.find_all('table')
        results = []
        for table in tables:
            # Check headers
            rows = table.find_all('tr')
            if not rows:
                continue
            
            headers = [th.get_text(strip=True) for th in rows[0].find_all(['td', 'th'])]
            # Looking for headers like "项目名称", "金额", "时间"
            # Typical headers: 序号, 项目名称, 采购需求概况, 预算金额(万元), 预计采购时间, 备注
            name_idx = -1
            amt_idx = -1
            time_idx = -1
            
            for i, h in enumerate(headers):
                if "项目名称" in h:
                    name_idx = i
                elif "金额" in h or "预算" in h:
                    amt_idx = i
                elif "时间" in h:
                    time_idx = i
            
            if name_idx != -1:
                # Valid table
                for row in rows[1:]:
                    cols = row.find_all('td')
                    if len(cols) > max(name_idx, amt_idx, time_idx):
                        item = {}
                        item['project_name'] = cols[name_idx].get_text(strip=True)
                        item['amount'] = cols[amt_idx].get_text(strip=True) if amt_idx != -1 else ""
                        item['est_time'] = cols[time_idx].get_text(strip=True) if time_idx != -1 else ""
                        results.append(item)
        return results

    def process_item(self, record):
        # record has id, title, userName (client name), areaName (city), date, colCode
        full_link = f"http://www.ccgp-shandong.gov.cn/detail?id={record['id']}&colCode={record['colCode']}&oldData={record['oldData']}"
        self._log(f"[{record.get('areaName', '未知')}] 正在爬取详情: {record.get('title', '无标题')}")
        self._log(f"   URL: {full_link}")
        
        html = self.get_detail_html(record['id'], record['colCode'])
        projects = self.parse_html_table(html)
        
        final_rows = []
        if projects:
            for i, p in enumerate(projects):
                row = {
                    "序号": i + 1, # relative to list, or just global? User example "1"
                    "分类1": "",
                    "分类2": "政采意向",
                    "地市": record.get("areaName", ""),
                    "客户名称": record.get("userName", ""),
                    "项目名称": p['project_name'],
                    "金额": p['amount'],
                    "预计时间": p['est_time'],
                    "link": full_link
                }
                final_rows.append(row)
        else:
            # If no table found, maybe correct logic is different or it's a unstructured text.
            # Fallback: use title as project name?
            row = {
                "序号": 1,
                "分类1": "",
                "分类2": "政采意向",
                "地市": record.get("areaName", ""),
                "客户名称": record.get("userName", ""),
                "项目名称": record.get("title", ""),
                "金额": "",
                "预计时间": "",
                "link": full_link
            }
            final_rows.append(row)
        return final_rows

    def run(self, max_pages=5, title="", start_time="", end_time="", area="370000"):
        all_data = []
        # First get total pages
        records, total_pages = self.get_list(1, title, start_time, end_time, area)
        self._log(f"Total pages available: {total_pages}, Processing max: {max_pages}")
        
        pages_to_crawl = min(total_pages, max_pages)
        if pages_to_crawl == 0 and len(records) > 0:
             # Case where total_pages might be 0 but data exists? 
             # Usually pages >= 1 if records > 0
             pages_to_crawl = 1
        
        # Process page 1
        if records:
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(self.process_item, rec) for rec in records]
                for f in futures:
                    all_data.extend(f.result())
        
        # Process other pages
        for p in range(2, pages_to_crawl + 1):
            self._log(f"Processing page {p}...")
            records, _ = self.get_list(p, title, start_time, end_time, area)
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(self.process_item, rec) for rec in records]
                for f in futures:
                    all_data.extend(f.result())
            time.sleep(1) # Be nice
            
        return all_data

if __name__ == "__main__":
    s = Shandong()
    data = s.run(max_pages=2) # Test run
    df = pd.DataFrame(data)
    # Reorder columns
    cols = ["序号", "分类1", "分类2", "地市", "客户名称", "项目名称", "金额", "预计时间", "link"]
    # Adjust 序号 to be global
    df['序号'] = range(1, len(df) + 1)
    df = df[cols]
    print(df.head())
    df.to_excel("shandong_bid.xlsx", index=False)
    print("Saved to shandong_bid.xlsx")
