import os, datetime, exifread, uuid, asyncio, pathlib, json, traceback, fitz # PyMuPDF
from PIL import Image
from weasyprint import HTML
from jinja2 import Template
from enum import Enum
from concurrent.futures import ProcessPoolExecutor

# 配置路径
CLI_PATH = r"D:\Test\dji_thermal_sdk_v1.8_20250829\utility\bin\windows\release_x64\dji_irp.exe"  # 编译好的 dji_irp 路径
INPUT_DIR = "./input_images"
OUTPUT_DIR = "./reports"
TEMP_DIR = "./temp"
LUT_DIR = "./lut"

class ThermalPalette(Enum):
    white_hot = 0
    fulgurite = 1
    iron_red = 2
    hot_iron = 3
    medical = 4
    arctic = 5
    rainbow1 = 6
    rainbow2 = 7
    tint = 8
    black_hot = 9

def get_palette(palette: ThermalPalette):
    palette_json = pathlib.Path(LUT_DIR) / f"lut{palette.value}.json"
    if not palette_json.exists():
        raise FileNotFoundError("Cannot find target LUT file")
    with open(palette_json, mode='r', encoding='utf-8') as f:
        return ', '.join(f"rgb({r},{g},{b})" for r, g, b in json.load(f).__reversed__())

def convert_to_decimal(coords: tuple[int, int, float] | str) -> float:
    # coords 格式为 [23, 21, 28.4713]
    try:
        if isinstance(coords, str):
            coords = tuple(coord.strip() for coord in coords.strip('[]').split(','))
        d = float(coords[0])
        m = float(coords[1])
        s = float(coords[2])
        return d + (m / 60.0) + (s / 3600.0)
    except:
        return 0.0

class ThermalReportGenerator:
    def __init__(self, 
            distance: float = 5.0,
            humidity: float = 50.0,
            emissivity: float = 0.95,
            ambient: float = 25.0,
            reflection: float = 25.0,
            brightness: int = 50,
            palette: ThermalPalette = ThermalPalette.iron_red,
            max_workers: int = 4
        ):
        pathlib.Path(OUTPUT_DIR).mkdir(exist_ok=True)
        pathlib.Path(TEMP_DIR).mkdir(exist_ok=True)
        with open("template.html", "r", encoding="utf-8") as f:
            self.template = Template(f.read())

        self.distance = distance
        self.humidity = humidity
        self.emissivity = emissivity
        self.ambient = ambient
        self.reflection = reflection
        self.brightness = brightness
        self.palette = palette

        self.semaphore = asyncio.Semaphore(max_workers)
        self.executor = ProcessPoolExecutor(max_workers=max_workers)

    def get_metadata(self, img_path):
        """从 APP1 Marker 提取元数据"""
        with open(img_path, 'rb') as f:
            tags = exifread.process_file(f, builtin_types=True)
            
        def get_tag(key):
            return str(tags.get(key, "N/A"))

        return {
            "model": get_tag('Image Model'),
            "sn": get_tag('EXIF BodySerialNumber'),
            "focal_length": get_tag('EXIF FocalLength'),
            "aperture": f"{float(get_tag('EXIF FNumber')):.1f}" if get_tag('EXIF FNumber') != "N/A" else "N/A",
            "create_time": get_tag('EXIF DateTimeOriginal'),
            "gps": f"{convert_to_decimal(get_tag('GPS GPSLatitude')):.6f}, {convert_to_decimal(get_tag('GPS GPSLongitude')):.6f}"
        }

    async def process_thermal_async(self, img_path: str, task_id: str):
        """调用 DJI SDK CLI 处理图像"""
        raw_out = os.path.join(TEMP_DIR, f"{task_id}.raw")
        
        # 生成伪彩色图像数据 (RGB 格式)
        cmd = [
            "-a", "process", "-s", img_path, "-o", raw_out, 
            "-p", self.palette.name,
            "--distance", str(self.distance),
            "--humidity", str(self.humidity),
            "--emissivity", str(self.emissivity),
            "--ambient", str(self.ambient),
            "--reflection", str(self.reflection),
            "--brightness", str(self.brightness)
        ]
        proc = await asyncio.create_subprocess_exec(
            CLI_PATH, *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        result = stdout.decode()
        
        # 解析 CLI 输出获取自适应温度范围
        # 示例输出: Color bar adaptive range is [25.5, 36.8]
        min_temp, max_temp, w, h = "N/A", "N/A", 0, 0
        for line in result.split('\n'):
            if "adaptive range" in line:
                temps = line.split('[')[1].split(']')[0].split(',')
                min_temp, max_temp = f"{float(temps[0].strip()):.2f}", f"{float(temps[1].strip()):.2f}"
            if "image  width" in line:
                w = int(line.split(':')[-1].strip())
            if "image height" in line:
                h = int(line.split(':')[-1].strip())

        # 将 Raw RGB 转换为 PNG
        with open(raw_out, "rb") as f:
            img = Image.frombytes("RGB", (w, h), f.read())
        
        final_img_path = os.path.join(TEMP_DIR, f"{task_id}.png")
        img.save(final_img_path)

        if os.path.exists(raw_out): os.remove(raw_out)
        
        return final_img_path, min_temp, max_temp, w, h

    async def render_pdf_worker(self, html_str: str, pdf_path: str):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self.executor, 
            self._sync_render_pdf, html_str, pdf_path
        )

    @staticmethod
    def _sync_render_pdf(html_str: str, pdf_path: str):
        HTML(string=html_str).write_pdf(pdf_path)

    async def process_single_file(self, img_name: str):
        """单个文件的完整处理流水线"""
        async with self.semaphore:
            task_id = uuid.uuid4().hex
            full_path = os.path.join(INPUT_DIR, img_name)
            pdf_path = os.path.join(TEMP_DIR, f"{task_id}.pdf")
            
            try:
                # SDK 处理
                png_path, t_min, t_max, w, h = await self.process_thermal_async(full_path, task_id)
                
                # 元数据提取 (同步)
                meta = self.get_metadata(full_path)
                
                # 渲染 HTML
                html_out = self.template.render(
                    filename=img_name,
                    image_path=pathlib.Path(png_path).absolute().as_uri(),
                    min_temp=t_min, max_temp=t_max,
                    palette_colors=get_palette(self.palette),
                    width=w, height=h,
                    distance=f"{self.distance}", 
                    humidity=f"{self.humidity}", 
                    emissivity=f"{self.emissivity}", 
                    reflection=f"{self.reflection}",
                    ambient=f"{self.ambient}",
                    **meta
                )
                
                # 进程池渲染 PDF
                await self.render_pdf_worker(html_out, pdf_path)
                return pdf_path, png_path, img_name
            except Exception:
                traceback.print_exc()
                return None, None, img_name
            
    async def run(self):
        images = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(('.jpg', '.jpeg'))]
        if not images:
            print("未发现待处理图片")
            return

        print(f"开始处理 {len(images)} 张图片...")
        # 利用 Python 3.6 后 dict 的有序性，保证拼合PDF时保持输入顺序
        results = {img: None for img in images}
        tasks = [asyncio.create_task(self.process_single_file(img)) for img in images]
        
        # 并行执行所有任务
        for task in asyncio.as_completed(tasks):
            result = await task
            if result[0] is not None and result[1] is not None:
                results[result[2]] = (result[0], result[1])
                print(f"完成: {result[2]}")
            else:
                print(f"失败: {result[2]}")
        
        # 筛选有效的 PDF 路径
        pdf_paths = [r[0] for r in results.values()]
        all_temp_imgs = [r[1] for r in results.values()]

        if pdf_paths:
            # 合并 PDF (Fitz 合并极快，同步即可)
            merged_pdf = fitz.open()
            for p in pdf_paths:
                with fitz.open(p) as f:
                    merged_pdf.insert_pdf(f)
            
            output_file = os.path.join(OUTPUT_DIR, f"DJI_Thermal_Report_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf")
            merged_pdf.save(output_file)
            merged_pdf.close()
            print(f"\n报告已生成: {output_file}")

            # 清理所有临时文件
            for f in pdf_paths + all_temp_imgs:
                if os.path.exists(f): os.remove(f)
        
        self.executor.shutdown()

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    gen = ThermalReportGenerator(palette=ThermalPalette.iron_red)
    asyncio.run(gen.run())