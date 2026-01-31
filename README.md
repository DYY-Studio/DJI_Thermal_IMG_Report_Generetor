# DJI Thermal Image Report Generator
批量生成简化的、形式上类似于DJI Thermal Analysis Tool的PDF图像报告

基于 DJI Thermal SDK 的示范程序 `dji_irp` 实现伪彩色转换和温度范围提取

## 实现功能
* 基于Python的Windows/Linux系统支持（由于DJI没有macOS的SDK，不受支持）
* 多文件批量输入
* 批量转换LUT/调色盘
* 输出批量报告
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
   source .venv/bin/activate # Linux 
   ```
   ```bash
   # 安装依赖
   # requirements/requirements-cli-* 适用于使用CLI版本的用户
   # requirements/requirements-gui-* 适用于使用GUI版本的用户
   # requirements/requirements-* 全都装上的用户
   pip install -r requirements/requirements-win.txt # Windows
   pip install -r requirements/requirements-linux.txt # Linux
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
## GUI 图形化界面
```bash
flet run gui.py
```
## CLI 命令提示符界面
```bash
python cli.py --help # 查看帮助信息
```
### 命令
* ```python cli.py report [OPTIONS] [输入文件夹]```
  * 输出一份输入文件的信息报告，类似于DJI Thermal Analysis Tool
  * 有一定技术基础的用户可自行调整 `template.html` 进行自定义
  > **OPTIONS**
  * `--dji`/`-d` 
    * 可执行文件`dji_irp`的绝对路径。
    * 如果没有输入，会在`$PATH`和工作目录下尝试搜索
  * `--input`/`-i`
    * 不希望输入文件夹时，可用该选项输入指定文件
    * 可重复多次该选项，输入多个文件
  * `--output`/`-o`
    * 指定输出文件夹，默认为`工作目录/reports`
  * `--temp`/`-t`
    * 指定临时文件暂存文件夹，默认为`工作目录/temps`
  * `--distance`/`-dis` 距离
  * `--humidity`/`-hum` 空气湿度
  * `--emissivity`/`-emi` 发射率
  * `--ambient`/`-amv` 环境温度
  * `--reflection`/`-ref` 反射温度
  * `--brightness`/`-bri` 亮度
  * `--palette`/`-p`
    * 可从 SDK 提供的10个 LUT / 调色盘 中选择一个进行转换
  * `--cbwidth`/`-cbw`
    * 温度-颜色光谱图的宽度
  * `--cbborder`/`--no-cbborder`
    * 温度-颜色光谱图是否需要黑色边框
  * `--weasy-lib`/`--no-weasy-lib`
    * 决定以Python库形式还是以可执行文件形式调用`WeasyPrint`
    * 对于Windows默认为`--no-weasy-lib`，需要把`weasyprint.exe`放到`$PATH`或工作目录下
    * 对于Linux默认为`--weasy-lib`
  * `--workers`/`-ws`
    * 最大并发执行数，适当调高可有效加快处理
* `python cli.py palette [OPTIONS] [输入文件夹]`
  * 批量转换图像到指定的LUT/调色盘（即使与原调色盘相同也会进行转换）
  > **OPTIONS**
  * `--dji`/`-d` 
    * 可执行文件`dji_irp`的绝对路径。
    * 如果没有输入，会在`$PATH`和工作目录下尝试搜索
  * `--input`/`-i`
    * 不希望输入文件夹时，可用该选项输入指定文件
    * 可重复多次该选项，输入多个文件
  * `--output`/`-o`
    * 指定输出文件夹，默认为`工作目录/palette_changed`
  * `--temp`/`-t`
    * 指定临时文件暂存文件夹，默认为`工作目录/temps`
  * `--palette`/`-p`
    * 可从 SDK 提供的10个 LUT / 调色盘 中选择一个进行转换
  * `--overwrite`/`-ow`
    * 是否要覆盖同名的输出文件
  * `--workers`/`-ws`
    * 最大并发执行数，适当调高可有效加快处理
## 依赖
* `flet`
  * 基于Flutter的跨平台GUI界面
* `exifread`
  * 读取图像`EXIF`数据
* `pillow`, `xmltodict`
  * 读取图像`XMP`数据
* `pillow`
  * 图像处理
* `typer`, `rich`
  * 驱动美观的可视化CLI
* `weasyprint`, `jinja2`
  * 使用HTML模板导出PDF页面
* `pymupdf`(`fitz`)
  * 高速高效将分散的PDF页合成为一个PDF

## 许可
MIT