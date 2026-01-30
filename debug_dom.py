from spider.browser_engine import BrowserEngine
import time
import random

def debug():
    browser = BrowserEngine(headless=True)
    browser.init_driver()
    
    try:
        # 尝试几个可能的入口
        urls = [
            "http://www.ccgp-shandong.gov.cn/xxgk" 
        ]
        
        for url in urls:
            print(f"Visiting {url}...")
            browser.driver.get(url)
            time.sleep(random.uniform(8, 15)) # Wait for Vue to render
            title = browser.driver.title
            print(f"Title: {title}")
            
            # 保存 HTML 以便 grep
            with open(f"debug_html_{urls.index(url)}.html", "w", encoding="utf-8") as f:
                f.write(browser.driver.page_source)
            print(f"Saved debug_html_{urls.index(url)}.html")
            
    finally:
        browser.close()

if __name__ == "__main__":
    debug()
