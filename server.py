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

class ScheduleTaskRequest(BaseModel):
    area: str = "370000"
    hour: int = 0  # 执行时间（小时）
    minute: int = 0  # 执行时间（分钟）
    downloadPath: str = "D:\\spider_downloads"  # 下载路径

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
            area=req.area
        )
        
        if data:
            df = pd.DataFrame(data)
            # Define new column order
            cols = [
                "序号", 
                "地区", 
                "标题",
                "发布人",
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
            
            # Ensure all columns exist
            for col in cols:
                if col not in df.columns:
                    df[col] = ""
            
            # Reorder
            df = df[cols]
            
            # 自动编号：1, 2, 3, ...
            df['序号'] = range(1, len(df) + 1)
            
            filename = f"shandong_data_{task_id}.xlsx"
            filepath = os.path.join("static", filename)
            df.to_excel(filepath, index=False)
            
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["file"] = filepath
            spider._log(f"任务完成! 数据已保存到 {filepath}")
        else:
            tasks[task_id]["status"] = "completed"
            spider._log("任务完成，但未抓取到任何数据。")
            
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
        """添加日志到全局列表"""
        scheduled_task_logs.append(msg)
        print(f"[定时任务] {msg}")
    
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
    download_path = config.get("downloadPath", "D:\\spider_downloads")
    
    # 确保下载目录存在
    os.makedirs(download_path, exist_ok=True)
    add_log(f"下载路径: {download_path}")
    
    # 定义日志回调函数
    def log_callback(msg):
        add_log(msg)
    
    # 执行爬取（今日数据，100页）
    spider = Shandong(use_proxy=False)
    spider.log_func = log_callback  # 设置日志回调
    
    add_log("开始爬取今日数据（最多100页）...")
    
    data = spider.run(
        max_pages=100,
        start_page=1,
        title="",
        start_time="0",  # 今日
        end_time="",
        area=area
    )
    
    # 定义列结构
    cols = [
        "序号", "地区", "标题", "发布人", "发布时间",
        "子序号", "采购项目名称", "采购需求概况", "预算金额(万元)",
        "拟面向中小企业预留", "预计采购时间", "备注", "Link"
    ]
    
    # 生成文件名（带日期时间）
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"shandong_scheduled_{timestamp}.xlsx"
    filepath = os.path.join(download_path, filename)
    
    if data:
        df = pd.DataFrame(data)
        
        for col in cols:
            if col not in df.columns:
                df[col] = ""
        
        df = df[cols]
        df['序号'] = range(1, len(df) + 1)
        
        df.to_excel(filepath, index=False)
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
        # 创建空的Excel文件
        df = pd.DataFrame(columns=cols)
        df.to_excel(filepath, index=False)
        
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
        "downloadPath": req.downloadPath
    }
    
    with open(SCHEDULE_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    # 删除旧任务
    scheduler.remove_all_jobs()
    
    # 添加新任务
    trigger = CronTrigger(hour=req.hour, minute=req.minute)
    scheduler.add_job(run_scheduled_spider, trigger, id='daily_spider')
    
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
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
