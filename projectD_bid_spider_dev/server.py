from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import uuid
from spider.shandong import Shandong
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import json
import shutil
from openpyxl.styles import Alignment, Font
import math
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def split_keywords(kw_str):
    """
    处理关键词字符串，支持中文和英文逗号分隔
    """
    if not kw_str:
        return ["大学", "学校", "学院", "教育厅", "教育电视台", "教育招生考试院", "电教馆", "电化教育馆"]
    # 支持中文逗号和英文逗号
    kw_str = kw_str.replace("，", ",")
    return [k.strip() for k in kw_str.split(",") if k.strip()]

def calculate_row_height(row_values, col_width_map, base_height=18):
    """
    根据每一列的内容长度和列宽，估算该行需要的最大高度。
    DingTalk 预览有时不会自动计算 wrap_text 的高度，需强制设置。
    """
    max_lines = 1
    
    # 字体宽度估算系数 (基于微软雅黑 10号)
    # 中文/全角字符宽度约为 2.0，英文/数字约为 1.1
    char_width_cn = 2.0
    char_width_en = 1.1
    
    for col_idx, val in enumerate(row_values, 1):
        if not val:
            continue
            
        # 获取当前列的设定宽度
        col_width = col_width_map.get(col_idx, 10) # 默认宽 10
        if col_width == 0: continue
        
        # 将内容转为字符串并计算预估总宽度
        text = str(val)
        estimated_width = 0
        for char in text:
            if '\u4e00' <= char <= '\u9fff': # 简单判断中文
                estimated_width += char_width_cn
            else:
                estimated_width += char_width_en
        
        # 加上一点 padding (左右各一点)
        estimated_width += 2 
        
        # 计算需要多少行
        lines = math.ceil(estimated_width / col_width)
        if lines > max_lines:
            max_lines = lines
            
    # 设置上限，防止单行过高 (例如最多 10 行)
    if max_lines > 15:
        max_lines = 15
        
    return max_lines * base_height

def save_df_to_excel_with_style(df, filepath):
    """
    保存 DataFrame 为 Excel，并设置手机端友好样式：
    1. 自动换行
    2. 顶端对齐
    3. 合理列宽适配手机屏幕
    4. 显式设置行高 (适配 DingTalk)
    """
    if df is None:
        return
        
    # 如果 DataFrame 为空，补入一行“无数据”标记
    if df.empty:
        cols = df.columns.tolist()
        if cols:
            # 创建一行数据，第一个单元格填入 "无数据"
            empty_row = {col: "" for col in cols}
            empty_row[cols[0]] = "无数据"
            df = pd.DataFrame([empty_row])
        else:
            # 如果连列名都没有（理论上不会），直接保存返回
            df.to_excel(filepath, index=False)
            return

    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='意向数据')
        workbook = writer.book
        worksheet = writer.sheets['意向数据']
        
        # 定义对齐样式：自动换行，水平/垂直都居中
        wrap_alignment = Alignment(wrap_text=True, vertical='center', horizontal='center')
        link_alignment = Alignment(wrap_text=True, vertical='center', horizontal='center')
        header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        
        # 预设列宽（极致优化：确保钉钉一打开，所有列都能通过滑动看到，无需手动调宽）
        # 核心逻辑：固定非重要列宽度，给长文本列预留足够宽度以触发自动换行，但不至于溢出屏幕太多
        col_width_map = {
            1: 6,   # 序号 
            2: 12,  # 地区 
            3: 25,  # 标题 
            4: 20,  # 发布时间
            5: 18,  # 发布人
            6: 6,   # 子序号
            7: 30,  # 采购项目名称
            8: 60,  # 采购需求概况
            9: 15, # 预算金额(万元)
            10: 20, # 拟面向中小企业预留
            11: 18, # 预计采购时间
            12: 20, # 备注
            13: 15, # 发布地址
        }
        
        # 应用列宽
        for col_idx, width in col_width_map.items():
            from openpyxl.utils import get_column_letter
            col_letter = get_column_letter(col_idx)
            worksheet.column_dimensions[col_letter].width = width

        
        # 应用对齐样式和字体
        # [用户配置] 内容行固定高度，您可以在此处直接修改数字来调节松紧
        FIXED_CONTENT_HEIGHT = 50 

        for row_idx, row in enumerate(worksheet.iter_rows(min_row=1), 1):
            if row_idx == 1:
                # 表头：固定高度 30
                worksheet.row_dimensions[row_idx].height = 30
            else:
                # 内容行：使用固定高度 (写死)
                worksheet.row_dimensions[row_idx].height = FIXED_CONTENT_HEIGHT

            for col_idx, cell in enumerate(row, 1):
                if row_idx == 1:
                    # 表头：加粗居中，确保标题不被遮挡
                    cell.alignment = header_alignment
                    cell.font = Font(bold=True, size=11, name='微软雅黑')
                else:
                    # 内容：全部强制自动换行 + 顶端对齐
                    cell.alignment = wrap_alignment
                    cell.font = Font(size=10, name='微软雅黑')
        
        # 添加筛选器
        worksheet.auto_filter.ref = worksheet.dimensions
        # 移除冻结窗格 (用户要求)
        # worksheet.freeze_panes = "C2" 

app = FastAPI()

# Make sure static directory exists
if not os.path.exists("static"):
    os.makedirs("static")

# Mount static files
app.mount("/ui", StaticFiles(directory="static"), name="static")

# Store task status and logs
tasks = {}

# 定时任务调度器
scheduler = BackgroundScheduler()
scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    print("正在关闭调度器和后台任务...")
    try:
        scheduler.shutdown(wait=False)
    except Exception as e:
        print(f"关闭调度器时出错: {e}")
    
    # 强制退出：由于 Selenium 的长时间阻塞或循环操作，FastAPI 默认的优雅停机
    # 会一直等待 BackgroundTasks 结束，导致 Ctrl+C 卡死并报错。这里直接强制终止进程。
    import os
    print("强制终止所有后台爬虫进程...")
    os._exit(0)

# 定时任务配置文件
SCHEDULE_CONFIG_FILE = "schedule_config.json"

# 定时任务日志和状态
scheduled_task_logs = []
scheduled_task_status = {
    "running": False,
    "last_result": None,
    "last_run_time": None
}

class CrawlRequest(BaseModel):
    area: str = "370000"
    startTime: str = ""
    endTime: str = ""
    startPage: int = 1
    maxPages: int = 1
    title: str = ""
    useProxy: bool = False
    keywords: str = ""

class ScheduleTaskRequest(BaseModel):
    area: str = "370000"
    hour: int = 0  # 执行时间（小时）
    minute: int = 0  # 执行时间（分钟）
    downloadPath: str = "D:\\spider_downloads"  # 下载路径
    keywords: str = "" # 检索关键词

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.post("/api/crawl")
async def start_crawl(req: CrawlRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "running", "file": None, "logs": []}
    
    background_tasks.add_task(run_spider_task, task_id, req)
    return {"task_id": task_id}

@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    return tasks.get(task_id, {"status": "not_found"})

@app.get("/api/download/{task_id}")
async def download_file(task_id: str):
    task = tasks.get(task_id)
    if task and task["status"] == "completed" and task["file"]:
        return FileResponse(task["file"], filename="shandong_data.xlsx")
    return {"error": "File not ready"}

import io
import sys
from contextlib import redirect_stdout

def run_spider_task(task_id: str, req: CrawlRequest):
    # Setup custom logging inside the function
    def log_callback(msg):
        print(msg) # Still print to terminal
        if task_id in tasks:
            tasks[task_id]["logs"].append(msg)
            # Keep log size manageable
            if len(tasks[task_id]["logs"]) > 1000:
                tasks[task_id]["logs"].pop(0)

    try:
        spider = Shandong(use_proxy=req.useProxy)
        spider.log_func = log_callback
        
        data = spider.run(
            max_pages=req.maxPages, 
            start_page=req.startPage,
            title=req.title, 
            start_time=req.startTime, 
            end_time=req.endTime, 
            area=req.area,
            keywords=split_keywords(req.keywords)
        )
        
        # 无论是否有数据，都生成 Excel 供下载（无数据则只有表头）
        df = pd.DataFrame(data if data else [])
        
        # 1. 整理采集到的数据（不再强制 14:00 过滤，因为单次任务由用户在前端指定各异的时间跨度）
        if not df.empty:
            log_callback(f"采集完成条数: {len(df)}")

        # 2. 列名归一化与补充表头
        if "发布具体时间" in df.columns:
            # 防止重名冲突出现两个“发布时间”
            if "发布时间" in df.columns:
                df = df.drop(columns=["发布时间"])
            df = df.rename(columns={"发布具体时间": "发布时间"})
        if "意向发布地址" in df.columns:
            if "发布地址" in df.columns:
                df = df.drop(columns=["发布地址"])
            df = df.rename(columns={"意向发布地址": "发布地址"})
            
        # 标准输出列
        cols = [
            "序号", "地区", "标题", "发布时间", "发布人",
            "子序号", "采购项目名称", "采购需求概况", "预算金额(万元)",
            "拟面向中小企业预留", "预计采购时间", "备注", "发布地址" 
        ]
        
        # 补全缺失列
        for col in cols:
            if col not in df.columns:
                df[col] = ""
        
        # 重新排序并编号
        df = df[cols]
        if not df.empty:
            df['序号'] = range(1, len(df) + 1)
        
        # 3. 保存文件
        filename = f"shandong_data_{task_id}.xlsx"
        filepath = os.path.join("static", filename)
        save_df_to_excel_with_style(df, filepath)
        
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["file"] = filepath
        
        if data:
            spider._log(f"任务完成! 数据已保存到 {filepath}")
        else:
            spider._log("任务完成，未抓取到数据，已生成空表头文件。")

            
    except Exception as e:
        print(f"Task failed: {e}")
        tasks[task_id]["status"] = "failed"
        if task_id in tasks:
            tasks[task_id]["logs"].append(f"Error: {str(e)}")

def run_scheduled_spider():
    """定时任务执行函数"""
    global scheduled_task_logs, scheduled_task_status
    
    # 清空之前的日志
    scheduled_task_logs = []
    scheduled_task_status["running"] = True
    scheduled_task_status["last_run_time"] = None
    scheduled_task_status["last_result"] = None
    
    def add_log(msg):
        """添加日志到全局列表并写入文件"""
        from datetime import datetime
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = f"[{time_str}] {msg}"
        
        scheduled_task_logs.append(msg)
        print(f"[定时任务] {msg}")
        
        pass
    
    add_log("=" * 50)
    add_log("定时任务开始执行...")
    add_log("=" * 50)
    
    # 读取配置
    try:
        with open(SCHEDULE_CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except:
        add_log("未找到定时任务配置，跳过执行")
        scheduled_task_status["running"] = False
        return
    
    area = config.get("area", "370000")
    download_path = config.get("downloadPath", "D:\\spider_downloads_C")
    keywords_str = config.get("keywords", "大学，学校，学院，教育厅，教育电视台，教育招生考试院，电教馆，电化教育馆")
    
    # 确保下载目录存在
    os.makedirs(download_path, exist_ok=True)
    add_log(f"下载路径: {download_path}")
    add_log(f"检索关键词: {keywords_str}")
    
    # 定义日志回调函数
    def log_callback(msg):
        add_log(msg)
    
    # 执行爬取（今日数据，100页）
    spider = Shandong(use_proxy=False)
    spider.log_func = log_callback  # 设置日志回调
    
    add_log("开始爬取数据（时间范围: 昨天14:00 ~ 今天14:00，最多100页）...")
    
    data = spider.run(
        max_pages=100,
        start_page=1,
        title="",
        start_time="0",  # 今日
        end_time="",
        area=area,
        keywords=split_keywords(keywords_str)
    )
    
    # 定义列结构
    cols = [
        "序号", "地区", "标题", "发布时间", "发布人",
        "子序号", "采购项目名称", "采购需求概况", "预算金额(万元)",
        "拟面向中小企业预留", "预计采购时间", "备注", "发布地址"
    ]
    
    # 生成文件名（使用环境变量配置前缀：省本级采购意向（20260206）.xlsx）
    from datetime import datetime, timedelta
    today_str = datetime.now().strftime("%Y%m%d")
    prefix = os.getenv("EXCEL_FILENAME_PREFIX", "省本级采购意向")
    filename = f"{prefix}（{today_str}）.xlsx"
    filepath = os.path.join(download_path, filename)
    
    if data:
        df = pd.DataFrame(data)
        
        # 时间过滤：只保留 昨天14:00 ~ 今天14:00 的数据
        try:
            now = datetime.now()
            today_14 = now.replace(hour=14, minute=0, second=0, microsecond=0)
            yesterday_14 = today_14 - timedelta(days=1)
            
            add_log(f"时间过滤范围: {yesterday_14.strftime('%Y-%m-%d %H:%M:%S')} ~ {today_14.strftime('%Y-%m-%d %H:%M:%S')}")
            add_log(f"过滤前数据条数: {len(df)}")
            
            if "发布具体时间" in df.columns:
                def is_in_range(dt_str):
                    if not dt_str or pd.isna(dt_str):
                        return True
                    try:
                        dt = datetime.strptime(str(dt_str).strip(), "%Y-%m-%d %H:%M:%S")
                        return yesterday_14 <= dt <= today_14
                    except:
                        return True
                
                df = df[df["发布具体时间"].apply(is_in_range)]
                add_log(f"过滤后数据条数: {len(df)}")
            else:
                add_log("⚠️ 未找到'发布具体时间'列，跳过时间过滤")
        except Exception as e:
            add_log(f"时间过滤出错: {e}")
        
        if "发布具体时间" in df.columns:
            if "发布时间" in df.columns:
                df = df.drop(columns=["发布时间"])
            df = df.rename(columns={"发布具体时间": "发布时间"})
        if "意向发布地址" in df.columns:
            if "发布地址" in df.columns:
                df = df.drop(columns=["发布地址"])
            df = df.rename(columns={"意向发布地址": "发布地址"})

        for col in cols:
            if col not in df.columns:
                df[col] = ""
        
        df = df[cols]
        df['序号'] = range(1, len(df) + 1)
        
        # 使用带样式的保存函数
        save_df_to_excel_with_style(df, filepath)
        add_log(f"数据已保存到: {filepath}")
        add_log(f"共抓取 {len(df)} 条记录")
        
        # 设置任务完成状态
        scheduled_task_status["running"] = False
        scheduled_task_status["last_run_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        scheduled_task_status["last_result"] = {
            "success": True,
            "count": len(df),
            "filepath": filepath,
            "filename": filename
        }
        add_log("=" * 50)
        add_log("定时任务执行完成！")
        add_log("=" * 50)
    else:
        # 创建空的Excel文件（带样式和表头）
        df = pd.DataFrame(columns=cols)
        save_df_to_excel_with_style(df, filepath)
        
        add_log("未抓取到任何数据，已生成空Excel文件")
        add_log(f"文件已保存到: {filepath}")
        
        scheduled_task_status["running"] = False
        scheduled_task_status["last_run_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        scheduled_task_status["last_result"] = {
            "success": True,
            "count": 0,
            "filepath": filepath,
            "filename": filename
        }
        add_log("=" * 50)
        add_log("定时任务执行完成（无数据）")
        add_log("=" * 50)

@app.post("/api/schedule/create")
async def create_schedule(req: ScheduleTaskRequest):
    """创建/更新定时任务"""
    # 保存配置
    config = {
        "area": req.area,
        "hour": req.hour,
        "minute": req.minute,
        "downloadPath": req.downloadPath,
        "keywords": req.keywords
    }
    
    with open(SCHEDULE_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    # 删除旧任务
    scheduler.remove_all_jobs()
    
    # 添加新任务
    # misfire_grace_time=3600 表示如果错过了时间点，在一小时内探测到仍会补执行
    # coalesce=True 表示如果错过了多次，只补执行一次
    trigger = CronTrigger(day_of_week='mon-sun', hour=req.hour, minute=req.minute)
    scheduler.add_job(
        run_scheduled_spider, 
        trigger, 
        id='daily_spider',
        misfire_grace_time=3600,
        coalesce=True
    )
    
    return {
        "success": True,
        "message": f"定时任务已创建/更新：每天 {req.hour:02d}:{req.minute:02d} 执行",
        "config": config
    }

@app.get("/api/schedule/status")
async def get_schedule_status():
    """获取定时任务状态"""
    try:
        with open(SCHEDULE_CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        jobs = scheduler.get_jobs()
        has_task = len(jobs) > 0
        
        return {
            "hasTask": has_task,
            "config": config if has_task else None
        }
    except:
        return {"hasTask": False, "config": None}

@app.delete("/api/schedule/delete")
async def delete_schedule():
    """删除定时任务"""
    scheduler.remove_all_jobs()
    
    if os.path.exists(SCHEDULE_CONFIG_FILE):
        os.remove(SCHEDULE_CONFIG_FILE)
    
    return {"success": True, "message": "定时任务已删除"}

@app.get("/api/schedule/logs")
async def get_schedule_logs():
    """获取定时任务日志和状态"""
    return {
        "logs": scheduled_task_logs,
        "status": scheduled_task_status
    }


if __name__ == "__main__":
    # --- Windows Console Optimization (Fix for "Enter" key pause issue) ---
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        hLineEdit = kernel32.GetStdHandle(-10) # Standard input handle
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(hLineEdit, ctypes.byref(mode))
        # Remove ENABLE_QUICK_EDIT_MODE (0x0040)
        new_mode = (mode.value & ~0x0040) | 0x0080 # 0x0080 is ENABLE_EXTENDED_FLAGS
        kernel32.SetConsoleMode(hLineEdit, new_mode)
        print("Windows Console: Quick Edit Mode disabled successfully.")
    except Exception as e:
        print(f"Windows Console Optimization Failed: {e}")
    # ----------------------------------------------------------------------

    import uvicorn
    # access_log=False：彻底关闭请求记录（屏蔽轮询日志），同时保留启动信息
    uvicorn.run(app, host="0.0.0.0", port=8091, access_log=False)
