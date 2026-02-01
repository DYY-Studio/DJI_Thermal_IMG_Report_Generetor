import typer, pathlib, asyncio, os, shutil
from rich.progress import Progress, MofNCompleteColumn, BarColumn, TimeRemainingColumn, TextColumn
from generator import ThermalReportGenerator
from typing import Literal, Annotated, Optional

app = typer.Typer(help="A tool to generate report of DJI R-JPEG (Thermal Image) based on [b i]dji_irp[/b i]")

@app.command(help="Generate thermal image reports. Auto detect [b i]dji_irp[/b i] if it's in [b]$PATH[/b] or working dir.")
def report(
    input_dir: Annotated[
        Optional[pathlib.Path], typer.Argument(help="Directory of your input files (You can also pass multiple --input/-i to input files)")
    ] = None,
    cli_path: Annotated[
        pathlib.Path, typer.Option("--dji", "-d", help='Absolute path to your complied [b i]dji_irp[/b i] executable')
    ] = None,
    input_files: Annotated[
        list[pathlib.Path], typer.Option("--input", "-i", help="Your input files (Alternative)")
    ] = [],
    output_dir: Annotated[
        pathlib.Path, typer.Option("--output", "-o", help="Directory for saving PDFs")
    ] = pathlib.Path('./reports'),
    temp_dir: Annotated[
        pathlib.Path, typer.Option("--temp", "-t", help="Directory for temporary RAW files")
    ] = pathlib.Path('./temps'),
    distance: Annotated[
        float, typer.Option("--distance", "-dis", min=1.0, max=25.0)
    ] = 5.0,
    humidity: Annotated[
        float, typer.Option("--humidity", "-hum", min=20.0, max=100.0)
    ] = 50.0,
    emissivity: Annotated[
        float, typer.Option("--emissivity", "-emi", min=0.10, max=1.00)
    ] = 0.95,
    ambient: Annotated[
        float, typer.Option("--ambient", "-amb", min=-40.0, max=80.0)
    ] = 25.0,
    reflection: Annotated[
        float, typer.Option("--reflection", "-ref", min=-40.0, max=500.0)
    ] = 25.0,
    brightness: Annotated[
        int, typer.Option("--brightness", "-bri", min=0, max=100)
    ] = 50,
    palette: Annotated[
        Literal['white_hot', 'fulgurite', 'iron_red', 
                'hot_iron', 'medical', 'arctic', 'rainbow1', 
                'rainbow2', 'tint', 'black_hot'], 
        typer.Option("--palette", "-p")
    ] = 'iron_red',
    colorbar_width: Annotated[
        int, typer.Option("--cbwidth", "-cbw", min=1, max=100, help='Width of Temperature-Color Bar')
    ] = 10,
    cbborder: Annotated[
        bool, typer.Option(help='Whether to show border of Temperature-Color Bar')
    ] = False,
    weasy_lib: Annotated[
        bool, typer.Option(help='Use WeasyPrint executable instead of Library in Windows')
    ] = False if os.name == 'nt' else True,
    img_format: Annotated[
        Literal['png', 'jpeg'], typer.Option('--img-format', '--iformat', help='Choose JPEG may lead to smaller PDF')
    ] = 'png',
    png_compress: Annotated[
        int, typer.Option('--png-compress', '-pcom', help='higher = smaller but slower', max=9, min=0)
    ] = 6,
    jpeg_quality: Annotated[
        int, typer.Option('--jpeg-quality', '-jqua',help='higher (<= 95) = bigger and better', max=100, min=0)
    ] = 95,
    jpeg_subsampling: Annotated[
        Literal['4:4:4', '4:2:2', '4:2:0', '0', '1', '2'], 
        typer.Option('--jpeg-subsampling', '-jsub', help='0 = 4:4:4, 1 = 4:2:2, 2 = 4:2:0')
    ] = '4:4:4',
    max_workers: Annotated[
        int, typer.Option("--workers", "-ws", min=1, help='Max workers of concurrent process')
    ] = 4
):
    if not cli_path:
        cli_path = shutil.which("dji_irp")
    if not cli_path or not pathlib.Path(cli_path).exists():
        raise FileNotFoundError("Cannot find dji_irp executable")
    if not input_dir and not input_files:
        raise ValueError("No any input")
    if not weasy_lib and not shutil.which('weasyprint'):
        raise FileNotFoundError("Invaild WreayPrint executable path")
    
    if ':' not in jpeg_subsampling:
        jpeg_subsampling = {
            '0': '4:4:4',
            '1': '4:2:2',
            '2': '4:2:0'
        }[jpeg_subsampling]
    
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    async def __internal_async():
        gen = ThermalReportGenerator(
            input_dir=input_dir,
            output_dir=output_dir,
            temp_dir=temp_dir,
            cli_path=cli_path,
            weasy_path=None if weasy_lib else shutil.which('weasyprint'),
            distance=distance,
            humidity=humidity,
            emissivity=emissivity,
            ambient=ambient,
            reflection=reflection,
            brightness=brightness,
            palette=palette,
            colorbar_width=colorbar_width,
            colorbar_border=cbborder,
            img_format=img_format,
            png_compress=png_compress,
            jpeg_quality=jpeg_quality,
            jpeg_subsampling=jpeg_subsampling,
            max_workers=max_workers
        )
        with Progress(
            TextColumn("[progress.description]{task.description}"), BarColumn(), MofNCompleteColumn(), TimeRemainingColumn(),
            transient=True
        ) as progress:
            dummy_task = progress.add_task('Please wait...', total=None)
            task = None
            async for i, r in gen.run(input_files if input_files else None):
                print(r['message'])
                if not task:
                    progress.remove_task(dummy_task)
                    task = progress.add_task('Processing...', total=i)
                progress.advance(task, 1)
                if progress.finished:
                    progress.remove_task(task)
                    progress.add_task("PDF Merging...", total=None)
    
    asyncio.run(__internal_async())

@app.command(help="Change the palette of thremal images in batch. Auto detect [b i]dji_irp[/b i] if it's in [b]$PATH[/b] or working dir.")
def palette(
    input_dir: Annotated[
        Optional[pathlib.Path], typer.Argument(help="Directory of your input files (You can also pass multiple --input/-i to input files)")
    ] = None,
    cli_path: Annotated[
        pathlib.Path, typer.Option("--dji", "-d", help='Absolute path to your complied [b i]dji_irp[/b i] executable')
    ] = None,
    input_files: Annotated[
        list[pathlib.Path], typer.Option("--input", "-i", help="Your input files (Alternative)")
    ] = [],
    output_dir: Annotated[
        pathlib.Path, typer.Option("--output", "-o", help="Directory for saving PDFs")
    ] = pathlib.Path('./palette_changed'),
    palette: Annotated[
        Literal['white_hot', 'fulgurite', 'iron_red', 
                'hot_iron', 'medical', 'arctic', 'rainbow1', 
                'rainbow2', 'tint', 'black_hot'], 
        typer.Option("--palette", "-p")
    ] = 'iron_red',
    overwrite: Annotated[
        bool, typer.Option("--overwrite", "-ow", help="Overwrite exist output file or rename new file")
    ] = False,
    img_format: Annotated[
        Literal['png', 'jpeg'], typer.Option('--img-format', '--iformat', help='Choose JPEG may lead to smaller PDF')
    ] = 'png',
    png_compress: Annotated[
        int, typer.Option('--png-compress', '-pcom', help='higher = smaller but slower', max=9, min=0)
    ] = 6,
    jpeg_quality: Annotated[
        int, typer.Option('--jpeg-quality', '-jqua',help='higher (<= 95) = bigger and better', max=100, min=0)
    ] = 95,
    jpeg_subsampling: Annotated[
        Literal['4:4:4', '4:2:2', '4:2:0', '0', '1', '2'], 
        typer.Option('--jpeg-subsampling', '-jsub', help='0 = 4:4:4, 1 = 4:2:2, 2 = 4:2:0')
    ] = '4:4:4',
    max_workers: Annotated[
        int, typer.Option("--workers", "-ws", min=1, max=32, help='Max workers of concurrent process')
    ] = 4
):
    if not cli_path:
        cli_path = shutil.which('dji_irp')
    if not cli_path or not pathlib.Path(cli_path).exists():
        raise FileNotFoundError("Cannot find dji_irp executable")
    
    if ':' not in jpeg_subsampling:
        jpeg_subsampling = {
            '0': '4:4:4',
            '1': '4:2:2',
            '2': '4:2:0'
        }[jpeg_subsampling]
    
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    async def __internal_async():
        gen = ThermalReportGenerator(
            input_dir=input_dir,
            output_dir=output_dir,
            temp_dir=pathlib.Path('./temps'),
            cli_path=cli_path,
            palette=palette,
            max_workers=max_workers,
            overwrite=overwrite,
            img_format=img_format,
            png_compress=png_compress,
            jpeg_quality=jpeg_quality,
            jpeg_subsampling=jpeg_subsampling
        )
        with Progress(
            TextColumn("[progress.description]{task.description}"), BarColumn(), MofNCompleteColumn(), TimeRemainingColumn(),
            transient=True
        ) as progress:
            dummy_task = progress.add_task('Please wait...', total=None)
            task = None
            async for i, r in gen.run_palette_change(input_files if input_files else None):
                print(r['message'])
                if not task:
                    progress.remove_task(dummy_task)
                    task = progress.add_task('Processing...', total=i)
                progress.advance(task, 1)

    asyncio.run(__internal_async())

if __name__ == "__main__":
    app()