import os, re, datetime, exifread, io, struct, aiofiles
import shutil, uuid, asyncio, pathlib
import json, traceback, locale, xmltodict, fitz # PyMuPDF
from PIL import Image
from jinja2 import Template
from enum import Enum
from concurrent.futures import ProcessPoolExecutor
from typing import AsyncGenerator, Optional, Literal

# 配置路径
LUT_DIR = pathlib.Path(__file__).parent / "luts"

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
    keep = 10

def camel_to_snake(name: str):
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

def get_palette(palette: ThermalPalette):
    palette_json = pathlib.Path(LUT_DIR) / f"lut{palette.value}.json"
    if not palette_json.exists():
        raise FileNotFoundError("Cannot find target LUT file")
    with open(palette_json, mode='r', encoding='utf-8') as f:
        return ', '.join(f"rgb({r},{g},{b})" for r, g, b in json.load(f).__reversed__())

def convert_to_decimal(coords: tuple[float, float, float] | str) -> float:
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
            input_dir: str | pathlib.Path,
            output_dir: str | pathlib.Path,
            temp_dir: str | pathlib.Path,
            cli_path: str | pathlib.Path,
            weasy_path: Optional[str | pathlib.Path] = None,
            distance: Optional[float] = None, # 5.0
            humidity: Optional[float] = None, # 50.0
            emissivity: Optional[float] = None, # 0.95
            ambient: Optional[float] = None, # 25.0
            reflection: Optional[float] = None, # 25.0
            brightness: int = 50,
            palette: ThermalPalette | Literal['white_hot', 'fulgurite', 'iron_red',
    'hot_iron', 'medical', 'arctic', 'rainbow1', 'rainbow2', 'tint', 'black_hot', 'keep'] = ThermalPalette.keep,
            colorbar_width: int = 10,
            colorbar_border: bool = False,
            img_format: Literal['png', 'jpeg'] = 'png',
            png_compress: int = 6,
            jpeg_quality: int = 95,
            jpeg_subsampling: Literal['4:4:4', '4:2:2', '4:2:0'] = '4:4:4',
            jpeg_keepdata: bool = False,
            max_workers: int = 4
        ):
        pathlib.Path(output_dir).mkdir(exist_ok=True)
        pathlib.Path(temp_dir).mkdir(exist_ok=True)
        with open(pathlib.Path(__file__).parent / "template.html", "r", encoding="utf-8") as f:
            self.template = Template(f.read())

        self.distance = distance
        self.humidity = humidity
        self.emissivity = emissivity
        self.ambient = ambient
        self.reflection = reflection
        self.brightness = brightness
        self.palette = palette if isinstance(palette, ThermalPalette) else ThermalPalette.__members__.get(palette, ThermalPalette.iron_red)
        self.colorbar_width = colorbar_width
        self.border = "border: 1px solid #000;" if colorbar_border else ""
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.cli_path = cli_path
        self.temp_dir = temp_dir
        self.weasy_path = weasy_path

        self.img_format = img_format
        self.png_compress = png_compress
        self.jpeg_quality = jpeg_quality
        self.jpeg_subsampling = jpeg_subsampling
        self.jpeg_keepdata = jpeg_keepdata

        self.semaphore = asyncio.Semaphore(max_workers)
        self.executor = ProcessPoolExecutor(max_workers=max_workers)

    @staticmethod
    def get_jpeg_app_segments(stream: io.BufferedIOBase, pos_only: bool = False):
        stream.seek(0)
        segments: dict[int | str, list[bytes]] = {'pos': dict()}
        
        # 验证 SOI (0xFFD8)
        if stream.read(2) != b'\xff\xd8':
            raise ValueError("不是有效的 JPEG 文件")

        while True:
            # 读取 4 个字节: [Marker (2字节)] + [Length (2字节)]
            header = stream.read(4)
            if len(header) < 4:
                break
                
            marker = header[0:2]

            # SOS (0xFFDA)，元数据结束
            if marker == b'\xff\xda':
                stream.seek(-4, 1)
                break

            # 解包大端序长度
            length = struct.unpack(">H", header[2:4])[0]
            
            # JPEG 段长度包含长度字段自身的 2 字节
            content = stream.read(length - 2)
            
            # 如果是 APPn 段 (0xFFE0 - 0xFFEF)
            if 0xE0 <= marker[1] <= 0xEF:
                if not pos_only:
                    if marker[1] not in segments:
                        segments[marker[1]] = []
                    # 存储完整的段（包含 Marker 和 Length）
                    segments[marker[1]].append(marker + header[2:4] + content)
                segments['pos'][marker[1]] = (stream.tell() - length - 2, stream.tell())
                
        return segments

    def get_metadata(self, img_path: str | pathlib.Path):
        """从 APP1 Marker 提取元数据"""
        xmp = ''
        exif = b''
        app_segments: dict[str, list[bytes]] = None
        with open(img_path, mode='rb') as f:
            tags = exifread.process_file(f, builtin_types = True)
            f.seek(0)
            with Image.open(f) as img:
                exif = img.info.get('exif', b'')
                if (xmp := img.info.get('xmp', '')):
                    tags.update(xmltodict.parse(xmp)['x:xmpmeta']['rdf:RDF']['rdf:Description'])
                else:
                    return None
            app_segments = self.get_jpeg_app_segments(f)

        if not tags.get("@drone-dji:ImageSource", "") == "InfraredCamera":
            return None
            
        def get_tag(key: str):
            result = str(tags.get(key, "N/A"))
            return result
        
        gps = (
            convert_to_decimal(get_tag('GPS GPSLatitude')),
            convert_to_decimal(get_tag('GPS GPSLongitude')),
            tags.get('GPS GPSAltitude', 0.0)
        )

        return {
            "model": get_tag('@tiff:Model'),
            "sn": get_tag('@drone-dji:DroneSerialNumber'),
            "focal_length": get_tag('EXIF FocalLength'),
            "aperture": f"{float(get_tag('EXIF FNumber')):.1f}" if get_tag('EXIF FNumber') != "N/A" else "N/A",
            "create_time": datetime.datetime.fromisoformat(get_tag('@xmp:CreateDate')).strftime("%Y/%m/%d %H:%M:%S"),
            "gps": f"{gps[0]:.6f}, {gps[1]:.6f}",
            "palette": camel_to_snake(get_tag('EXIF ImageDescription')),
            "raw_gps": gps,
            "raw_xmp": xmp,
            "raw_exif": exif,
            "raw_segments": app_segments
        }
    
    async def get_default_settings(self, img_path: str | pathlib.Path) -> Optional[dict[str, float]]:
        default_vals: Optional[dict[str, float]] = None

        # 如果有任何选项没有定义，则空跑一轮获取默认值
        if not all((self.distance, self.humidity, self.emissivity, self.ambient, self.reflection)):
            default_vals = dict()
            cmd = [
                "-a", "measure", "-s", str(img_path), "-o", "NUL" if os.name == 'nt' else "/dev/null", 
            ]+ \
            (["--distance", "1.0",] if not self.distance else []) + \
            (["--humidity", "20.0",] if not self.humidity else []) + \
            (["--emissivity", "0.10",] if not self.emissivity else []) + \
            (["--ambient", "0.0",] if not self.ambient else []) + \
            (["--reflection", "0.0",] if not self.reflection else [])
            proc = await asyncio.create_subprocess_exec(
                self.cli_path, *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            result = stdout.decode(locale.getencoding())
            for line in result.split('\n'):
                if (matched := re.match(r'Change (\w+) from ([+-]?(?:\d+\.?\d*|\.\d+)) to [+-]?(?:\d+\.?\d*|\.\d+)', line)):
                    param, default_val = matched.groups()
                    default_vals[param.split('_')[0]] = float(default_val)

        return default_vals

    async def measure_thermal_async(self, 
            img_path: str | pathlib.Path, 
            task_id: str, 
            gps: tuple[float, float, float],
            xmp: str,
            exif: bytes,
        ):
        raw_out = pathlib.Path(self.temp_dir) / f"{task_id}.raw"
        
        cmd = [
            "-a", "measure", "--measurefmt", "float32", "-s", str(img_path), "-o", raw_out, 
        ]

        proc = await asyncio.create_subprocess_exec(
            self.cli_path, *cmd,
            stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if not proc.returncode == 0 or not raw_out.exists():
            return None
        
        result = stdout.decode(locale.getencoding())
        w, h = 0, 0
        for line in result.split('\n'):
            if "image  width" in line:
                w = int(line.split(':')[-1].strip())
            if "image height" in line:
                h = int(line.split(':')[-1].strip())
        
        import numpy as np
        async with aiofiles.open(raw_out, mode='rb') as f:
            temp_data = np.frombuffer(await f.read(), dtype=np.float32).reshape((h, w))

        # gps: (lat, lon, alt)
        pixel_scale = (1.0, 1.0, 0.0) 
        tiepoint = (0.0, 0.0, 0.0, gps[1], gps[0], gps[2])

        geo_keys = [
            1, 1, 0, 3,  # 版本 1.1.0, 3 个 Key
            # Key 1: GTModelTypeGeoKey (1024) = GeographicLatLong (2)
            1024, 0, 1, 2,
            # Key 2: GTRasterTypeGeoKey (1025) = RasterPixelIsArea (1)
            1025, 0, 1, 1,
            # Key 3: GeographicTypeGeoKey (2048) = WGS 84 (4326)
            2048, 0, 1, 4326
        ]

        extra_tags = [
            (33550, 'd', 3, pixel_scale, False), # ModelPixelScaleTag
            (33922, 'd', 6, tiepoint, False),    # ModelTiepointTag
            (34735, 'H', len(geo_keys), geo_keys, True)
        ]

        final_img_path = pathlib.Path(self.temp_dir) / f"{task_id}.tif"

        import tifffile
        cache_bytesIO = io.BytesIO()
        await asyncio.to_thread(
            tifffile.imwrite,
            cache_bytesIO,
            temp_data,
            photometric=tifffile.PHOTOMETRIC.MINISBLACK,
            # description=xmp,
            metadata=None,
            extratags=extra_tags,
        )

        cache_bytesIO_2 = io.BytesIO()
        cache_bytesIO.seek(0)
        with Image.open(cache_bytesIO) as img:
            img.save(cache_bytesIO_2, format='tiff', xmp=xmp, exif=exif)
        del cache_bytesIO

        async with aiofiles.open(final_img_path, mode='wb') as f:
            await f.write(cache_bytesIO_2.getbuffer())
        del cache_bytesIO_2

        raw_out.unlink(missing_ok=True)

        return final_img_path if final_img_path.exists() else None

    async def process_thermal_async(self, img_path: str | pathlib.Path, task_id: str, app_segments: Optional[dict[int, list[str]]] = None):
        """调用 DJI SDK CLI 处理图像"""
        raw_out = pathlib.Path(self.temp_dir) / f"{task_id}.raw"
        
        # 生成伪彩色图像数据 (RGB 格式)
        cmd = [
            "-a", "process", "-s", str(img_path), "-o", raw_out, 
            "--brightness", str(self.brightness),
        ] + \
        (["--distance", str(self.distance),] if self.distance else []) + \
        (["--humidity", str(self.humidity),] if self.humidity else []) + \
        (["--emissivity", str(self.emissivity),] if self.emissivity else []) + \
        (["--ambient", str(self.ambient),] if self.ambient else []) + \
        (["--reflection", str(self.reflection),] if self.reflection else []) + \
        (["-p", self.palette.name,] if self.palette != ThermalPalette.keep else [])

        proc = await asyncio.create_subprocess_exec(
            self.cli_path, *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        result = stdout.decode(locale.getencoding())
        
        # 解析 CLI 输出获取自适应温度范围
        # 示例输出: Color bar adaptive range is [25.5, 36.8]
        min_temp, max_temp, w, h = "N/A", "N/A", 0, 0
        for line in result.split('\n'):
            if "adaptive range" in line:
                temps = line.split('[')[1].split(']')[0].split(',')
                min_temp, max_temp = f"{float(temps[0].strip()):.1f}", f"{float(temps[1].strip()):.1f}"
            if "image  width" in line:
                w = int(line.split(':')[-1].strip())
            if "image height" in line:
                h = int(line.split(':')[-1].strip())

        # 将 Raw RGB 转换指定格式
        async with aiofiles.open(raw_out, "rb") as f:
            img = Image.frombytes("RGB", (w, h), await f.read())
        
        final_img_path = pathlib.Path(self.temp_dir) / f"{task_id}.{self.img_format}"

        params = {'compress_level': self.png_compress}
        if self.img_format == 'jpeg':
            params = {
                'quality': self.jpeg_quality,
                'subsampling': self.jpeg_subsampling
            }
        if self.img_format == 'jpeg' and app_segments and 0xE1 in app_segments:
            for seg in app_segments[0xE1]:
                if seg[4:].startswith(b'Exif'):
                    params['exif'] = seg[4:]
                elif seg[4:].startswith(b'http://ns.adobe.com/xap/1.0/'):
                    params['xmp'] = seg[4:]

        with io.BytesIO() as stream:
            await asyncio.to_thread(img.save, stream, self.img_format, **params)
            if app_segments and self.img_format == 'jpeg':
                new_pos: dict[int, tuple[int, int]] = self.get_jpeg_app_segments(stream, pos_only=True)['pos']
                app_end_pos = new_pos.get(0xE1, new_pos.get(0xE0, (0, stream.tell())))[1]
                stream.seek(0)
                async with aiofiles.open(final_img_path, mode='wb') as f:
                    await f.write(stream.read(app_end_pos))
                    for marker, segs in app_segments.items():
                        if marker != 'pos' and (marker & 0xF) > 1:
                            for seg in segs:
                                await f.write(seg)
                    await f.write(stream.read())
            else:
                async with aiofiles.open(final_img_path, mode='wb') as f:
                    await f.write(stream.getvalue())

        raw_out.unlink(missing_ok=True)
        
        return final_img_path, min_temp, max_temp, w, h

    async def render_pdf_worker(self, html_str: str, pdf_path: str):
        if not self.weasy_path:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self.executor, 
                self._sync_render_pdf, html_str, pdf_path
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                str(self.weasy_path), "-", str(pdf_path),
                stdin=asyncio.subprocess.PIPE
            )
            await proc.communicate(html_str.encode('utf-8'))

    @staticmethod
    def _sync_render_pdf(html_str: str, pdf_path: str):
        try:
            from weasyprint import HTML
            HTML(string=html_str).write_pdf(pdf_path)
        except ImportError:
            print("错误: 未找到 weasyprint 库")
            raise

    async def process_single_file(self, img_name: str, work: Literal['report', 'palette', 'geotiff'] = 'report'):
        """单个文件的完整处理流水线"""
        async with self.semaphore:
            task_id = uuid.uuid4().hex
            if not pathlib.Path(img_name).is_absolute():
                full_path = pathlib.Path(self.input_dir) / img_name
            else:
                full_path = pathlib.Path(img_name)
            pdf_path = pathlib.Path(self.temp_dir) / f"{task_id}.pdf"
            
            try:
                # 元数据提取 (同步)
                meta = self.get_metadata(full_path)
                if meta is None:
                    return None, None, img_name, "No InfraredCamera Image / Cannot find DJI XMP"
                
                if work == 'geotiff':
                    tiff_path = await self.measure_thermal_async(full_path, task_id, meta['raw_gps'], meta['raw_xmp'], meta['raw_exif'])
                    return None, tiff_path, img_name, None
            
                # SDK 处理
                png_path, t_min, t_max, w, h = await self.process_thermal_async(
                    full_path,
                    task_id, 
                    meta['raw_segments'] if work == 'palette' else None
                )

                if work == 'palette':
                    return None, png_path, img_name, None
                
                for key in [k for k in meta if k.startswith('raw_')]:
                    if key in meta: meta.pop(key)
                
                default_vals = await self.get_default_settings(full_path) or dict()

                # 渲染 HTML
                html_out = self.template.render(
                    filename=pathlib.Path(img_name).name,
                    image_path=pathlib.Path(png_path).absolute().as_uri(),
                    min_temp=t_min, max_temp=t_max,
                    palette_colors = get_palette(
                        self.palette 
                        if self.palette != ThermalPalette.keep
                        else ThermalPalette.__members__.get(
                            meta['palette'], 
                            ThermalPalette.iron_red
                        )
                    ),
                    width=w, height=h,
                    distance=f"{self.distance if self.distance else default_vals.get('distance', 0.0)}", 
                    humidity=f"{self.humidity if self.humidity else default_vals.get('humidity', 0.0)}", 
                    emissivity=f"{self.emissivity if self.emissivity else default_vals.get('emissivity', 0.0)}", 
                    reflection=f"{self.reflection if self.reflection else default_vals.get('reflection', 0.0)}",
                    ambient=f"{self.ambient if self.ambient else default_vals.get('ambient', 0.0)}",
                    colorbar_width = self.colorbar_width,
                    colorbar_border = self.border,
                    **meta
                )
                
                # 进程池渲染 PDF
                await self.render_pdf_worker(html_out, pdf_path)
                return pdf_path, png_path, img_name, None
            except Exception as e:
                traceback.print_exc()
                return None, None, img_name, e

    async def run_geotiff(self, image_abs_paths: Optional[list[str | pathlib.Path]] = None) -> AsyncGenerator[tuple[int, dict], None]:
        if not image_abs_paths:
            images = [(pathlib.Path(self.input_dir) / f).absolute() for f in os.listdir(str(self.input_dir)) if f.lower().endswith(('.jpg', '.jpeg'))]
        else:
            images = []
            for f in image_abs_paths:
                if not pathlib.Path(f).is_absolute():
                    raise ValueError("Path in file list must be absolute!")
                if str(f).lower().endswith(('.jpg', '.jpeg')):
                    images.append(str(f))
        if not images:
            print("未发现待处理图片")
            return
        
        self.output_dir = pathlib.Path(self.output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        tasks = [asyncio.create_task(self.process_single_file(img, work='geotiff')) for img in images]
        for task in asyncio.as_completed(tasks):
            result = await task
            if result[0] is None and result[1] is not None:
                output_path = pathlib.Path(self.output_dir) / pathlib.Path(result[2]).with_suffix(f".{self.img_format}").name
                filename_out_ext = output_path.with_suffix('').name
                i = 1
                while output_path.exists():
                    output_path = output_path.with_name(f'{filename_out_ext}_{i}.{self.img_format}')
                    i += 1
                try:
                    shutil.move(result[1], output_path)
                except Exception as e:
                    pathlib.Path(result[1]).unlink(missing_ok=True)
                    yield len(images), {'success': False, 'message': f"失败: {result[2]} ({e})"}
                    continue
                while output_path.exists():
                    output_path = output_path.with_name(f'{filename_out_ext}_{i}.tif')
                    i += 1
                yield len(images), {'success': True, 'message': f"完成: {output_path}"}
            else:
                yield len(images), {'success': False, 'message': f"失败: {result[2]} ({result[3]})"}

        self.executor.shutdown()

    async def run_palette_change(self, 
        image_abs_paths: Optional[list[str | pathlib.Path]] = None
    ) -> AsyncGenerator[tuple[int, dict], None]:
        if not image_abs_paths:
            images = [(pathlib.Path(self.input_dir) / f).absolute() for f in os.listdir(str(self.input_dir)) if f.lower().endswith(('.jpg', '.jpeg'))]
        else:
            images = []
            for f in image_abs_paths:
                if not pathlib.Path(f).is_absolute():
                    raise ValueError("Path in file list must be absolute!")
                if str(f).lower().endswith(('.jpg', '.jpeg')):
                    images.append(str(f))
        if not images:
            print("未发现待处理图片")
            return
        
        self.output_dir = pathlib.Path(self.output_dir) / self.palette.name
        self.output_dir.mkdir(exist_ok=True)
        
        tasks = [asyncio.create_task(self.process_single_file(img, work='palette')) for img in images]
        for task in asyncio.as_completed(tasks):
            result = await task
            if result[0] is None and result[1] is not None:
                output_path = pathlib.Path(self.output_dir) / pathlib.Path(result[2]).with_suffix(f".{self.img_format}").name
                filename_out_ext = output_path.with_suffix('').name
                i = 1
                while output_path.exists():
                    output_path = output_path.with_name(f'{filename_out_ext}_{i}.{self.img_format}')
                    i += 1
                try:
                    shutil.move(result[1], output_path)
                except Exception as e:
                    pathlib.Path(result[1]).unlink(missing_ok=True)
                    yield len(images), {'success': False, 'message': f"失败: {result[2]} ({e})"}
                    continue
                yield len(images), {'success': True, 'message': f"完成: {output_path}"}
            else:
                yield len(images), {'success': False, 'message': f"失败: {result[2]} ({result[3]})"}

        self.executor.shutdown()
    
    async def run(self, image_abs_paths: Optional[list[str | pathlib.Path]] = None) -> AsyncGenerator[tuple[int, dict], None]:
        if not image_abs_paths:
            images = [(pathlib.Path(self.input_dir) / f).absolute() for f in os.listdir(str(self.input_dir)) if f.lower().endswith(('.jpg', '.jpeg'))]
        else:
            images = []
            for f in image_abs_paths:
                if not pathlib.Path(f).is_absolute():
                    raise ValueError("Path in file list must be absolute!")
                if str(f).lower().endswith(('.jpg', '.jpeg')):
                    images.append(str(f))
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
                yield len(images), {'success': True, 'message': f"完成: {result[2]}"}
            else:
                yield len(images), {'success': False, 'message': f"失败: {result[2]} ({result[3]})"}
        
        # 筛选有效的 PDF 路径
        pdf_paths = [r[0] for r in results.values() if r]
        all_temp_imgs = [r[1] for r in results.values() if r]

        if pdf_paths:
            # 合并 PDF (Fitz 合并极快，同步即可)
            merged_pdf = fitz.open()
            for p in pdf_paths:
                with fitz.open(p) as f:
                    merged_pdf.insert_pdf(f)
            
            output_file = pathlib.Path(self.output_dir) / f"DJI_Thermal_Report_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf"
            merged_pdf.save(output_file)
            merged_pdf.close()
            print(f"\n报告已生成: {output_file}")

            # 清理所有临时文件
            for f in pdf_paths + all_temp_imgs:
                pathlib.Path(f).unlink(missing_ok=True)
        
        self.executor.shutdown()

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    gen = ThermalReportGenerator(
        input_dir="./input_images",
        output_dir="./reports",
        temp_dir="./temps",
        cli_path=r"D:\Test\dji_thermal_sdk_v1.8_20250829\utility\bin\windows\release_x64\dji_irp.exe",
        palette=ThermalPalette.iron_red,
        # img_format='jpeg'
    )
    async def _internal():
        async for i in gen.run():
            pass
    asyncio.run(_internal())