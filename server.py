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
    maxPages: int = 5
    title: str = ""

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
    def task_log(msg):
        print(msg) # Still print to terminal
        if task_id in tasks:
            tasks[task_id]["logs"].append(msg)
            # Keep only last 100 lines
            if len(tasks[task_id]["logs"]) > 100:
                tasks[task_id]["logs"].pop(0)

    try:
        spider = Shandong()
        # Mocking print for the spider object just for this call
        # Since the spider uses 'print', we capture it
        f = io.StringIO()
        with redirect_stdout(f):
            # We'll poll f.getvalue() in a thread or just run and append
            # For simplicity, we'll wrap the spider's print if we can, 
            # but since spider is a class, we'll just redirect stdout globally for this thread
            
            # This is a bit tricky with multithreading but since uvicorn is async 
            # and background_tasks run in threadpool, it might work if we are careful.
            # A better way is to pass a logger to the spider.
            
            # Let's just update the spider class's print or use a different approach.
            # I will modify shandong.py to accept a logger function.
            pass
        
        # Re-doing the approach: modify Shandong to take a log_func
        spider.log_func = task_log
        
        data = spider.run(
            max_pages=req.maxPages,
            title=req.title,
            start_time=req.startTime,
            end_time=req.endTime,
            area=req.area
        )
        
        if data:
            df = pd.DataFrame(data)
            cols = ["序号", "分类1", "分类2", "地市", "客户名称", "项目名称", "金额", "预计时间", "link"]
            df['序号'] = range(1, len(df) + 1)
            for c in cols:
                if c not in df.columns:
                    df[c] = ""
            df = df[cols]
            
            file_name = f"output_{task_id}.xlsx"
            file_path = os.path.join("static", file_name)
            df.to_excel(file_path, index=False)
            tasks[task_id] = {"status": "completed", "file": file_path}
        else:
            tasks[task_id] = {"status": "failed", "error": "No data found"}
    except Exception as e:
        tasks[task_id] = {"status": "failed", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
