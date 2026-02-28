import shutil, asyncio, locale, subprocess, os, sys
from typing import Literal, Optional

async def check_weasyprint(exe_path: Optional[str] = None, lib_only: bool = False) -> tuple[Literal['lib', 'exe', 'none'], Optional[str]]:
    if not exe_path:
        try:
            from weasyprint import HTML
            HTML(string='<p>test</p>')
            return 'lib', None
        except Exception as e:
            if lib_only:
                return 'none', None
        exe_path = shutil.which("weasyprint")
    
    if exe_path:
        proc = await asyncio.create_subprocess_exec(
            str(exe_path), "--version", 
            stdout = asyncio.subprocess.PIPE,
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
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
            stderr = asyncio.subprocess.PIPE,
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        _, stderr = await proc.communicate()
        if proc.returncode == 0 and stderr.decode(locale.getencoding()).strip().startswith('APP version'):
            return exe_path
    return None

def get_executable_path():
    if getattr(sys, 'frozen', False):
        return os.path.abspath(sys.executable)
    else:
        return os.path.abspath(__file__)