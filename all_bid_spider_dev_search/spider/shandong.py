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
        self.browser = None
        
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

    def run(self, max_pages=1, start_page=1, title="", start_time="", end_time="", area="370000", keywords=None):
        from spider.browser_engine import BrowserEngine
        import os
        
        all_data = []
        self.browser = BrowserEngine(headless=False)
        self.browser.logger = self.log_func
        
        try:
            self.browser.init_driver()
            
            # 2. 爬取控制
            if keywords is None:
                keywords = ["大学", "学校", "学院", "教育厅", "教育电视台", "教育招生考试院", "电教馆", "电化教育馆"]
            self._log(f"当前任务设定 ({start_time}模式): 启用核心词组模糊匹配策略 {keywords}")

            # 解析要抓取的区域
            target_areas = []
            if isinstance(area, list):
                target_areas = area
            elif isinstance(area, str) and "," in area:
                target_areas = area.split(",")
            else:
                target_areas = [area]

            search_configs = []
            if "370000" in target_areas:
                search_configs.append({"area": "370000", "desc": "省级"})
            if "CITY_COUNTY_ALL" in target_areas:
                search_configs.append({"area": "CITY_COUNTY_ALL", "desc": "市区县-全部"})
            
            # 兜底：如果都没选，按全选处理
            if not search_configs:
                search_configs = [
                    {"area": "370000", "desc": "省级"},
                    {"area": "CITY_COUNTY_ALL", "desc": "市区县-全部"}
                ]
            
            raw_collected_count = 0

            for config in search_configs:
                # 区域级 ID 去重：确保同一区域内不同关键词搜到重复内容时去重
                # 但不同区域（如省级、区县）之间不互相去重，取并集保留
                seen_ids = set() 
                
                for kw in keywords:
                    self._log(f"=== 抓取开始: 区域=[{config['desc']}] 关键词=[{kw if kw else '空'}] ===")
                    
                    self.browser.goto_search_page()
                    search_success = self.browser.perform_search(title=kw, start_time=start_time, end_time=end_time, area=config["area"])
                    
                    if not search_success and not self.browser.is_no_data_visible():
                        self._log("❌ 搜索执行异常且未确认无数据。")
                        self._log("❌ 为保证数据完整度，将立刻强行终止整个抓取任务！")
                        raise RuntimeError("关键搜索执行失败，放弃本次完整抓取任务。")
                        
                    current_page_idx = 1
                    while current_page_idx <= max_pages:
                        self._log(f"--- 抓取翻页: 第 {current_page_idx} 页 ---")
                        
                        records = self.browser.extract_records()
                        if not records:
                            if self.browser.is_no_data_visible():
                                self._log("页面提示暂无数据，此搜索结束。")
                                break
                            else:
                                self._log("未检测到记录，可能加载失败，跳过。")
                                break
                        
                        for rec in records:
                            rec_id = rec.get('id')
                            if rec_id in seen_ids:
                                continue 
                                
                            details = self.process_item(rec)
                            for detail in details:
                                all_data.append(detail)
                            
                            seen_ids.add(rec_id)
                            raw_collected_count += 1
                        
                        if not self.browser.next_page() or current_page_idx >= max_pages:
                            break
                        current_page_idx += 1
                    
                    # 使用配置的关键词/区域切换间隔
                    wait_min = int(os.getenv("WAIT_CRAWL_INTERVAL_MIN", "3"))
                    wait_max = int(os.getenv("WAIT_CRAWL_INTERVAL_MAX", "6"))
                    time.sleep(random.uniform(wait_min, wait_max))
                
            self._log(f"抓取结束。原始扫描: {raw_collected_count} 条，获取数据: {len(all_data)} 条。")
                    
        except RuntimeError as re:
            # 捕获我们自己主动抛出的阻断性异常（如连续5次验证码失败）
            self._log(f"🚨 严重错误中断: {re}")
            # 必须清空所有已抓取的数据，强制生成一份全空只有表头的文件
            self._log("🗑️ 已清空当前抓取的所有部分数据，确保只产生空表头。")
            all_data = []
        except Exception as e:
            self._log(f"爬虫运行异常: {e}")
            # 如果是意外报错，原逻辑不变，依然保留已抓取的数据并退出循环
        finally:
            if self.browser:
                self._log("任务结束，关闭浏览器...")
                self.browser.close()
                self.browser = None
            
        return all_data

if __name__ == "__main__":
    s = Shandong()
    # 测试运行前 2 页（空关键词模式）
    data = s.run(max_pages=2, start_time="0") 
    df = pd.DataFrame(data)
    if not df.empty:
        # 统一 Project C 的列名
        cols = [
            "序号", "地区", "标题", "发布时间", "发布人",
            "子序号", "采购项目名称", "采购需求概况", "预算金额(万元)",
            "拟面向中小企业预留", "预计采购时间", "备注", "意向发布地址"
        ]
        # 补齐可能缺失的列
        for col in cols:
            if col not in df.columns:
                df[col] = ""
        
        df['序号'] = range(1, len(df) + 1)
        df = df[cols]
        print(df.head())
        df.to_excel("shandong_bid_C_test.xlsx", index=False)
        print("测试数据已保存到 shandong_bid_C_test.xlsx")
    else:
        print("未抓取到任何符合目标的数据。")
        # 即使无数据，也按要求生成空 Excel 并在第一个格子写入“无数据”
        cols = [
            "序号", "地区", "标题", "发布时间", "发布人",
            "子序号", "采购项目名称", "采购需求概况", "预算金额(万元)",
            "拟面向中小企业预留", "预计采购时间", "备注", "意向发布地址"
        ]
        df = pd.DataFrame(columns=cols)
        empty_row = {col: "" for col in cols}
        empty_row[cols[0]] = "无数据"
        df = pd.DataFrame([empty_row])
        df.to_excel("shandong_bid_C_test.xlsx", index=False)
        print("已生成包含‘无数据’标记的空 Excel 文件: shandong_bid_C_test.xlsx")
