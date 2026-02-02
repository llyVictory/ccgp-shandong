# 山东政府采购意向爬虫

## 使用说明

### 前置要求

1. **Chrome 浏览器** - 请确保已安装最新版 Chrome
2. **Python 3.10+** - [下载地址](https://www.python.org/downloads/)

### 一键启动

双击 `启动爬虫.bat` 即可！

首次运行会自动：

- 创建虚拟环境
- 安装所需依赖

### 使用方法

1. 启动后，浏览器打开 <http://localhost:8080>
2. 选择搜索条件（地区、时间范围等）
3. 点击"开始爬取"
4. 等待完成后下载 Excel 文件

### 常见问题

**Q: 提示"未检测到 Python"**
A: 请安装 Python 3.10+，并勾选"Add Python to PATH"

**Q: 验证码总是识别错误**
A: 程序会自动重试，一般3-5次内会成功

**Q: 浏览器窗口不自动关闭**
A: 这是调试模式，任务完成后请手动关闭 Chrome 窗口

### 文件说明

```
bid_spider/
├── 启动爬虫.bat      # 一键启动脚本
├── server.py         # 后端服务
├── requirements.txt  # 依赖列表
├── static/
│   ├── index.html    # 前端页面
│   └── *.xlsx        # 导出的数据文件
└── spider/
    ├── browser_engine.py  # 浏览器控制
    └── shandong.py        # 爬虫逻辑
```
