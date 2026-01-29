# DJI Thermal Image Report Generator
批量生成简化的、形式上类似于DJI Thermal Analysis Tool的PDF图像报告

基于 DJI Thermal SDK 的示范程序 `dji_irp` 实现伪彩色转换和温度范围提取

## 实现功能
* 基于Python的跨操作系统支持
* 输入多文件，输出批量报告
* 基于`asyncio`和`concurrent`的异步&进程池并行加速
* 可从 DJI Thermal SDK 提供的10个LUT/调色盘中选择
  * `white_hot` | `fulgurite` | `iron_red` | `hot_iron`  | `medical`   | `arctic` | `rainbow1`  | `rainbow2`  | `tint` | `black_hot`
* 支持手动设置计算参数
  * `距离`，`空气湿度`，`发射率`，`环境温度`，`反射温度`
* 可以自行修改输出模板

## 使用方法
1. `clone`本仓库，或打包下载仓库
2. 安装依赖
```bash
# 可选：创建虚拟环境并激活
python -m venv .venv 

call ".\.venv\Scripts\activate.bat" # Windows: CMD
.\.venv\Scripts\Activate.ps1 # Windows: Powershell
source .venv/bin/activate # macOS / Linux 
```
```bash
# 安装依赖
pip install -r requirements.txt
```
3. 配置`weasyprint`，请阅读[这里](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation)
    * Windows 用户请直接从下面语句后开始阅读：
        > If you want to use WeasyPrint as a Python library 
4. 运行CLI
```bash
python cli.py --help # 查看帮助信息
```

## 依赖
* `pyexiv2`
  * 读取图像`EXIF`和`XMP`数据
* `typer`, `rich`
  * 驱动美观的可视化CLI
* `weasyprint`, `jinja2`
  * 使用HTML模板导出PDF页面
* `pymupdf`(`fitz`)
  * 高速高效将分散的PDF页合成为一个PDF

## 许可
MIT