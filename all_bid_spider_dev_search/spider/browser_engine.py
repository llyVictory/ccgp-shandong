import time
import os
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import ddddocr
from PIL import Image
import io
import re
import random

# 加载 .env 配置
from dotenv import load_dotenv
load_dotenv()

class BrowserEngine:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        self.logger = None
        
        # 加载停留时间参数
        self.wait_next_page = (int(os.getenv("WAIT_NEXT_PAGE_MIN", "2")), int(os.getenv("WAIT_NEXT_PAGE_MAX", "4")))
        self.wait_detail_page = (int(os.getenv("WAIT_DETAIL_PAGE_MIN", "2")), int(os.getenv("WAIT_DETAIL_PAGE_MAX", "4")))
        self.wait_search = (int(os.getenv("WAIT_SEARCH_MIN", "2")), int(os.getenv("WAIT_SEARCH_MAX", "4")))
        self.wait_action_delay = (int(os.getenv("WAIT_ACTION_DELAY_MIN", "1")), int(os.getenv("WAIT_ACTION_DELAY_MAX", "2")))

    def _log(self, msg):
        if self.logger:
            self.logger(f"[Browser] {msg}")
        else:
            print(f"[Browser] {msg}")

    def _sleep_random(self, range_tuple):
        """执行随机等待"""
        time.sleep(random.uniform(range_tuple[0], range_tuple[1]))

    def init_driver(self):
        if self.driver:
            return
        
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # 从 .env 读取 Chrome 浏览器路径
        chrome_binary = os.getenv("CHROME_BINARY_PATH", "").strip()
        if chrome_binary and os.path.exists(chrome_binary):
            options.binary_location = chrome_binary
            self._log(f"使用自定义 Chrome 路径: {chrome_binary}")
        
        # 从 .env 读取 ChromeDriver 路径
        chrome_driver_path = os.getenv("CHROME_DRIVER_PATH", "").strip()
        
        self._log("正在启动 Chrome 浏览器...")
        
        if chrome_driver_path and os.path.exists(chrome_driver_path):
            # 使用手动配置的 ChromeDriver
            self._log(f"使用自定义 ChromeDriver 路径: {chrome_driver_path}")
            service = ChromeService(executable_path=chrome_driver_path)
        else:
            # 自动下载匹配版本的 ChromeDriver
            self._log("使用 webdriver-manager 自动下载 ChromeDriver...")
            service = ChromeService(ChromeDriverManager().install())
        
        self.driver = webdriver.Chrome(service=service, options=options)
        
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        
        # 从 .env 读取超时配置
        page_load_timeout = int(os.getenv("PAGE_LOAD_TIMEOUT", "60"))
        implicit_wait = int(os.getenv("IMPLICIT_WAIT_TIMEOUT", "15"))
        self.element_wait_timeout = int(os.getenv("ELEMENT_WAIT_TIMEOUT", "30"))
        
        # 设置超时
        self.driver.set_page_load_timeout(page_load_timeout)
        self.driver.implicitly_wait(implicit_wait)
        self._log(f"超时设置: 页面加载={page_load_timeout}s, 隐式等待={implicit_wait}s, 元素等待={self.element_wait_timeout}s")
        self._log("浏览器启动成功")
        
        # 网络连接测试
        try:
            self.driver.get("https://www.baidu.com")
            self._log("网络连接正常")
        except Exception as net_err:
            self._log(f"⚠️ 网络连接测试失败: {net_err}")
            self._log("请检查: 1. 网络是否连接 2. 代理是否开启 3. 防火墙设置")

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def solve_captcha(self, refresh_first=True):
        """
        检测并自动识别只有在出现验证码时才调用的逻辑
        """
        try:
            # 查找验证码图片和输入框
            # 根据 debug_html_0.html 分析
            # 图片: div.n-captcha > img
            # 输入框: input[placeholder="请输入验证码"]
            
            # 使用更宽泛的查找以免 DOM 微调失效
            captcha_imgs = self.driver.find_elements(By.CSS_SELECTOR, "div.n-captcha img")
            input_box = None
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs:
                ph = inp.get_attribute("placeholder")
                label = inp.get_attribute("aria-label")
                if (ph and "验证码" in ph) or (label and "验证码" in label):
                    input_box = inp
                    break
            
            if captcha_imgs and input_box:
                img_el = captcha_imgs[0]
                if img_el.is_displayed():
                    # 1. 点击刷新 (根据用户要求)
                    if refresh_first:
                        try:
                            refresh_btn = self.driver.find_element(By.CSS_SELECTOR, "div.n-captcha i.refresh-icon")
                            refresh_btn.click()
                            self._log("点击了验证码刷新按钮")
                            self._sleep_random(self.wait_action_delay) # 等待新图片加载
                        except Exception as e:
                            self._log(f"刷新验证码失败: {e}")

                    src = img_el.get_attribute("src")
                    if src and "blob:" in src and len(src) > 10:
                        self._log("检测到验证码，准备识别...")
                        
                        # 截图
                        screenshot = img_el.screenshot_as_png
                        img = Image.open(io.BytesIO(screenshot))
                        
                        # 识别
                        res = self.ocr.classification(img)
                        self._log(f"OCR 识别结果: {res}")
                        
                        # 填入
                        input_box.clear()
                        input_box.send_keys(res)
                        self._sleep_random(self.wait_action_delay)
                        return True
            return False
        except Exception as e:
            self._log(f"验证码处理异常（非阻断）: {e}")
        
        return False

    def goto_search_page(self):
        url = "http://www.ccgp-shandong.gov.cn/xxgk"
        self._log(f"访问页面: {url}")
        self.driver.get(url)
        # 等待加载 (使用配置的超时时间)
        timeout = getattr(self, 'element_wait_timeout', 30)
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.second-search"))
            )
            self._log("页面加载完成")
        except:
            self._log(f"页面加载超时({timeout}s)，可能网络慢或结构变更")

    def _fill_date_range(self, start_date_str, end_date_str):
        """通用私有方法：在页面中填入起止日期"""
        # 1. 尝试找到并点击"自定义"时间按钮
        try:
            all_divs = self.driver.find_elements(By.TAG_NAME, "div")
            for div in all_divs:
                try:
                    div_text = div.text.strip()
                    div_class = div.get_attribute("class") or ""
                    if "item" in div_class and ("自定义" in div_text or "自选" in div_text):
                        if "is_active" not in div_class:
                            div.click()
                            self._log("点击了'自定义'时间按钮")
                            self._sleep_random(self.wait_action_delay)
                        break
                except:
                    continue
            
            # 2. 查找日期输入框方案 A: 根据 placeholder
            date_inputs = []
            all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
            for inp in all_inputs:
                ph = inp.get_attribute("placeholder") or ""
                if "开始" in ph or "起始" in ph:
                    date_inputs.append(("start", inp))
                elif "结束" in ph or "截止" in ph:
                    date_inputs.append(("end", inp))
            
            # 方案 B: 根据 el-date-editor 类名 (Element UI)
            if len(date_inputs) < 2:
                range_inputs = self.driver.find_elements(By.CSS_SELECTOR, ".el-date-editor input, .el-range-input")
                if len(range_inputs) >= 2:
                    date_inputs = [("start", range_inputs[0]), ("end", range_inputs[1])]
            
            if len(date_inputs) >= 2:
                for dtype, inp in date_inputs:
                    target_val = start_date_str if dtype == "start" else end_date_str
                    # 使用 JS 清空并填入值，防止原生 clear()/send_keys() 触发日期面板阻碍操作
                    try:
                        self.driver.execute_script("arguments[0].value = '';", inp)
                        inp.send_keys(target_val)
                        self._log(f"已填入{'开始' if dtype=='start' else '结束'}日期: {target_val}")
                    except:
                        inp.clear()
                        inp.send_keys(target_val)
                self._sleep_random(self.wait_action_delay)
                return True
            else:
                self._log("⚠️ 未能在页面找到有效的起止日期输入框")
                return False
        except Exception as e:
            self._log(f"填充日期过程异常: {e}")
            return False

    def perform_search(self, title="", start_time="", end_time="", area="370000"):
        # 把快捷代码转成可读文本用于日志显示
        time_display_map = {
            "0": "今日", "7": "近7天", "30": "近30天",
            "180": "近半年", "365": "近一年", "1095": "近三年"
        }
        time_display = time_display_map.get(start_time, f"{start_time}~{end_time}")
        
        # 0. 切换到 '意向公开' Tab (左侧菜单第一项)
        try:
            self._log("尝试切换到 '意向公开' Tab...")
            tab_xpath = "/html/body/div[1]/div[1]/div/div/div[1]/div/ul/li[1]"
            tab_el = self.driver.find_element(By.XPATH, tab_xpath)
            class_attr = tab_el.get_attribute("class") or ""
            if "is_active" not in class_attr:
                tab_el.click()
                self._log("点击了 '意向公开' Tab")
                self._sleep_random(self.wait_action_delay)
            else:
                self._log("'意向公开' Tab 已经是激活状态")
        except Exception as e:
            self._log(f"切换 Tab 失败: {e}")

        # 1. 地区选择
        try:
            city_xpath_index = {
                "370100": 2, "370200": 3, "370300": 4, "370400": 5, "370500": 6,
                "370600": 7, "370700": 8, "370800": 9, "370900": 10, "371000": 11,
                "371100": 12, "371200": 13, "371300": 14, "371400": 15, "371500": 16,
                "371600": 17, "371700": 18,
            }
            if area == "370000":
                xpath = "/html/body/div[1]/div[1]/div/div/div[2]/div/div[2]/div[1]/div[1]/div[1]"
                el = self.driver.find_element(By.XPATH, xpath)
                if "is_active" not in (el.get_attribute("class") or ""):
                    el.click()
                    self._log("选择了: 山东省本级")
                    self._sleep_random(self.wait_action_delay)
            elif area == "CITY_COUNTY_ALL":
                tab_xpath = "/html/body/div[1]/div[1]/div/div/div[2]/div/div[2]/div[1]/div[1]/div[2]"
                tab_el = self.driver.find_element(By.XPATH, tab_xpath)
                if "is_active" not in (tab_el.get_attribute("class") or ""):
                    tab_el.click()
                    self._log("点击了: 市区县 Tab")
                    self._sleep_random(self.wait_action_delay)
                all_xpath = "/html/body/div[1]/div[1]/div/div/div[2]/div/div[2]/div[1]/div[2]/div[1]/div[3]/div[2]/div[1]"
                all_el = self.driver.find_element(By.XPATH, all_xpath)
                all_el.click()
                self._log("选择了: 市区县 - 全部")
                self._sleep_random(self.wait_action_delay)
            elif area in city_xpath_index:
                tab_xpath = "/html/body/div[1]/div[1]/div/div/div[2]/div/div[2]/div[1]/div[1]/div[2]"
                tab_el = self.driver.find_element(By.XPATH, tab_xpath)
                if "is_active" not in (tab_el.get_attribute("class") or ""):
                    tab_el.click()
                    self._log("点击了: 市区县 Tab")
                    self._sleep_random(self.wait_action_delay)
                idx = city_xpath_index[area]
                city_xpath = f"/html/body/div[1]/div[1]/div/div/div[2]/div/div[2]/div[1]/div[2]/div[1]/div[3]/div[2]/div[{idx}]"
                city_el = self.driver.find_element(By.XPATH, city_xpath)
                city_el.click()
                self._log(f"选择了城市: {city_el.text.strip()}")
                self._sleep_random(self.wait_action_delay)
        except Exception as e:
            self._log(f"地区选择出错: {e}")

        # 2. 标题输入
        if title:
            try:
                inputs = self.driver.find_elements(By.TAG_NAME, "input")
                for inp in inputs:
                    ph = inp.get_attribute("placeholder")
                    if ph and "公告标题" in ph:
                        inp.clear()
                        inp.send_keys(title)
                        break
            except Exception as e:
                self._log(f"标题输入出错: {e}")

        # 3. 时间范围选择
        time_range_map = { "7": "近7天", "30": "近30天", "180": "近半年", "365": "近一年", "1095": "近三年" }
        
        if start_time == "0":
            from datetime import datetime, timedelta
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            today = datetime.now().strftime("%Y-%m-%d")
            self._log(f"今日模式策略: 爬取 {yesterday} ~ {today}")
            self._fill_date_range(yesterday, today)
        elif start_time in time_range_map:
            quick_btn_text = time_range_map[start_time]
            try:
                self._log(f"尝试点击时间范围: {quick_btn_text}")
                all_divs = self.driver.find_elements(By.TAG_NAME, "div")
                clicked = False
                for div in all_divs:
                    try:
                        div_text = div.text.strip()
                        div_class = div.get_attribute("class") or ""
                        if "item" in div_class and div_text == quick_btn_text:
                            if "is_active" not in div_class:
                                div.click()
                                self._log(f"点击了时间范围按钮: {quick_btn_text}")
                                self._sleep_random(self.wait_action_delay)
                            clicked = True
                            break
                    except: continue
            except Exception as e: self._log(f"快捷时间设置出错: {e}")
        else:
            # 处理自定义日期 (如 2026-01-01)
            self._log(f"使用自选日期: {start_time} 至 {end_time}")
            self._fill_date_range(start_time, end_time)

        # 4. 点击查询 (带重试机制)
        try:
            try:
                refresh_btn = self.driver.find_element(By.CSS_SELECTOR, "div.n-captcha i.refresh-icon")
                refresh_btn.click()
                self._log("强制刷新验证码...")
                self._sleep_random(self.wait_action_delay) 
            except: pass

            max_search_attempts = 5
            search_success = False
            for attempt in range(max_search_attempts):
                self.solve_captcha(refresh_first=(attempt > 0))
                buttons = self.driver.find_elements(By.TAG_NAME, "button")
                found_btn = False
                for btn in buttons:
                    if btn.text and "查询" in btn.text:
                        btn.click()
                        found_btn = True
                        break
                if not found_btn: break
                self._sleep_random(self.wait_search)
                error = self.check_search_error()
                if error == "captcha_error":
                    self._log(f"⚠️ 识别错误 (尝试 {attempt+1}/{max_search_attempts})...")
                    continue
                res_count = self.get_result_count()
                if res_count >= 0:
                    self._log(f"✅ 查询成功，总数: {res_count}")
                    search_success = True
                    break
            return search_success
        except Exception as e:
            self._log(f"搜索提交出错: {e}")
            return False


    def extract_records(self):
        """
        提取当前页列表数据，并点击获取详情页 URL ID
        """
        records = []
        try:
            # 1. 精确查找有效数据行（无需等待重试，找不到直接返回空，由上层rescue逻辑处理）
            all_rows = self.driver.find_elements(By.CSS_SELECTOR, "table:not(.el-date-table) tbody tr")
            
            # 二次过滤：排除含有 el-date-table__row 类的行
            all_rows = [r for r in all_rows if "el-date-table__row" not in (r.get_attribute("class") or "")]
            visible_rows = [r for r in all_rows if r.is_displayed()]
            
            self._log(f"当前页发现 {len(all_rows)} 行，其中可见行 {len(visible_rows)} 行")
            
            if len(all_rows) > 0 and len(visible_rows) == 0:
                self._log("⚠️ 警告：检测到有数据行但判定为不可见，正在分析原因...")
                for idx, r in enumerate(all_rows[:3]): # 只分析前3行
                    try:
                        className = r.get_attribute("class")
                        style = r.get_attribute("style")
                        innerText = r.get_attribute("innerText")
                        self._log(f"Row {idx} Debug: Class='{className}', Style='{style}', Text='{innerText[:50]}...'")
                        # 检查父级
                        parent = r.find_element(By.XPATH, "./..") # tbody
                        p_style = parent.get_attribute("style")
                        p_class = parent.get_attribute("class")
                        self._log(f"Parent (TBODY) Debug: Class='{p_class}', Style='{p_style}'")
                    except Exception as e:
                        self._log(f"分析行 {idx} 失败: {e}")
                
                # 尝试强制使用 all_rows，看看是否能死马当活马医
                self._log("尝试强制处理所有行（忽略可见性检查）...")
                visible_rows = all_rows
            
            # 保存主窗口句柄
            main_handle = self.driver.current_window_handle
            
            # 由于点击后可能会发生页面跳转或刷新，导致 element 失效 (StaleElementReferenceException)
            # 我们采取"先收集索引，再逐个处理"的策略，或者每次重新获取？
            # 如果是新标签页打开，row element 不会失效。
            # 如果是当前页跳转，back() 后 row element 会失效。
            # 既然不确定，我们采用保守策略：每次处理完恢复现场后，重新获取 row 列表
            
            row_count = len(visible_rows)
            for i in range(row_count):
                try:
                    # 重新获取行列表，防止 Stale
                    current_rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                    visible_current_rows = [r for r in current_rows if r.is_displayed()]
                    
                    if i >= len(visible_current_rows):
                        break
                        
                    row = visible_current_rows[i]
                    
                    # 提取基础数据
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) < 3: continue
                    
                    area_name = cols[1].text.strip()
                    title = cols[2].text.strip()
                    # buy_mode = cols[3].text.strip()  # 官方数据为空，已注释
                    # prj_type = cols[4].text.strip()  # 官方数据为空，已注释
                    pub_date = cols[5].text.strip()
                    
                    # 点击标题
                    # 尝试定位标题元素
                    try:
                        click_target = cols[2].find_element(By.TAG_NAME, "span")
                    except:
                        click_target = cols[2] # 降级点击 td
                    
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", click_target)
                    self._sleep_random(self.wait_action_delay)
                    
                    # 记录点击前的状态
                    old_handles = self.driver.window_handles
                    old_url = self.driver.current_url
                    
                    # 执行点击
                    try:
                        click_target.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", click_target)
                    
                    # 等待反应
                    self._sleep_random(self.wait_action_delay)
                    
                    new_handles = self.driver.window_handles
                    new_url = self.driver.current_url
                    detail_url = ""
                    publisher = ""  # 初始化发布人
                    publish_datetime = ""  # 初始化发布具体时间
                    
                    if len(new_handles) > len(old_handles):
                        # 新标签页打开了
                        new_handle = [h for h in new_handles if h not in old_handles][0]
                        self.driver.switch_to.window(new_handle)
                        self._log("已打开详情页 Tab，模拟浏览停留...")
                        self._sleep_random(self.wait_detail_page)
                        detail_url = self.driver.current_url
                        
                        # 提取发布具体时间 (格式: "发布时间：2026-02-05 10:46:14")
                        publish_datetime = ""
                        try:
                            time_xpath = "/html/body/div/div[1]/div/div/div[1]/div[2]/span[1]"
                            time_el = self.driver.find_element(By.XPATH, time_xpath)
                            time_raw = time_el.text.strip()
                            # 去掉 "发布时间：" 前缀
                            if "发布时间：" in time_raw:
                                publish_datetime = time_raw.replace("发布时间：", "").strip()
                            elif "发布时间:" in time_raw:
                                publish_datetime = time_raw.replace("发布时间:", "").strip()
                            else:
                                publish_datetime = time_raw
                            self._log(f"提取到发布具体时间: {publish_datetime}")
                        except Exception as e:
                            self._log(f"提取发布具体时间失败: {e}")
                        
                        # 提取发布人
                        publisher = ""
                        try:
                            publisher_xpath = "/html/body/div/div[1]/div/div/div[1]/div[2]/span[2]"
                            publisher_el = self.driver.find_element(By.XPATH, publisher_xpath)
                            publisher_raw = publisher_el.text.strip()
                            # 去掉"发布人："前缀
                            if "发布人：" in publisher_raw:
                                publisher = publisher_raw.replace("发布人：", "").strip()
                            else:
                                publisher = publisher_raw
                        except Exception as e:
                            self._log(f"提取发布人失败: {e}")
                        
                        self.driver.close()
                        self.driver.switch_to.window(main_handle)
                    elif new_url != old_url:
                        # 当前页跳转了
                        detail_url = new_url
                        self.driver.back()
                        # 等待列表页重新加载
                        try:
                            WebDriverWait(self.driver, 10).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
                            )
                        except:
                            self._log("返回列表页后等待超市")
                    else:
                        self._log(f"点击第 {i+1} 行未触发跳转，尝试强制 JS 打开？")
                        # 暂时跳过
                        pass

                    # 解析 ID 和 oldData
                    if detail_url:
                        record_id = ""
                        col_code = "01" 
                        old_data = "0"
                        
                        if "id=" in detail_url:
                            match = re.search(r"id=([^&]+)", detail_url)
                            if match: record_id = match.group(1)
                        if "colCode=" in detail_url:
                            match = re.search(r"colCode=([^&]+)", detail_url)
                            if match: col_code = match.group(1)
                        if "oldData=" in detail_url:
                            match = re.search(r"oldData=([^&]+)", detail_url)
                            if match: old_data = match.group(1)
                        
                        if record_id:
                            rec = {
                                "id": record_id,
                                "colCode": col_code,
                                "oldData": old_data,
                                "title": title,
                                "areaName": area_name,
                                # "buyKindCode": buy_mode,  # 已注释
                                # "projectType": prj_type,  # 已注释
                                "date": pub_date,
                                "publishDatetime": publish_datetime,  # 发布具体时间 (精确到秒)
                                "url": detail_url,
                                "publisher": publisher  # 发布人
                            }
                            records.append(rec)
                            self._log(f"成功提取: {title}")
                        
                except Exception as e:
                    self._log(f"行处理出错: {e}")
                    # 尝试恢复句柄
                    try:
                        if len(self.driver.window_handles) > 1:
                            self.driver.switch_to.window(main_handle)
                    except: pass
                    
        except Exception as e:
            self._log(f"提取列表出错: {e}")
            
        return records

    def next_page(self):
        """点击下一页，并处理可能出现的验证码"""
        try:
            # li.btn-next/ button.btn-next
            next_btn = self.driver.find_element(By.CSS_SELECTOR, "button.btn-next")
            btn_class = next_btn.get_attribute("class") or ""
            btn_disabled = next_btn.get_attribute("disabled")
            
            self._log(f"下一页按钮状态: class='{btn_class}', disabled='{btn_disabled}', is_enabled={next_btn.is_enabled()}")
            
            # Element UI disabled button has property or class
            if next_btn.is_enabled() and "disabled" not in btn_class:
                next_btn.click()
                self._log("已点击下一页按钮")
                self._sleep_random(self.wait_next_page) # 等待加载
                
                # 翻页后可能需要验证码！检测并处理
                has_captcha = self.solve_captcha(refresh_first=True)
                if has_captcha:
                    self._log("翻页后检测到验证码，已自动处理")
                    # 点击查询按钮
                    buttons = self.driver.find_elements(By.TAG_NAME, "button")
                    for btn in buttons:
                        if btn.text and "查询" in btn.text:
                            btn.click()
                            self._log("点击了查询按钮")
                            self._sleep_random(self.wait_action_delay)
                            break
                
                return True
            else:
                self._log(f"下一页按钮不可用 (disabled/class包含disabled)")
                return False
        except Exception as e:
            self._log(f"翻页失败: {e}")
            return False

    def get_current_page(self):
        """获取当前页码"""
        try:
            inp = self.driver.find_element(By.CSS_SELECTOR, ".el-pagination__editor input")
            val = inp.get_attribute("value")
            if val and val.isdigit():
                return int(val)
        except:
            pass
        return 1  # 默认返回1

    def jump_to_page(self, page_num):
        """跳转到指定页"""
        try:
            self._log(f"尝试跳转到第 {page_num} 页...")
            from selenium.webdriver.common.keys import Keys
            
            # 找到输入框: .el-pagination__editor input
            inp = self.driver.find_element(By.CSS_SELECTOR, ".el-pagination__editor input")
            
            # 记录当前值
            old_val = inp.get_attribute("value")
            self._log(f"跳转前输入框值: '{old_val}'")
            
            # 彻底清空：先全选再删除
            inp.click()
            inp.send_keys(Keys.CONTROL + "a")
            inp.send_keys(Keys.DELETE)
            time.sleep(random.uniform(0.5, 1.5))
            
            # 输入目标页码
            inp.send_keys(str(page_num))
            time.sleep(random.uniform(0.5, 1.5))
            
            # 回车触发跳转
            inp.send_keys(Keys.ENTER)
            self._log(f"已输入页码 {page_num} 并按下回车")
            self._sleep_random(self.wait_next_page)
            
            # 验证跳转结果
            new_val = inp.get_attribute("value")
            self._log(f"跳转后输入框值: '{new_val}'")
            
            # 跳转后也可能需要验证码
            has_captcha = self.solve_captcha(refresh_first=True)
            if has_captcha:
                self._log("跳转页面后检测到验证码，已自动处理")
                # 点击查询按钮
                buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    if btn.text and "查询" in btn.text:
                        btn.click()
                        self._log("点击了查询按钮")
                        time.sleep(random.uniform(2, 3))
                        break
            
            return True
        except Exception as e:
            self._log(f"页面跳转失败: {e}")
            return False
    def is_no_data_visible(self):
        """
        检查当前页面是否显示“暂无数据”或结果为0
        """
        try:
            # 1. 检查搜索结果条数 el
            if self.get_result_count() == 0:
                self._log("检测到搜索结果总数为0")
                return True

            # 2. Element UI 常见的空状态选择器
            empty_selectors = [".el-table__empty-text", ".el-empty__description", ".n-no-data"]
            for sel in empty_selectors:
                el = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if el and el[0].is_displayed():
                    text = el[0].text.strip()
                    if text and ("暂无数据" in text or "无数据" in text or "未查询到" in text):
                        self._log(f"检测到空状态提示: {text}")
                        return True
            
            # 3. 检查表格 td
            all_tds = self.driver.find_elements(By.CSS_SELECTOR, "table td")
            for td in all_tds[:5]: # 只检查前几个
                 if "暂无数据" in td.text:
                     return True
            return False
        except:
            return False

    def is_captcha_showing(self):
        """
        检查当前页面是否显示验证码
        """
        try:
            captcha_divs = self.driver.find_elements(By.CSS_SELECTOR, "div.n-captcha")
            if captcha_divs and captcha_divs[0].is_displayed():
                return True
            return False
        except:
            return False
    def check_search_error(self):
        """
        检查页面是否弹出错误消息（如验证码错误）
        """
        try:
            # 临时将隐式等待缩短到很小，因为错误消息通常是立刻弹出的，不需要死等 15 秒
            self.driver.implicitly_wait(2)
            # 常见 Element UI 消息选择器
            msgs = self.driver.find_elements(By.CSS_SELECTOR, ".el-message--warning, .el-message--error")
            for msg in msgs:
                if msg.is_displayed():
                    text = msg.text.strip()
                    if "验证码" in text:
                        return "captcha_error"
                    return text
            return None
        except:
            return None
        finally:
            # 恢复隐式等待（读取环境变量或默认15秒）
            import os
            implicit_wait = int(os.getenv("IMPLICIT_WAIT_TIMEOUT", "15"))
            self.driver.implicitly_wait(implicit_wait)

    def get_result_count(self):
        """
        解析搜索结果的总条数 (例如: 共搜到526条内容)
        """
        try:
            xpath = "/html/body/div[1]/div[1]/div/div/div[2]/div/div[2]/div[2]/div"
            el = self.driver.find_element(By.XPATH, xpath)
            text = el.text.strip()
            # 格式：！ 搜索结果：共搜到526条内容
            import re
            match = re.search(r"共搜到\s*(\d+)\s*条", text)
            if match:
                return int(match.group(1))
            # 增加备用容错：只要能找到这个由数字组成的块，且没有报错，也可以视为成功
            if "共搜到" in text:
               return 0
            return -1 # -1 表示没找到这行提示，可能是验证码失败了
        except:
            return -1
