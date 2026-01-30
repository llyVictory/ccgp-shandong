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

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def solve_captcha(self):
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
                    try:
                        refresh_btn = self.driver.find_element(By.CSS_SELECTOR, "div.n-captcha i.refresh-icon")
                        refresh_btn.click()
                        self._log("点击了验证码刷新按钮")
                        time.sleep(random.uniform(2, 3)) # 等待新图片加载
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
                        time.sleep(random.uniform(2, 3))
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
        self._log(f"执行搜索: 地区={area}, 标题={title}, 时间={start_time}~{end_time}")
        
        # 0. 切换到 '意向公开' Tab (用户强制要求)
        try:
            self._log("尝试切换到 '意向公开' Tab...")
            # 这里的 selector 是根据用户提供的 HTML 片段推断
            # <li data-v-6fa4cba9="" class="is_active">意向公开</li>
            # 为了稳健，我们通过文本内容查找
            all_lis = self.driver.find_elements(By.TAG_NAME, "li")
            target_li = None
            for li in all_lis:
                if "意向公开" in li.text.strip():
                    target_li = li
                    break
            
            if target_li:
                # 检查是否激活
                class_attr = target_li.get_attribute("class") or ""
                if "is_active" not in class_attr:
                    target_li.click()
                    self._log("点击了 '意向公开' Tab")
                    time.sleep(random.uniform(3, 5))
                else:
                    self._log("'意向公开' Tab 已经是激活状态")
            else:
                self._log("警告：未找到 '意向公开' Tab，可能页面结构已变更")
                
        except Exception as e:
            self._log(f"切换 Tab 失败: {e}")

        
        # 1. 地区选择
        # 默认是“省级” (370000)，如果要选市区县，需要点击 Tab
        # div.second-n-radio > div (两个，第一个省级，第二个市区县)
        try:
            tabs = self.driver.find_elements(By.CSS_SELECTOR, "div.second-n-radio > div")
            if len(tabs) >= 2:
                if area == "370000":
                    if "is_active" not in tabs[0].get_attribute("class"):
                        tabs[0].click()
                        time.sleep(random.uniform(2, 3))
                else:
                    # 市区县
                    if "is_active" not in tabs[1].get_attribute("class"):
                        tabs[1].click()
                        time.sleep(random.uniform(2, 3))
                    
                    # 还要点击具体的市
                    # 找到包含该地区名称的 item
                    # 比如 area="370100" -> 济南市
                    # 需要一个映射表，或者简单遍历文本
                    # 这里简化处理：如果是 370000 以外，暂只支持“市区县”大类，或者需要更复杂的点击
                    # 考虑到用户之前的 select 有 value -> text 映射
                    # 这里先略过具体城市的点击，以免复杂化，默认搜全省市区县
                    pass
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

        # 3. 时间输入
        if start_time:
            try:
                inputs = self.driver.find_elements(By.TAG_NAME, "input")
                for inp in inputs:
                    ph = inp.get_attribute("placeholder")
                    if ph and "开始时间" in ph:
                        inp.send_keys(start_time) # 也就是 YYYY-MM-DD
                        # ElementUI 日期控件可能需要回车或点击确认，或者点一下空白处
                        # 尝试 send keys 后点一下 body
                        self.driver.find_element(By.TAG_NAME, "body").click()
                        break
            except: pass
            
        if end_time:
            try:
                inputs = self.driver.find_elements(By.TAG_NAME, "input")
                for inp in inputs:
                    ph = inp.get_attribute("placeholder")
                    if ph and "结束时间" in ph:
                        inp.send_keys(end_time)
                        self.driver.find_element(By.TAG_NAME, "body").click()
                        break
            except: pass

        # 4. 点击查询 (可能触发验证码)
        # 查找按钮: span 文本为 "查询" 的按钮
        # 4. 点击查询 (带重试机制)
        # 查找按钮: span 文本为 "查询" 的按钮
        try:
            max_retries = 5
            for attempt in range(max_retries):
                self._log(f"执行查询 (尝试 {attempt + 1}/{max_retries})...")
                
                # a. 处理验证码
                # 第一次不强求刷新？或者根据情况。目前 solve_captcha 内部是“如果发现图片就刷新”，
                # 这稍微有点激进。但为了稳妥，我们每次重试都重新做一遍。
                # 注意：solve_captcha 返回 True 表示填了，False 表示没填(可能没出现)
                has_captcha = self.solve_captcha()

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
                    time.sleep(random.uniform(3, 5))
                    
                    # c. 检查是否出现“验证码错误”提示
                    # 检查页面 body 文本是否包含关键词，或者特定 element
                    # 这里简单检查 body text
                    page_source = self.driver.page_source
                    if "验证码错误" in page_source:
                         self._log("检测到 '验证码错误' 提示，准备重试...")
                         time.sleep(random.uniform(3, 5))
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
            # 1. 精确查找有效数据行
            # Element UI 有时会有多个 table (fixed header/column)，通常真实的在中间
            # 这里我们尝试通过判断行是否可见来过滤
            all_rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            visible_rows = [r for r in all_rows if r.is_displayed()]
            
            self._log(f"当前页发现 {len(all_rows)} 行，其中可见行 {len(visible_rows)} 行")
            
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
                    buy_mode = cols[3].text.strip()
                    prj_type = cols[4].text.strip()
                    pub_date = cols[5].text.strip()
                    
                    # 点击标题
                    # 尝试定位标题元素
                    try:
                        click_target = cols[2].find_element(By.TAG_NAME, "span")
                    except:
                        click_target = cols[2] # 降级点击 td
                    
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", click_target)
                    time.sleep(random.uniform(1, 3))
                    
                    # 记录点击前的状态
                    old_handles = self.driver.window_handles
                    old_url = self.driver.current_url
                    
                    # 执行点击
                    try:
                        click_target.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", click_target)
                    
                    # 等待反应
                    time.sleep(random.uniform(1, 3))
                    
                    new_handles = self.driver.window_handles
                    new_url = self.driver.current_url
                    detail_url = ""
                    
                    if len(new_handles) > len(old_handles):
                        # 新标签页打开了
                        new_handle = [h for h in new_handles if h not in old_handles][0]
                        self.driver.switch_to.window(new_handle)
                        self._log("已打开详情页 Tab，模拟浏览停留...")
                        time.sleep(random.uniform(3, 5))
                        detail_url = self.driver.current_url
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
                                "buyKindCode": buy_mode, 
                                "projectType": prj_type,
                                "date": pub_date,
                                "url": detail_url
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
        """点击下一页"""
        try:
            # li.btn-next/ button.btn-next
            next_btn = self.driver.find_element(By.CSS_SELECTOR, "button.btn-next")
            # Element UI disabled button has property or class
            if next_btn.is_enabled() and "disabled" not in next_btn.get_attribute("class"):
                next_btn.click()
                time.sleep(random.uniform(3, 5)) # 等待加载
                return True
        except:
            return False
        return False

    def jump_to_page(self, page_num):
        """跳转到指定页"""
        try:
            self._log(f"尝试跳转到第 {page_num} 页...")
            # 找到输入框: .el-pagination__editor input
            inp = self.driver.find_element(By.CSS_SELECTOR, ".el-pagination__editor input")
            inp.clear()
            inp.send_keys(str(page_num))
            time.sleep(random.uniform(2, 3))
            # 回车 or blur? Element UI usually triggers on Enter or Blur.
            from selenium.webdriver.common.keys import Keys
            inp.send_keys(Keys.ENTER)
            time.sleep(random.uniform(3, 5))
            return True
        except Exception as e:
            self._log(f"页面跳转失败: {e}")
            return False
