import typer, pathlib, asyncio, os, shutil
from rich.progress import Progress, MofNCompleteColumn, BarColumn, TimeRemainingColumn, TextColumn
from main import ThermalReportGenerator
from typing import Literal, Annotated, Optional

app = typer.Typer(help="A tool to generate report of DJI R-JPEG (Thermal Image) based on [b i]dji_irp[/b i]")

@app.command(help="[b]FAST[/b] will try to locate your [b i]dji_irp[/b i] in $PATH or working dir. Will raise error if cannot find it.")
def fast(
    input_dir: Annotated[
        Optional[pathlib.Path], typer.Argument(help="Directory of your input files (You can also pass multiple --input/-i to input files)")
    ] = None,
    input_files: Annotated[
        Optional[list[pathlib.Path]], typer.Option("--input", "-i", help="Your input files (Alternative)")
    ] = None,
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
    max_workers: Annotated[
        int, typer.Option("--workers", "-ws", min=1, max=32, help='Max workers of concurrent process')
    ] = 4
):
    main(
        cli_path=shutil.which("dji_irp"),
        input_dir=input_dir,
        input_files=input_files,
        output_dir=output_dir,
        temp_dir=temp_dir,
        distance=distance,
        humidity=humidity,
        emissivity=emissivity,
        ambient=ambient,
        reflection=reflection,
        brightness=brightness,
        palette=palette,
        colorbar_width=colorbar_width,
        cbborder=cbborder,
        weasy_lib=weasy_lib,
        max_workers=max_workers
    )

@app.command(help="Require user to pass absolute path to [b i]dji_irp[/b i] executable")
def main(
    cli_path: Annotated[
        pathlib.Path, typer.Argument(help='Absolute path to your complied [b i]dji_irp[/b i] executable')
    ],
    input_dir: Annotated[
        Optional[pathlib.Path], typer.Argument(help="Directory of your input files (You can also pass multiple --input/-i to input files)")
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
    max_workers: Annotated[
        int, typer.Option("--workers", "-ws", min=1, max=32, help='Max workers of concurrent process')
    ] = 4
):
    if not cli_path or not pathlib.Path(cli_path).exists():
        raise FileNotFoundError("Cannot find dji_irp executable")
    if not input_dir and not input_files:
        raise ValueError("No any input")
    if not weasy_lib and not shutil.which('weasyprint'):
        raise FileNotFoundError("Invaild WreayPrint executable path")
    
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    async def __internal_async():
        gen = ThermalReportGenerator(
            input_dir=input_dir,
            output_dir=output_dir,
            temp_dir=temp_dir,
            cli_path=cli_path,
            wreay_path=None if weasy_lib else shutil.which('weasyprint'),
            distance=distance,
            humidity=humidity,
            emissivity=emissivity,
            ambient=ambient,
            reflection=reflection,
            brightness=brightness,
            palette=palette,
            colorbar_width=colorbar_width,
            colorbar_border=cbborder,
            max_workers=max_workers
        )
        with Progress(
            TextColumn("[progress.description]{task.description}"), BarColumn(), MofNCompleteColumn(), TimeRemainingColumn(),
            transient=True
        ) as progress:
            dummy_task = progress.add_task('Please wait...', total=None)
            task = None
            async for i, r in gen.run(input_files if input_files else None):
                if not task:
                    progress.remove_task(dummy_task)
                    task = progress.add_task('Processing...', total=i)
                progress.advance(task, 1)
                if progress.finished:
                    progress.remove_task(task)
                    progress.add_task("PDF Merging...", total=None)
    
    asyncio.run(__internal_async())

if __name__ == "__main__":
    app()