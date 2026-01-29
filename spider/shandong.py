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
    def __init__(self, use_proxy=True):
        self.list_url = "http://www.ccgp-shandong.gov.cn:8087/api/website/site/getListByCode"
        self.detail_url = "http://www.ccgp-shandong.gov.cn:8087/api/website/site/getDetail"
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        ]
        self.colCode = "2500" # 政采意向
        
        self.use_proxy = use_proxy
        self.proxies = None
        if self.use_proxy:
            self.proxies = {
                "http": "http://127.0.0.1:7897",
                "https": "http://127.0.0.1:7897",
            }
        
        self.log_func = None
        
        # 仅在启用代理时检查状态
        if self.use_proxy:
            self.check_proxy()
        else:
            self._log("="*50)
            self._log("⚠️ 代理已禁用，将使用本地直接连接。")
            self._log("="*50)

    def check_proxy(self):
        """检查代理是否生效并获取出口IP位置"""
        self._log("="*50)
        self._log("正在检查网络出口环境...")
        test_url = "http://ip-api.com/json?lang=zh-CN"
        proxies = self.proxies
        
        try:
            # 1. 获取代理出口信息
            resp = requests.get(test_url, proxies=proxies, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                ip = data.get("query")
                country = data.get("country", "")
                region = data.get("regionName", "")
                city = data.get("city", "")
                isp = data.get("isp", "")
                
                self._log(f"✅ 代理已生效！")
                self._log(f"   当前探测出口 IP: {ip}")
                self._log(f"   物理地理位置: {country} - {region} - {city}")
                self._log(f"   运营商信息: {isp}")
            else:
                self._log(f"⚠️ 代理连接测试返回状态码: {resp.status_code}")
        except Exception as e:
            self._log(f"❌ 代理连接失败！请检查 Clash (127.0.0.1:7897) 是否开启。")
            self._log(f"   错误详情: {e}")
        
        self._log("="*50)

    def _log(self, msg):
        if self.log_func:
            self.log_func(msg)
        else:
            print(msg)

    def get_headers(self):
        return {
            "accept": "application/json, text/plain, */*",
            # "accept-encoding": "gzip, deflate", # requests usually handles this
            "accept-language": "zh-CN,zh;q=0.9",
            "connection": "keep-alive",
            "content-type": "application/json;charset=UTF-8",
            "host": "www.ccgp-shandong.gov.cn:8087",
            "origin": "http://www.ccgp-shandong.gov.cn",
            "referer": "http://www.ccgp-shandong.gov.cn/",
            "user-agent": random.choice(self.user_agents)
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
            self._log(f"正在请求列表页: 第 {page} 页 (地区: {area}, 搜索词: {title})")
            # 强化反爬：列表页请求间隔 3.0 - 6.0 秒
            time.sleep(random.uniform(3.0, 6.0))
            
            resp = requests.post(self.list_url, json=data, headers=self.get_headers(), timeout=20, proxies=self.proxies)
            
            # 状态码监控
            if resp.status_code in [403, 429]:
                self._log("🔥 警告: 触发服务器拦截 (403/429)，立即停止爬取以保护 IP！")
                return [], -1
            elif resp.status_code >= 500:
                self._log(f"🔥 警告: 目标服务器过载或出错 (错误码: {resp.status_code})，停止爬取，避免加重负担！")
                return [], -1
                
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
            # 强化反爬：详情页请求间隔 2.0 - 5.0 秒
            time.sleep(random.uniform(2.0, 5.0))
            resp = requests.get(self.detail_url, params=params, headers=self.get_headers(), timeout=20, proxies=self.proxies)
            
            if resp.status_code in [403, 429]:
                self._log(f"🔥 详情页 {id_val} 触发拦截，跳过...")
                return None
                
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
        
        # 降低并发：max_workers 从 5 降至 2
        if records:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(self.process_item, rec) for rec in records]
                for f in futures:
                    res = f.result()
                    if res: all_data.extend(res)
        
        # 处理后续页面
        for p in range(2, pages_to_crawl + 1):
            self._log(f"--- 准备翻阅第 {p} 页 ---")
            # 页际长休眠：3.0 - 8.0 秒
            time.sleep(random.uniform(3.0, 8.0))
            
            records, total = self.get_list(p, title, start_time, end_time, area)
            if total == -1: break # 触发熔断
            
            if records:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(self.process_item, rec) for rec in records]
                    for f in futures:
                        res = f.result()
                        if res: all_data.extend(res)
            
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
