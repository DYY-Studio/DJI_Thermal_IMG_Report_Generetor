import shutil, asyncio, locale
from typing import Literal, Optional

async def check_weasyprint(exe_path: Optional[str] = None, lib_only: bool = False) -> tuple[Literal['lib', 'exe', 'none'], Optional[str]]:
    try:
        from weasyprint import HTML
        HTML(string='<p>test</p>')
        return 'lib', None
    except (ImportError, OSError) as e:
        if lib_only:
            return 'none', None

    if not exe_path:
        exe_path = shutil.which("weasyprint")
    if exe_path:
        proc = await asyncio.create_subprocess_exec(
            str(exe_path), "--version", 
            stdout = asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0 and stdout.decode(locale.getencoding()).strip().startswith('WeasyPrint version'):
            return 'exe', exe_path
    return 'none', None

async def check_dji_irp(exe_path: Optional[str] = None) -> Optional[str]:
    if not exe_path:
        exe_path = shutil.which('dji_irp')

    if exe_path:
        proc = await asyncio.create_subprocess_exec(
            str(exe_path), "--version", 
            stderr = asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        if proc.returncode == 0 and stderr.decode(locale.getencoding()).strip().startswith('APP version'):
            return exe_path
    return None