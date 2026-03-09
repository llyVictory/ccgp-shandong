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
    def __init__(self, use_proxy=False):
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
            # 严格反爬：列表页请求前随机休眠 2-5 秒
            time.sleep(random.uniform(2.0, 5.0))
            
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
            # 严格反爬：详情页请求前随机休眠 2-5 秒
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
        """
        [V3.1] 终极解析方案：自动纠错与去重 (Fixed)
        1. 必须包含 '序号' 列才视为有效清单表。
        2. 使用 recursive=False 并支持 tbody 查找。
        3. 智能列偏移校正：检测到“序号”列由长文本占据时，自动触发 Left-Shift 修正。
        4. 全局去重：防止同一项目被多次提取。
        """
        if not html:
            return []
        soup = BeautifulSoup(html, 'lxml')
        tables = soup.find_all('table')
        results = []
        seen_titles = set()
        
        self._log(f"Debug: Found {len(tables)} tables")
        
        for table_idx, table in enumerate(tables):
            # 优先查找直接子节点 tr，若无则查找 tbody 下的 tr
            rows = table.find_all('tr', recursive=False)
            if len(rows) < 2: 
                tbody = table.find('tbody', recursive=False)
                if tbody:
                    rows = tbody.find_all('tr', recursive=False)
            
            if len(rows) < 2: 
                continue
            
            # 1. 精确寻找表头行
            header_row_idx = -1
            col_map = {
                "sub_index": -1, "project_name": -1, "desc": -1, 
                "amount": -1, "sme_reserve": -1, "est_time": -1, "remark": -1
            }
            
            # 搜索前 6 行寻找表头
            for idx, tr in enumerate(rows[:6]):
                cells = tr.find_all(['td', 'th'], recursive=False)
                headers = [c.get_text(strip=True) for c in cells]
                
                temp_map = {k: -1 for k in col_map}
                for i, h in enumerate(headers):
                    if "序号" in h: temp_map["sub_index"] = i
                    elif "名称" in h: temp_map["project_name"] = i
                    elif "概况" in h or "需求" in h: temp_map["desc"] = i
                    elif "金额" in h: temp_map["amount"] = i
                    elif "中小企业" in h: temp_map["sme_reserve"] = i
                    elif "时间" in h: temp_map["est_time"] = i
                    elif "备注" in h: temp_map["remark"] = i
                
                # 严格标准：必须找到“序号”和“项目名称”才视为有效表头
                if temp_map["sub_index"] != -1 and temp_map["project_name"] != -1:
                    header_row_idx = idx
                    col_map = temp_map
                    break
            
            if header_row_idx == -1:
                continue

            # 2. 从表头下一行开始遍历数据
            for row in rows[header_row_idx+1:]:
                cols = row.find_all(['td', 'th'], recursive=False)
                if len(cols) < 2: continue
                
                def get_clean_text(idx):
                    if idx != -1 and idx < len(cols):
                        txt = cols[idx].get_text(" ", strip=True) # 使用空格连接标签内容
                        txt = txt.replace("\n", " ").replace("\r", " ").replace("\t", " ")
                        while "  " in txt: 
                            txt = txt.replace("  ", " ")
                        return txt.strip()
                    return ""

                # 提取原始数据
                raw_idx_val = get_clean_text(col_map["sub_index"])
                raw_name_val = get_clean_text(col_map["project_name"])
                
                # 3. 智能错位修正 (Data Shift Correction)
                is_shifted = False
                # 如果序号列内容长度超过5且不是纯数字，极有可能是项目名称挤占了序号列
                if len(raw_idx_val) > 5 and not raw_idx_val.isdigit():
                    is_shifted = True
                
                item = {}
                if is_shifted:
                    # 错位处理：物理列重映射
                    # 假定物理顺序列：[Name, Desc, Amount, SME, Time, Remark] (Index丢失)
                    # 强制按物理顺序读取
                    phy_cols = [c.get_text(" ", strip=True).replace("\n","").replace("\r","").strip() for c in cols]
                    # 清洗物理列中的多余空格
                    phy_cols = [" ".join(p.split()) for p in phy_cols]
                    while len(phy_cols) < 7: phy_cols.append("")
                    
                    item = {
                        "子序号": "", 
                        "采购项目名称": phy_cols[0],
                        "采购需求概况": phy_cols[1],
                        "预算金额(万元)": phy_cols[2],
                        "拟面向中小企业预留": phy_cols[3],
                        "预计采购时间": phy_cols[4],
                        "备注": phy_cols[5] if len(phy_cols)>5 else ""
                    }
                else:
                    # 正常映射
                    item = {
                        "子序号": raw_idx_val,
                        "采购项目名称": raw_name_val,
                        "采购需求概况": get_clean_text(col_map["desc"]),
                        "预算金额(万元)": get_clean_text(col_map["amount"]),
                        "拟面向中小企业预留": get_clean_text(col_map["sme_reserve"]),
                        "预计采购时间": get_clean_text(col_map["est_time"]),
                        "备注": get_clean_text(col_map["remark"])
                    }

                # 4. 有效性校验
                if not item["采购项目名称"] or item["采购项目名称"] in ["采购项目名称", "项目名称", "名称"]:
                    continue
                
                # 5. 全局去重 (使用 项目名称+金额 作为指纹)
                unique_key = item["采购项目名称"] + item["预算金额(万元)"]
                if unique_key in seen_titles:
                    continue
                seen_titles.add(unique_key)

                results.append(item)
                    
        return results

    def process_item(self, record):
        # record 包含列表页字段: id, title, userName, areaName, date, buyKindCode...
        full_link = f"http://www.ccgp-shandong.gov.cn/detail?id={record['id']}&colCode={record['colCode']}&oldData={record['oldData']}"
        self._log(f"[{record.get('areaName', '未知')}] 解析中: {record.get('title', '无标题')}")
        
        html = self.get_detail_html(record['id'], record['colCode'])
        child_rows = self.parse_html_table(html)
        
        final_rows = []
        
        # 基础父级字段 (Parent Fields)
        parent_info = {
            "地区": record.get("areaName", ""),
            "标题": record.get("title", ""),
            "发布具体时间": record.get("publishDatetime", ""),  # 精确到秒的发布时间
            "发布人": record.get("publisher", ""),  # 从详情页提取的发布人
            # "采购方式": record.get("buyKindCode", ""),  # 官方数据为空，已注释
            # "项目类型": record.get("projectType", ""),  # 官方数据为空，已注释
            "发布时间": record.get("date", ""),
            "意向发布地址": full_link
        }

        if child_rows:
            # 有详情页表格数据：One Parent -> Many Children
            for child in child_rows:
                row = parent_info.copy()
                row.update(child) # 合并子字段
                final_rows.append(row)
        else:
            # 无详情页表格数据：One Parent -> Empty Child (保留一行)
            row = parent_info.copy()
            # 填充空的子字段
            row.update({
                "子序号": "1",
                "采购项目名称": record.get("title", ""), # 兜底：用大标题
                "采购需求概况": "详情页未解析到表格",
                "预算金额(万元)": "",
                "拟面向中小企业预留": "",
                "预计采购时间": "",
                "备注": ""
            })
            final_rows.append(row)
            
        return final_rows

    def run(self, max_pages=1, start_page=1, title="", start_time="", end_time="", area="370000"):
        from spider.browser_engine import BrowserEngine
        
        all_data = []
        self.browser = BrowserEngine(headless=False) # GUI 模式以便通过验证码
        self.browser.logger = self.log_func # 传递日志函数
        
        try:
            self.browser.init_driver()
            
            # 1. 导航并搜索
            self.browser.goto_search_page()
            self.browser.perform_search(title, start_time, end_time, area)
            
            # 2. 如果起始页不是1，跳转
            if start_page > 1:
                success = self.browser.jump_to_page(start_page)
                if not success:
                    self._log(f"跳转到第 {start_page} 页失败，将从当前页开始")
            
            # 3. 循环爬取
            pages_crawled = 0
            current_page_idx = start_page
            
            while pages_crawled < max_pages:
                self._log(f"--- 正在处理第 {current_page_idx} 页 ---")
                
                # 提取列表 (无限重试机制：空白数据一定是验证码问题)
                records = self.browser.extract_records()
                
                rescue_attempts = 0
                max_rescue_attempts = 5  # ✅ 最多重试5次验证码,避免无限循环
                
                while not records and rescue_attempts < max_rescue_attempts:
                    rescue_attempts += 1
                    self._log(f"第 {current_page_idx} 页未检测到数据，执行验证码重试 (第 {rescue_attempts} 次)...")
                    
                    # 重新执行全量搜索逻辑 (Tab -> 参数 -> 刷新验证码 -> 识别 -> 查询)
                    self.browser.perform_search(title, start_time, end_time, area)
                    
                    # 检查当前页码，只有不在目标页时才跳转
                    current_page_in_browser = self.browser.get_current_page()
                    if current_page_in_browser != current_page_idx:
                        self._log(f"当前页码 {current_page_in_browser}，需要跳转到第 {current_page_idx} 页...")
                        self.browser.jump_to_page(current_page_idx)
                    else:
                        self._log(f"当前已在第 {current_page_idx} 页，无需跳转")
                    
                    # 再次尝试提取
                    records = self.browser.extract_records()
                
                if not records:
                    self._log(f"⚠️ 已重试 {max_rescue_attempts} 次验证码仍无数据")
                    
                    # 🔥 关键优化：第一页无数据直接退出,认为今日无数据
                    if current_page_idx == start_page:
                        self._log(f"✅ 第一页在 {max_rescue_attempts} 次重试后仍无数据，判定为今日无数据，停止爬取")
                        break
                    
                    # 非第一页则跳过继续
                    self._log(f"跳过第 {current_page_idx} 页，继续下一页")
                    pages_crawled += 1
                    current_page_idx += 1
                    if not self.browser.next_page():
                        self._log("无法点击下一页，停止爬取")
                        break
                    continue
                
                # 详情页处理 (保持并发)
                # 注意：BrowserEngine 已经提取了 ID，我们继续用 requests 并发获取详情
                # 为了保持 session 状态 (Cookies)，我们可以尝试让 requests 使用 browser 的 cookies
                # 但目前详情页 API 似乎不需要 cookie 或者不敏感？
                # 如果需要，可以: s = requests.Session(); s.cookies.update(...)
                
                if records:
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        futures = [executor.submit(self.process_item, rec) for rec in records]
                        for f in futures:
                            res = f.result()
                            if res: all_data.extend(res)
                
                pages_crawled += 1
                if pages_crawled >= max_pages:
                    break
                
                # 翻页
                if not self.browser.next_page():
                    self._log("无法点击下一页，停止爬取")
                    break
                    
                current_page_idx += 1
                
        except Exception as e:
            self._log(f"爬虫运行异常: {e}")
        finally:
            if self.browser:
                self._log("任务结束，5秒后自动关闭浏览器...")
                time.sleep(5)
                self.browser.close()
                self.browser = None
                self._log("✅ 浏览器已关闭")
            
        return all_data

if __name__ == "__main__":
    s = Shandong()
    data = s.run(max_pages=2) # Test run
    df = pd.DataFrame(data)
    # Reorder columns
    cols = ["序号", "分类1", "分类2", "地市", "客户名称", "项目名称", "金额", "预计时间", "意向发布地址"]
    # Adjust 序号 to be global
    df['序号'] = range(1, len(df) + 1)
    df = df[cols]
    print(df.head())
    df.to_excel("shandong_bid.xlsx", index=False)
    print("Saved to shandong_bid.xlsx")
