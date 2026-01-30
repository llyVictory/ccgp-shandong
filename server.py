from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import uuid
from spider.shandong import Shandong
import pandas as pd

app = FastAPI()

# Make sure static directory exists
if not os.path.exists("static"):
    os.makedirs("static")

# Mount static files
app.mount("/ui", StaticFiles(directory="static"), name="static")

# Store task status and logs
tasks = {}

class CrawlRequest(BaseModel):
    area: str = "370000"
    startTime: str = ""
    endTime: str = ""
    startPage: int = 1
    maxPages: int = 1
    title: str = ""
    useProxy: bool = False

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
            
            # Ensure all columns exist
            for col in cols:
                if col not in df.columns:
                    df[col] = ""
            
            # Reorder
            df = df[cols]
            
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
