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

class BrowserEngine:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        self.logger = None

    def _log(self, msg):
        if self.logger:
            self.logger(f"[Browser] {msg}")
        else:
            print(f"[Browser] {msg}")

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

        self._log("正在启动 Chrome 浏览器...")
        service = ChromeService(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        self.driver.implicitly_wait(5)
        self._log("浏览器启动成功")
        
        # 网络连接测试
        try:
            self.driver.set_page_load_timeout(15)
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
                            time.sleep(random.uniform(1, 2)) # 等待新图片加载
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
                        time.sleep(random.uniform(1, 2))
                        return True
            return False
        except Exception as e:
            self._log(f"验证码处理异常（非阻断）: {e}")
        
        return False

    def goto_search_page(self):
        url = "http://www.ccgp-shandong.gov.cn/xxgk"
        self._log(f"访问页面: {url}")
        self.driver.get(url)
        # 等待加载
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.second-search"))
            )
        except:
            self._log("页面加载超时，可能网络慢或结构变更")

    def perform_search(self, title="", start_time="", end_time="", area="370000"):
        # 把快捷代码转成可读文本用于日志显示
        time_display_map = {
            "0": "今日", "7": "近7天", "30": "近30天",
            "180": "近半年", "365": "近一年", "1095": "近三年"
        }
        time_display = time_display_map.get(start_time, f"{start_time}~{end_time}")
        # self._log(f"执行搜索: 地区={area}, 标题={title}, 时间范围={time_display}")
        
        # 0. 切换到 '意向公开' Tab (左侧菜单第一项)
        try:
            self._log("尝试切换到 '意向公开' Tab...")
            # 使用用户提供的精确 XPath
            tab_xpath = "/html/body/div[1]/div[1]/div/div/div[1]/div/ul/li[1]"
            tab_el = self.driver.find_element(By.XPATH, tab_xpath)
            
            # 检查是否已激活
            class_attr = tab_el.get_attribute("class") or ""
            if "is_active" not in class_attr:
                tab_el.click()
                self._log("点击了 '意向公开' Tab")
                time.sleep(random.uniform(1, 2))
            else:
                self._log("'意向公开' Tab 已经是激活状态")
        except Exception as e:
            self._log(f"切换 Tab 失败: {e}")

        
        # 1. 地区选择 - 使用精确的 XPath
        # 山东省本级 = 370000
        # 其他市需要先点击"市区县"tab，再点击具体城市
        try:
            # 城市代码到 XPath index 的映射 (基于用户提供的 XPath)
            city_xpath_index = {
                "370100": 2,   # 济南市
                "370200": 3,   # 青岛市
                "370300": 4,   # 淄博市
                "370400": 5,   # 枣庄市
                "370500": 6,   # 东营市
                "370600": 7,   # 烟台市
                "370700": 8,   # 潍坊市
                "370800": 9,   # 济宁市
                "370900": 10,  # 泰安市
                "371000": 11,  # 威海市
                "371100": 12,  # 日照市
                "371200": 13,  # 莱芜市
                "371300": 14,  # 临沂市
                "371400": 15,  # 德州市
                "371500": 16,  # 聊城市
                "371600": 17,  # 滨州市
                "371700": 18,  # 菏泽市
            }
            
            if area == "370000":
                # 山东省本级 - 直接点击
                xpath = "/html/body/div[1]/div[1]/div/div/div[2]/div/div[2]/div[1]/div[1]/div[1]"
                el = self.driver.find_element(By.XPATH, xpath)
                if "is_active" not in (el.get_attribute("class") or ""):
                    el.click()
                    self._log("选择了: 山东省本级")
                    time.sleep(random.uniform(1, 2))
            elif area in city_xpath_index:
                # 先点击"市区县"tab
                tab_xpath = "/html/body/div[1]/div[1]/div/div/div[2]/div/div[2]/div[1]/div[1]/div[2]"
                tab_el = self.driver.find_element(By.XPATH, tab_xpath)
                if "is_active" not in (tab_el.get_attribute("class") or ""):
                    tab_el.click()
                    self._log("点击了: 市区县 Tab")
                    time.sleep(random.uniform(1, 2))
                
                # 再点击具体城市
                idx = city_xpath_index[area]
                city_xpath = f"/html/body/div[1]/div[1]/div/div/div[2]/div/div[2]/div[1]/div[2]/div[1]/div[3]/div[2]/div[{idx}]"
                city_el = self.driver.find_element(By.XPATH, city_xpath)
                city_el.click()
                self._log(f"选择了城市: {city_el.text.strip()}")
                time.sleep(random.uniform(1, 2))
            else:
                self._log(f"未知的地区代码: {area}，跳过地区选择")
        except Exception as e:
            self._log(f"地区选择出错: {e}")

        # 2. 标题输入
        if title:
            try:
                # input[placeholder="请输入公告标题"]
                # 遍历 input 找 placeholder
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
        # 映射关系: 我们的参数 -> 网站按钮文本
        # start_time 现在传的是 quickTimeRange 值: "0"=今日, "7"=近7天, "30"=近30天, "180"=近半年, "365"=近一年, "1095"=近三年
        # 特殊处理: "0"(今日) 使用自定义时间范围: 昨天14:00 到 今天14:00
        time_range_map = {
            "7": "近7天",
            "30": "近30天",
            "180": "近半年",
            "365": "近一年",
            "1095": "近三年"
        }
        
        # 特殊处理 "0" (今日) - 策略：先爬取"昨天+今天"两天数据，后期通过精确发布时间过滤
        # 由于网站日期选择器只支持日期不支持时分秒，我们选择更宽的范围
        if start_time == "0":
            try:
                from datetime import datetime, timedelta
                now = datetime.now()
                yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
                today = now.strftime("%Y-%m-%d")
                
                self._log(f"时间范围策略: 爬取 {yesterday} ~ {today} 两天数据")
                self._log("后续将通过精确发布时间过滤 (昨天14:00 ~ 今天14:00)")
                
                # 尝试点击"自定义"或找到日期输入框
                # 1. 先尝试找并点击"自定义"按钮
                all_divs = self.driver.find_elements(By.TAG_NAME, "div")
                custom_clicked = False
                for div in all_divs:
                    try:
                        div_text = div.text.strip()
                        div_class = div.get_attribute("class") or ""
                        if "item" in div_class and ("自定义" in div_text or "自选" in div_text):
                            if "is_active" not in div_class:
                                div.click()
                                self._log("点击了'自定义'时间按钮")
                                time.sleep(random.uniform(1, 2))
                            custom_clicked = True
                            break
                    except:
                        continue
                
                # 2. 查找日期输入框 (只填日期，不填时分秒)
                date_inputs = []
                all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
                for inp in all_inputs:
                    ph = inp.get_attribute("placeholder") or ""
                    if "开始" in ph or "起始" in ph:
                        date_inputs.append(("start", inp))
                    elif "结束" in ph or "截止" in ph:
                        date_inputs.append(("end", inp))
                
                if len(date_inputs) < 2:
                    range_inputs = self.driver.find_elements(By.CSS_SELECTOR, ".el-date-editor input, .el-range-input")
                    if len(range_inputs) >= 2:
                        date_inputs = [("start", range_inputs[0]), ("end", range_inputs[1])]
                
                if len(date_inputs) >= 2:
                    for dtype, inp in date_inputs:
                        if dtype == "start":
                            inp.clear()
                            inp.send_keys(yesterday)
                            self._log(f"填入开始日期: {yesterday}")
                        elif dtype == "end":
                            inp.clear()
                            inp.send_keys(today)
                            self._log(f"填入结束日期: {today}")
                    time.sleep(random.uniform(1, 2))
                else:
                    # Fallback: 点击"近7天"按钮（包含昨天和今天）
                    self._log("⚠️ 未找到日期输入框，降级使用'近7天'按钮")
                    for div in all_divs:
                        try:
                            div_text = div.text.strip()
                            div_class = div.get_attribute("class") or ""
                            if "item" in div_class and div_text == "近7天":
                                if "is_active" not in div_class:
                                    div.click()
                                    self._log("点击了时间范围按钮: 近7天 (降级方案)")
                                    time.sleep(random.uniform(1, 2))
                                break
                        except:
                            continue
                            
            except Exception as e:
                self._log(f"时间范围设置出错: {e}")
        
        # 如果 start_time 是其他快捷代码（非"0"），点击对应按钮
        elif start_time in time_range_map:
            quick_btn_text = time_range_map[start_time]
            try:
                self._log(f"尝试点击时间范围: {quick_btn_text}")
                # 查找时间范围按钮列表 - 通过文本内容查找所有 div
                all_divs = self.driver.find_elements(By.TAG_NAME, "div")
                clicked = False
                for div in all_divs:
                    try:
                        div_text = div.text.strip()
                        div_class = div.get_attribute("class") or ""
                        # 必须是 .item 类的 div，且文本完全匹配
                        if "item" in div_class and div_text == quick_btn_text:
                            if "is_active" not in div_class:
                                div.click()
                                self._log(f"点击了时间范围按钮: {quick_btn_text}")
                                time.sleep(random.uniform(1, 2))
                            else:
                                self._log(f"时间范围按钮 '{quick_btn_text}' 已激活")
                            clicked = True
                            break
                    except:
                        continue
                
                if not clicked:
                    self._log(f"未找到时间范围按钮: {quick_btn_text}")
            except Exception as e:
                self._log(f"时间范围选择出错: {e}")

        # 4. 点击查询 (可能触发验证码)
        # 查找按钮: span 文本为 "查询" 的按钮
        # 4. 点击查询 (带重试机制)
        # 查找按钮: span 文本为 "查询" 的按钮
        try:
            max_retries = 5
            for attempt in range(max_retries):
                self._log(f"执行查询 (尝试 {attempt + 1}/{max_retries})...")
                
                # a. 处理验证码
                # 用户强调步骤：参数设置完 -> 点击刷新 -> 识别 -> 填入 -> 点击查询
                # 我们显式触发刷新按钮点击，确保拿到最新验证码
                try:
                    refresh_btn = self.driver.find_element(By.CSS_SELECTOR, "div.n-captcha i.refresh-icon")
                    refresh_btn.click()
                    self._log("强制刷新验证码...")
                    time.sleep(random.uniform(1, 2)) 
                except:
                    pass

                has_captcha = self.solve_captcha(refresh_first=False) # 已经刷过了，传个参控制一下(需修改solve_captcha)
                # 暂时 solve_captcha 内部还是会检测并刷新的逻辑，为了不破坏原有逻辑，
                # 我们先保留 solve_captcha 的内部逻辑，但在它执行前我们已经点了一次刷新，
                # solve_captcha 内部如果判断图片是 blob 且有效，可能不会点刷新？
                # The implementation of solve_captcha clicks refresh if it finds the image.
                # Let's rely on solve_captcha's own refresh logic but ensure we call it here.
                # The user's log shows "点击了验证码刷新按钮", so it IS refreshing.
                
                # The user suspects the input is wrong. "7c59" - maybe letters vs numbers?
                # or maybe the "check" happens too fast.
                
                # Let's stick to the plan: continue relying on solve_captcha but maybe add a small delay before it.


                # b. 点击查询
                buttons = self.driver.find_elements(By.TAG_NAME, "button")
                search_btn = None
                for btn in buttons:
                    if btn.text and "查询" in btn.text:
                        search_btn = btn
                        break
                
                if search_btn:
                    search_btn.click()
                    self._log("点击了查询按钮")
                    time.sleep(random.uniform(1, 2))
                    
                    # c. 检查是否出现“验证码错误”提示
                    # 检查页面 body 文本是否包含关键词，或者特定 element
                    # 这里简单检查 body text
                    page_source = self.driver.page_source
                    if "验证码错误" in page_source:
                         self._log("检测到 '验证码错误' 提示，准备重试...")
                         time.sleep(random.uniform(1, 2))
                         continue
                    
                    # d. 检查是否成功加载数据 (可选)
                    # 如果没有错误提示，且没有抛异常，我们假定成功
                    self._log("查询操作完成，未检测到错误提示。")
                    break
                else:
                    self._log("未找到查询按钮，无法执行搜索")
                    break
                
        except Exception as e:
            self._log(f"搜索过程出错: {e}")


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
                    time.sleep(random.uniform(1, 2))
                    
                    # 记录点击前的状态
                    old_handles = self.driver.window_handles
                    old_url = self.driver.current_url
                    
                    # 执行点击
                    try:
                        click_target.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", click_target)
                    
                    # 等待反应
                    time.sleep(random.uniform(1, 2))
                    
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
                        time.sleep(random.uniform(1, 2))
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
                time.sleep(random.uniform(2, 3)) # 等待加载
                
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
                            time.sleep(random.uniform(1, 2))
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
            time.sleep(random.uniform(2, 3))
            
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
