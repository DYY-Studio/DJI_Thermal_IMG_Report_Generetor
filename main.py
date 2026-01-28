import os, subprocess, exifread, pathlib, json, traceback, fitz # PyMuPDF
from PIL import Image
from weasyprint import HTML
from jinja2 import Template
from enum import Enum

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
            palette: ThermalPalette = ThermalPalette.iron_red
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
            "aperture": f"{float(get_tag('EXIF FNumber')):.1f}",
            "create_time": get_tag('EXIF DateTimeOriginal'),
            "gps": f"{convert_to_decimal(get_tag('GPS GPSLatitude')):.6f}, {convert_to_decimal(get_tag('GPS GPSLongitude')):.6f}"
        }

    def process_thermal(self, img_path: str,):
        """调用 DJI SDK CLI 处理图像"""
        base_name = os.path.basename(img_path)
        raw_out = os.path.join(TEMP_DIR, f"{base_name}.raw")
        
        # 生成伪彩色图像数据 (RGB 格式)
        cmd = [
            CLI_PATH, 
            "-a", "process", 
            "-s", img_path, 
            "-o", raw_out, 
            "-p", self.palette.name,
            "--distance", str(self.distance),
            "--humidity", str(self.humidity),
            "--emissivity", str(self.emissivity),
            "--ambient", str(self.ambient),
            "--reflection", str(self.reflection),
            "--brightness", str(self.brightness)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 解析 CLI 输出获取自适应温度范围
        # 示例输出: Color bar adaptive range is [25.5, 36.8]
        min_temp, max_temp = "N/A", "N/A"
        for line in result.stdout.split('\n'):
            if "adaptive range" in line:
                temps = line.split('[')[1].split(']')[0].split(',')
                min_temp, max_temp = f"{float(temps[0].strip()):.2f}", f"{float(temps[1].strip()):.2f}"
            if "image  width" in line:
                w = int(line.split(':')[-1].strip())
            if "image height" in line:
                h = int(line.split(':')[-1].strip())

        # 将 Raw RGB 转换为 PNG
        with open(raw_out, "rb") as f:
            raw_data = f.read()
        img = Image.frombytes("RGB", (w, h), raw_data)
        final_img_path = os.path.join(TEMP_DIR, f"{base_name}.png")
        img.save(final_img_path)
        
        return final_img_path, min_temp, max_temp, w, h

    def generate_batch(self):
        pdf_files = []
        images = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(('.jpg', '.jpeg'))]
        
        for idx, img_name in enumerate(images):
            print(f"处理中 ({idx+1}/{len(images)}): {img_name}")
            full_path = os.path.join(INPUT_DIR, img_name)
            
            try:
                # 处理热图
                processed_img, t_min, t_max, w, h = self.process_thermal(full_path)
                # 提取元数据
                meta = self.get_metadata(full_path)
                
                # 渲染 HTML
                html_out = self.template.render(
                    filename=img_name,
                    image_path=pathlib.Path(processed_img).absolute().as_uri(),
                    min_temp=t_min,
                    max_temp=t_max,
                    palette_colors=get_palette(self.palette),
                    width=w, height=h,
                    distance=f"{self.distance}", 
                    humidity=f"{self.humidity}", 
                    emissivity=f"{self.emissivity}", 
                    reflection=f"{self.reflection}",
                    ambient=f"{self.ambient}",
                    **meta
                )
                
                # 导出单页 PDF
                pdf_path = os.path.join(TEMP_DIR, f"{img_name}.pdf")
                HTML(string=html_out).write_pdf(pdf_path)
                pdf_files.append(pdf_path)
                
            except Exception as e:
                print(f"文件 {img_name} 处理失败")
                traceback.print_exc()

        # 最终拼合 PDF 避免内存问题
        if pdf_files:
            merged_pdf = fitz.open()
            for pdf in pdf_files:
                with fitz.open(pdf) as f:
                    merged_pdf.insert_pdf(f)
            merged_pdf.save(os.path.join(OUTPUT_DIR, "Final_Batch_Report.pdf"))
            merged_pdf.close()
            print(f"成功导出合并报告至 {OUTPUT_DIR}")

if __name__ == "__main__":
    gen = ThermalReportGenerator(palette=ThermalPalette.rainbow1)
    gen.generate_batch()