# DJI Thermal Image Report Generator
批量生成简化的、形式上类似于DJI Thermal Analysis Tool的PDF图像报告

基于 DJI Thermal SDK 的示范程序 `dji_irp` 实现伪彩色转换和温度范围提取

## 实现功能
* 基于Python的Windows/Linux系统支持（由于DJI没有macOS的SDK，不受支持）
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
3. 下载 [DJI Thermal SDK](https://www.dji.com/cn/downloads/softwares/dji-thermal-sdk)，解压其中的`utility/bin`文件夹得到`dji_irp`
4. 配置`weasyprint`
   * Windows方法一（推荐）
     * 直接到[这里](https://github.com/Kozea/WeasyPrint/releases)下载预编译好的WeasyPrint可执行文件，放置在工作目录或`$PATH`环境变量的目录下
   * Windows方法二（难度较大，可能出现各种问题）
     * 根据[这里](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html)的指导，将其作为Python库安装。
     * 运行时需要加上参数`--weasy-lib`（该参数在Windows下默认为False）
   * Linux
     * 根据[这里](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html)的指导，完成安装
5. 运行CLI
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