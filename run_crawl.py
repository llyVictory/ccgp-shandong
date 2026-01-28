from spider.shandong import Shandong
import pandas as pd
import os

def main():
    print("Starting crawl of Shandong Government Procurement Intention...")
    spider = Shandong()
    # You can adjust max_pages here. Set to a large number to crawl all.
    # Total pages is around 3114.
    max_pages = 2
    
    print(f"Crawling first {max_pages} pages...")
    data = spider.run(max_pages=max_pages)
    
    if not data:
        print("No data found!")
        return

    df = pd.DataFrame(data)
    
    # Reorder/Ensure columns
    cols = ["序号", "分类1", "分类2", "地市", "客户名称", "项目名称", "金额", "预计时间", "link"]
    
    # Global index
    df['序号'] = range(1, len(df) + 1)
    
    # Ensure all columns exist
    for c in cols:
        if c not in df.columns:
            df[c] = ""
            
    df = df[cols]
    
    output_file = "shandong_intention_data.xlsx"
    df.to_excel(output_file, index=False)
    print(f"Successfully saved {len(df)} records to {os.path.abspath(output_file)}")

if __name__ == "__main__":
    main()
