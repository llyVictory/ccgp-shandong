from spider.shandong import Shandong
import pandas as pd
import os

def main():
    print("Starting crawl of Shandong Government Procurement Intention...")
    spider = Shandong()
    # You can adjust max_pages here. Set to a large number to crawl all.
    # Total pages is around 3114.
    # Total pages is around 3114.
    max_pages = 1
    
    print(f"Crawling first {max_pages} pages...")
    data = spider.run(max_pages=max_pages)
    
    if not data:
        print("No data found!")
        return

    df = pd.DataFrame(data)
    
    # Reorder/Ensure columns
    # Reorder/Ensure columns
    cols = [
        "序号", 
        "地区", 
        "标题", 
        "采购方式", 
        "项目类型", 
        "发布时间",
        "子序号",
        "采购项目名称",
        "采购需求概况",
        "预算金额(万元)",
        "拟面向中小企业预留",
        "预计采购时间",
        "备注",
        "Link" 
    ]
    
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
