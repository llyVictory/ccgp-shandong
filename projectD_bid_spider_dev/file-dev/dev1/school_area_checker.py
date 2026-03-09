import pandas as pd
import requests
import time
import random
import os

# 配置信息
EXCEL_PATH = r"d:\LLYWORK\spider\bid_spider\projectB_bid_spider_dev\file-dev\重点监测学校清单.xlsx"
AREA_TXT_PATH = r"d:\LLYWORK\spider\bid_spider\projectB_bid_spider_dev\file-dev\area.txt"
OUTPUT_PATH = r"d:\LLYWORK\spider\bid_spider\projectB_bid_spider_dev\file-dev\dev1\重点监测学校清单_已处理.xlsx"
API_URL = "http://www.ccgp-shandong.gov.cn:8087/api/website/site/getListByCode"

def load_area_mapping(file_path):
    """加载地市与相应的 area 编码映射"""
    mapping = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) == 2:
                mapping[parts[0]] = parts[1]
    return mapping

def check_school_area(title, area_code):
    """请求 API 并返回 total 值"""
    payload = {
        "colCode": "0301",
        "area": str(area_code),
        "title": title,
        "projectCode": "",
        "currentPage": 1,
        "pageSize": 10,
        "buyKind": "",
        "buyType": "",
        "startTime": "2023-01-01 00:00:00",
        "oldData": 0,
        "endTime": "2026-02-28 23:59:59",
        "homePage": 0,
        "mergeType": 0,
        "projectType": "",
        "unitName": "",
        "captchaUuid": "69067e7e4652baff4b3737db2fdb1ca7"
    }
    
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            res_json = response.json()
            # 校验嵌套结构 data.data.total
            total = res_json.get("data", {}).get("data", {}).get("total", 0)
            return total
        else:
            print(f"  [ERROR] 请求失败, HTTP 状态码: {response.status_code}")
            return 0
    except Exception as e:
        print(f"  [ERROR] 请求异常: {e}")
        return 0

def main():
    print("开始加载数据...")
    area_mapping = load_area_mapping(AREA_TXT_PATH)
    
    # 读取 Excel，优先从 OUTPUT_PATH 读取（如果存在）以支持续传
    if os.path.exists(OUTPUT_PATH):
        print(f"检测到已处理的文件 {OUTPUT_PATH}，将基于此文件继续运行...")
        df = pd.read_excel(OUTPUT_PATH)
    else:
        df = pd.read_excel(EXCEL_PATH)
    
    # 确保列名一致
    col_area_param = "可检索到area参数"
    col_area_name = "可检索到area参数中文"
    
    for index, row in df.iterrows():
        school_name = row["学校名称"]
        city = row["地市"]
        
        # 如果已经存在结果，跳过
        if pd.notna(row.get(col_area_param)) and str(row.get(col_area_param)).strip() != "":
            print(f"跳过 [{index+1}/{len(df)}]: {school_name} (已有数据)")
            continue

        print(f"正在处理 [{index+1}/{len(df)}]: {school_name} (地市: {city})")
        
        # 待测试的 area 列表：省级(370000) 和 对应地市编码
        test_areas = [("省级", "370000")]
        if city in area_mapping:
            test_areas.append((city, area_mapping[city]))
        else:
            print(f"  [WARN] 未找到地市 '{city}' 的映射编码")

        matched = False
        for area_name, area_code in test_areas:
            print(f"  尝试校验 area: {area_name} ({area_code})... ", end="")
            total = check_school_area(school_name, area_code)
            print(f"total={total}")
            
            if total > 0:
                df.at[index, col_area_param] = area_code
                df.at[index, col_area_name] = area_name
                matched = True
                print(f"  [SUCCESS] 匹配成功: {area_name}")
                break # 只要匹配到一个就停止
            
            # 随机延迟，防止封 IP (请求之间也做一点点延迟)
            time.sleep(random.uniform(1, 2))
            
        if not matched:
            print(f"  [FAIL] 未能匹配到任何区域")

        # 每处理完一个学校，随机延迟
        wait_time = random.uniform(3, 6)
        print(f"等待 {wait_time:.2f} 秒后处理下一个...")
        time.sleep(wait_time)

    # 保存结果
    df.to_excel(OUTPUT_PATH, index=False)
    print(f"\n处理完成！结果已保存至: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
