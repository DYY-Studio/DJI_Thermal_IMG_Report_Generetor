import flet as ft, pathlib, shutil, os, platform, asyncio
from components.spin_box import SpinBox
from components.gallery_item import GalleryItem
from generator import ThermalReportGenerator
from utils import check_weasyprint, check_dji_irp

files_in_grid: dict[str, bool] = dict()
settings: dict[str, int | float | str | None] = {
    'temp_dir': str(pathlib.Path(__file__).parent / 'temps'),
    'distance': 5.0,
    'humidity': 50.0,
    'emissivity': 0.95,
    'ambient': 25.0,
    'reflection': 25.0,
    'brightness': 50,
    'colorbar_width': 10,
    'colorbar_border': False,
    'max_workers': 4,
    'palette': 'iron_red',
    'img_format': 'png',
    'png_compress': 6,
    'jpeg_quality': 95,
    'jpeg_subsampling': '4:4:4',
    'jpeg_keepdata': False
}
preset_overwrite: dict[str, bool] = {
    'distance': False,
    'humidity': False,
    'emissivity': False,
    'ambient': False,
    'reflection': False,
    'palette': False,
}
font_preset = {
    "Windows": "Microsoft YaHei",
    "Linux": "Noto Sans CJK SC",
    "Darwin": "PingFang SC"
}
is_running = False

def SettingRow(title: str, subtitle: str, control: ft.Control, visible: bool = True):
    return ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text(title, size=16, weight=ft.FontWeight.W_500),
                ft.Text(subtitle, size=12, color=ft.Colors.OUTLINE),
            ], expand=True, spacing=2),
            # 这里放置控制组件（Switch 或 SpinBox）
            ft.Container(content=control, alignment=ft.Alignment.CENTER_RIGHT)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=ft.Padding.symmetric(vertical=10, horizontal=15),
        border=ft.Border.only(bottom=ft.BorderSide(0.5, ft.Colors.OUTLINE_VARIANT)),
        visible=visible
    )

async def main(page: ft.Page):
    page.title = "DJI Thermal Image Report Generator"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.theme = ft.Theme(font_family=font_preset.get(platform.system(), "sans-serif"))
    page.window.prevent_close = True

    weasyprint_method, which_weasyprint = await check_weasyprint()

    dji_irp_textfield = ft.TextField(shutil.which('dji_irp'), max_lines=1, expand=True, read_only=True)
    weasyprint_textfield = ft.TextField(
        which_weasyprint if which_weasyprint else '',
        max_lines=1, 
        expand=True,
        read_only=True
    )

    async def read_config():
        global settings, preset_overwrite
        import json
        config_path = pathlib.Path(__file__).parent / 'dji_timgrg_config.json'
        if not config_path.exists():
            return
        try:
            with open(config_path, mode='r', encoding='utf-8') as f:
                all_config: dict = json.load(f)
            if not isinstance(all_config, dict):
                return
            
            for k, v in all_config.items():
                if k == 'cli_path':
                    if (await check_dji_irp(v)) is not None:
                        dji_irp_textfield.value = v
                        dji_irp_textfield.update()
                elif k == 'weasy_path':
                    if weasyprint_method == 'none':
                        if (await check_weasyprint(v))[0] == 'exe':
                            weasyprint_textfield.value = v
                            weasyprint_textfield.update()
                elif k in settings and k != 'temp_dir' and isinstance(v, type(settings[k])):
                    settings[k] = v
        except Exception as e:
            pass

        config_path2 = pathlib.Path(__file__).parent / 'dji_timgrg_config2.json'
        try:
            with open(config_path2, mode='r', encoding='utf-8') as f:
                preset_overwrite_cache: dict = json.load(f)
            if not isinstance(preset_overwrite_cache, dict):
                return
            
            for k, v in preset_overwrite_cache.items():
                if k in preset_overwrite and isinstance(v, bool):
                    preset_overwrite[k] = v
        except Exception as e:
            pass

    await read_config()

    image_grid = ft.GridView(
        expand=True,
        runs_count=5,
        max_extent=150,
        child_aspect_ratio=1,
        spacing=5,
        run_spacing=5,
    )
    image_grid_none = ft.Text(
        "还没有添加图像",
        text_align=ft.TextAlign.CENTER,
        expand=True,
    )

    image_grid_container = ft.Container(
        image_grid_none,
        expand=True,
        alignment=ft.Alignment.CENTER
    )

    def on_settings_value_change(value, key: str):
        global settings
        settings[key] = value
        if key == 'img_format':
            for k, v in img_settings.items():
                v.visible = k.startswith(value)
                v.update()
            # settings_view.update()

    def on_preset_overwrite_value_change(value, key: str):
        global preset_overwrite
        preset_overwrite[key] = value

    palette_dropdown = ft.Dropdown(
        value='iron_red',
        options=[
            ft.DropdownOption('white_hot'),
            ft.DropdownOption('fulgurite'), 
            ft.DropdownOption('iron_red'), 
            ft.DropdownOption('hot_iron'), 
            ft.DropdownOption('medical'), 
            ft.DropdownOption('arctic'), 
            ft.DropdownOption('rainbow1'), 
            ft.DropdownOption('rainbow2'), 
            ft.DropdownOption('tint'), 
            ft.DropdownOption('black_hot')
        ],
        text_size=13,
        height=44,
        width=140,
        editable=False,
        on_select=lambda _: on_settings_value_change(palette_dropdown.value, 'palette')
    )

    imgformat_dropdown = ft.Dropdown(
        value='png',
        options=[
            ft.DropdownOption('png'),
            ft.DropdownOption('jpeg'), 
        ],
        text_size=13,
        height=44,
        width=140,
        editable=False,
        on_select=lambda _: on_settings_value_change(imgformat_dropdown.value, 'img_format')
    )

    subsampling_dropdown = ft.Dropdown(
        value='4:4:4',
        options=[
            ft.DropdownOption('4:4:4'),
            ft.DropdownOption('4:2:2'), 
            ft.DropdownOption('4:2:0'), 
        ],
        text_size=13,
        height=44,
        width=140,
        editable=False,
        on_select=lambda _: on_settings_value_change(subsampling_dropdown.value, 'jpeg_subsampling')
    )

    img_settings = {
        'jpeg_quality': SettingRow(
            'JPEG Quality',
            'Higher Better and Bigger. Effective when lower than 96',
            SpinBox(
                value=settings['jpeg_quality'],
                min_val=0,
                max_val=100,
                precision=0,
                step=1,
                on_change=lambda v: on_settings_value_change(int(float(v.data)), 'jpeg_quality')
            ),
            visible=imgformat_dropdown.value == 'jpeg'
        ),
        'jpeg_subsampling': SettingRow(
            'JPEG Subsampling',
            'Reduce size but lose a little quality',
            subsampling_dropdown,
            visible=imgformat_dropdown.value == 'jpeg'
        ),
        'jpeg_keepdata': SettingRow(
            'JPEG Keep Data',
            'Keep raw DJI thermal data (~640KB) in JPEG Header.',
            ft.Switch(
                on_change=lambda e: on_settings_value_change(e.data, 'jpeg_keepdata'),
                value=settings['jpeg_keepdata']
            ),
            visible=imgformat_dropdown.value == 'jpeg'
        ),
        'png_compress': SettingRow(
            'PNG Compress',
            'Higher Smaller Slower',
            SpinBox(
                value=settings['png_compress'],
                min_val=0,
                max_val=9,
                precision=0,
                step=1,
                on_change=lambda v: on_settings_value_change(int(float(v.data)), 'png_compress')
            ),
            visible=imgformat_dropdown.value == 'png'
        )
    }

    settings_view = ft.ListView(
        controls=[
            SettingRow(
                'Distance (m)',
                'Overwrite internal value / default value',
                ft.Row([
                    ft.Switch(
                        # 'Distance (m)', width=120,
                        on_change=lambda e: on_preset_overwrite_value_change(e.data, 'distance'),
                        value=preset_overwrite['distance']
                    ),
                    SpinBox(
                        value=settings['distance'],
                        min_val=1.0,
                        max_val=25.0,
                        precision=1,
                        step=0.1,
                        on_change=lambda v: on_settings_value_change(float(v.data), 'distance')
                    )
                ])
            ),
            SettingRow(
                'Humidity (%)',
                'Overwrite internal value / default value',
                ft.Row([
                ft.Switch(
                    # 'Humidity (%)', width=120,
                    on_change=lambda e: on_preset_overwrite_value_change(e.data, 'humidity'),
                    value=preset_overwrite['humidity']
                ),
                SpinBox(
                    value=settings['humidity'],
                    min_val=20.0,
                    max_val=100.0,
                    precision=1,
                    step=0.1,
                    on_change=lambda v: on_settings_value_change(float(v.data), 'humidity')
                )
            ])
            ),
            SettingRow(
                'Emissivity (ε)',
                'Overwrite internal value / default value',
                ft.Row([
                    ft.Switch(
                        # 'Emissivity (ε)', width=120,
                        on_change=lambda e: on_preset_overwrite_value_change(e.data, 'emissivity'),
                        value=preset_overwrite['emissivity']
                    ),
                    SpinBox(
                        value=settings['emissivity'],
                        min_val=0.10,
                        max_val=1.00,
                        precision=2,
                        step=0.01,
                        on_change=lambda v: on_settings_value_change(float(v.data), 'emissivity')
                    )
                ])
            ),
            SettingRow(
                'Ambient (℃)',
                'Overwrite internal value / default value',
                ft.Row([
                    ft.Switch(
                        # 'Ambient (℃)', width=120,
                        on_change=lambda e: on_preset_overwrite_value_change(e.data, 'ambient'),
                        value=preset_overwrite['ambient']
                    ),
                    SpinBox(
                        value=settings['ambient'],
                        min_val=-40.0,
                        max_val=80.00,
                        precision=1,
                        step=0.1,
                        on_change=lambda v: on_settings_value_change(float(v.data), 'ambient')
                    )
                ])
            ),
            SettingRow(
                'Reflection (℃)',
                'Overwrite internal value / default value',
                ft.Row([
                    ft.Switch(
                        # 'Reflection (℃)', width=120,
                        on_change=lambda e: on_preset_overwrite_value_change(e.data, 'reflection'),
                        value=preset_overwrite['reflection']
                    ),
                    SpinBox(
                        value=settings['reflection'],
                        min_val=-40.0,
                        max_val=500.0,
                        precision=1,
                        step=0.1,
                        on_change=lambda v: on_settings_value_change(float(v.data), 'reflection')
                    )
                ])
            ),
            SettingRow(
                'Brightness',
                'Brightness of output image',
                SpinBox(
                    value=settings['brightness'],
                    min_val=0,
                    max_val=100,
                    precision=0,
                    step=1,
                    on_change=lambda v: on_settings_value_change(int(float(v.data)), 'brigetness')
                )
            ),
            SettingRow(
                'Max Workers',
                'Concurrent tasks to generate result faster',
                SpinBox(
                    value=settings['max_workers'],
                    min_val=1,
                    max_val=128,
                    precision=0,
                    step=1,
                    on_change=lambda v: on_settings_value_change(int(float(v.data)), 'max_workers')
                )
            ),
            SettingRow(
                'Palette',
                'Palette for output image',
                ft.Row([
                    ft.Switch(
                        # 'Palette', width=80,
                        on_change=lambda e: on_preset_overwrite_value_change(e.data, 'palette'),
                        value=preset_overwrite['palette']
                    ),
                    palette_dropdown
                ])
            ),
            SettingRow(
                'Colorbar Width',
                'Set width of temperature-color bar',
                SpinBox(
                    value=settings['colorbar_width'],
                    min_val=5,
                    max_val=100,
                    precision=0,
                    step=1,
                    on_change=lambda v: on_settings_value_change(int(float(v.data)), 'colorbar_width')
                )
            ),
            SettingRow(
                'Colorbar Border',
                'Whether temperature-color bar has border',
                ft.Switch(
                    value=settings['colorbar_border'], 
                    on_change=lambda e: on_settings_value_change(e.data, 'colorbar_border')
                )
            ),
            SettingRow(
                'Image Format',
                'PNG for Lossles, JPEG for SMALL SIZE',
                imgformat_dropdown
            ),
            img_settings['jpeg_quality'],
            img_settings['jpeg_subsampling'],
            img_settings['jpeg_keepdata'],
            img_settings['png_compress']
        ],
        # wrap=True
    )

    uni_progress_bar = ft.ProgressBar(1.0)
    uni_progress_info = ft.Text("等待任务开始", text_align=ft.TextAlign.CENTER)
    uni_progress_log = ft.ListView(
        controls=[ft.Container(ft.Text("系统启动"), border=ft.Border.only(
            top=ft.BorderSide(0.5, ft.Colors.OUTLINE_VARIANT),
        ))], 
        expand=True, 
        auto_scroll=True, 
        margin=10, 
        divider_thickness = 5
    )

    tab_view = ft.Tabs(
        selected_index=0,
        length=3,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="图像", icon=ft.Icons.PHOTO_ALBUM),
                        ft.Tab(label="设置", icon=ft.Icons.SETTINGS),
                        ft.Tab(label="日志", icon=ft.Icons.LOGO_DEV)
                    ],
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        image_grid_container,
                        ft.Container(
                            settings_view
                        ),
                        ft.Column(
                            [
                                ft.Column(
                                    [
                                        uni_progress_info,
                                        uni_progress_bar,
                                    ],
                                    margin=20,
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Container(
                                    ft.Column(
                                        [
                                            ft.Text("Log"),
                                            uni_progress_log,
                                        ],
                                        expand=True,
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                        margin=10
                                    ),
                                    border=ft.Border.all(side=ft.BorderSide(0.5, ft.Colors.OUTLINE_VARIANT)),
                                    expand=True,
                                    border_radius=10
                                )
                            ],
                            expand=True,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            margin=10
                        )
                    ],
                ),
            ],
        ),
    )

    main_container = ft.Container(
        tab_view,
        expand=True,
        border=ft.Border.only(left=ft.BorderSide(0.5, ft.Colors.OUTLINE_VARIANT))
    )

    async def on_select_all(e: ft.ControlEventHandler[ft.Switch]):
        for item in image_grid.controls:
            item: GalleryItem
            if item.is_selected != select_all_checkbox.value:
                item.toggle_selection(e)

    select_all_checkbox = ft.Switch(
        label="选择全部图像", 
        on_change=on_select_all,
        expand=True,
    )

    async def on_files_remove(e: ft.ControlEventHandler[ft.Button]):
        for i in range(len(image_grid.controls) - 1, -1, -1):
            item: GalleryItem = image_grid.controls[i]
            if item.is_selected:
                files_in_grid.pop(item.img_url)
                image_grid.controls.remove(item)
        
        if len(image_grid.controls) == 0:
            image_grid_container.content = image_grid_none
            image_grid_container.update()

    async def on_executable_pick():
        file = await ft.FilePicker().pick_files(
            dialog_title="选择可执行文件",
            allow_multiple=False,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=['exe']
        )
        if not file:
            return None
        return file[0]
        
    async def on_dji_irp_pick(e):
        file = await on_executable_pick()
        if file:
            if await check_dji_irp(file.path):
                dji_irp_textfield.value = file.path
                dji_irp_textfield.update()
            else:
                page.show_dialog(no_dji_irp_alert)

    async def on_weasyprint_pick(e):
        file = await on_executable_pick()
        if file:
            weasyprint_textfield.value = file.path
            weasyprint_textfield.update()

    async def on_files_pick(e):
        files = await ft.FilePicker().pick_files(
            dialog_title='选择DJI R-JPEG文件',
            allow_multiple=True, 
            file_type=ft.FilePickerFileType.CUSTOM, 
            allowed_extensions=['jpg', 'jpeg']
        )
        if not files:
            return
        new_add_items: int = 0
        for file in files:
            if file.path in files_in_grid:
                continue
            else:
                files_in_grid[file.path] = False
            image_grid.controls.append(
                GalleryItem(
                    img_url=file.path,
                    alignment=ft.Alignment.CENTER,
                    files_in_grid=files_in_grid
                )
            )
            if image_grid_container.content != image_grid:
                image_grid_container.content = image_grid
                image_grid_container.update()

            new_add_items += 1
        image_grid.update()

        items_count = len(image_grid.controls)
        if select_all_checkbox.value:
            for i in range(items_count - 1, items_count - 1 - new_add_items, -1):
                item: GalleryItem = image_grid.controls[i]
                item.toggle_selection(None)

    no_dji_irp_alert = ft.AlertDialog(
        title=ft.Text("无效的 dji_irp 路径"),
        content=ft.Text("请先选择正确的 dji_irp 路径再执行！"),
        actions=[ft.TextButton("确认", on_click=lambda e: page.pop_dialog())],
        open=True,
    )

    no_weasyprint_alert = ft.AlertDialog(
        title=ft.Text("无效的 weasyprint"),
        content=ft.Text("请先选择正确的 weasyprint 路径或正确安装库后再执行！"),
        actions=[ft.TextButton("确认", on_click=lambda e: page.pop_dialog())],
        open=True,
    )

    no_img_select_alert = ft.AlertDialog(
        title=ft.Text("没有选择图像"),
        content=ft.Text("请选择图像再生成报告！"),
        actions=[ft.TextButton("确认", on_click=lambda e: page.pop_dialog())],
        open=True,
    )

    is_running_alert = ft.AlertDialog(
        title=ft.Text("有任务正在执行"),
        content=ft.Text("请等待当前任务完成再继续！"),
        actions=[ft.TextButton("确认", on_click=lambda e: page.pop_dialog())],
        open=True,
    )

    async def on_generate_report(e):
        global is_running
        if is_running:
            page.show_dialog(is_running_alert)
            return
        
        items: list[GalleryItem] = image_grid.controls
        selected_items = [item.img_url for item in items if item.is_selected and os.path.exists(item.img_url)]
        if not selected_items:
            page.show_dialog(no_img_select_alert)
            return

        if not dji_irp_textfield.value or not os.path.exists(dji_irp_textfield.value) or not await check_dji_irp(dji_irp_textfield.value):
            page.show_dialog(no_dji_irp_alert)
            return
        
        if not weasyprint_textfield.value or not os.path.exists(weasyprint_textfield.value):
            check_result = await check_weasyprint()
            if check_result[0] == 'exe':
                weasyprint_textfield.value = check_result[1]
                weasyprint_textfield.update()
        else:
            check_result = await check_weasyprint(weasyprint_textfield.value)
        if check_result[0] == 'none':
            page.show_dialog(no_weasyprint_alert)
            return

        weasyprint_method = check_result[0]
        
        output_dir = await ft.FilePicker().get_directory_path("选择输出文件夹")
        if not output_dir:
            return
        
        is_running = True
        tab_view.selected_index = 2
        tab_view.update()

        temp_settings = settings.copy()
        for setting, v in preset_overwrite.items():
            if not v:
                temp_settings[setting] = None if setting != 'palette' else 'keep'
        
        uni_progress_bar.value = 0
        uni_progress_bar.update()
        gen = ThermalReportGenerator(
            input_dir=None,
            output_dir=output_dir,
            cli_path=dji_irp_textfield.value,
            weasy_path=weasyprint_textfield.value if weasyprint_method == 'exe' else None,
            **temp_settings
        )

        count = 1
        async for i, r in gen.run(selected_items):
            uni_progress_bar.value = count / i
            uni_progress_info.value = f"正在处理报告 {count}/{i}"
            uni_progress_log.controls.append(
                ft.Container(
                    ft.Text(r['message'], color=ft.Colors.GREEN_400 if r['success'] else ft.Colors.RED_400), 
                    border=ft.Border.only(
                        top=ft.BorderSide(0.5, ft.Colors.OUTLINE_VARIANT),
                    )
                )
            )
            if len(uni_progress_log.controls) > 1000:
                uni_progress_log.controls.pop(0)
            uni_progress_info.update()
            uni_progress_bar.update()
            uni_progress_log.update()
            count += 1
        
        is_running = False
        uni_progress_info.value = f"任务已完成"
        uni_progress_log.controls.append(
            ft.Container(
                ft.Text(f'任务已完成，请检查输出文件夹 "{output_dir}"'), 
                border=ft.Border.only(
                    top=ft.BorderSide(0.5, ft.Colors.OUTLINE_VARIANT),
                )
            )
        )
        uni_progress_log.update()
        uni_progress_info.update()

    async def on_change_palette(e):
        global is_running
        if is_running:
            page.show_dialog(is_running_alert)
            return
        
        items: list[GalleryItem] = image_grid.controls
        selected_items = [item.img_url for item in items if item.is_selected and os.path.exists(item.img_url)]
        if not selected_items:
            page.show_dialog(no_img_select_alert)
            return

        if not dji_irp_textfield.value or not os.path.exists(dji_irp_textfield.value) or not await check_dji_irp(dji_irp_textfield.value):
            page.show_dialog(no_dji_irp_alert)
            return
        
        output_dir = await ft.FilePicker().get_directory_path("选择输出文件夹")
        if not output_dir:
            return
        
        is_running = True
        tab_view.selected_index = 2
        tab_view.update()
        
        uni_progress_bar.value = 0
        uni_progress_bar.update()
        working_palette = settings['palette']
        gen = ThermalReportGenerator(
            input_dir=None,
            output_dir=output_dir,
            cli_path=dji_irp_textfield.value,
            weasy_path=None,
            **settings
        )

        count = 1
        async for i, r in gen.run_palette_change(selected_items):
            uni_progress_bar.value = count / i
            uni_progress_info.value = f"正在处理LUT {count}/{i}"
            uni_progress_log.controls.append(
                ft.Container(
                    ft.Text(r['message'], color=ft.Colors.GREEN_400 if r['success'] else ft.Colors.RED_400), 
                    border=ft.Border.only(
                        top=ft.BorderSide(0.5, ft.Colors.OUTLINE_VARIANT),
                    )
                )
            )
            if len(uni_progress_log.controls) > 1000:
                uni_progress_log.controls.pop(0)
            uni_progress_info.update()
            uni_progress_bar.update()
            uni_progress_log.update()
            count += 1
        
        is_running = False
        uni_progress_info.value = f"任务已完成"
        uni_progress_log.controls.append(
            ft.Container(
                ft.Text(f'任务已完成，请检查输出文件夹 "{os.path.join(output_dir, working_palette)}"'), 
                border=ft.Border.only(
                    top=ft.BorderSide(0.5, ft.Colors.OUTLINE_VARIANT),
                )
            )
        )
        uni_progress_log.update()
        uni_progress_info.update()

    async def save_config():
        global settings, preset_overwrite
        import json
        config_path1 = pathlib.Path(__file__).parent / 'dji_timgrg_config.json'
        config_path2 = pathlib.Path(__file__).parent / 'dji_timgrg_config2.json'
        all_config = settings.copy()
        all_config['cli_path'] = dji_irp_textfield.value
        all_config['weasy_path'] = weasyprint_textfield.value
        with open(config_path1, mode='w', encoding='utf-8') as f:
            json.dump(all_config, f)
        with open(config_path2, mode='w', encoding='utf-8') as f:
            json.dump(preset_overwrite, f)

    async def handle_window_event(e: ft.WindowEvent):
        if e.type == ft.WindowEventType.CLOSE:
            await save_config()
            await page.window.destroy()

    page.window.on_event = handle_window_event
        
    page.add(
        ft.Row(
            expand=True,
            controls=[
                ft.Column(
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        ft.Button(
                            '添加图像', ft.Icons.FILE_OPEN,
                            on_click=on_files_pick,
                            width=180
                        ),
                        ft.Button(
                            '移除选中图像', ft.Icons.REMOVE,
                            on_click=on_files_remove,
                            width=180
                        ),
                        ft.Button(
                            '生成报告',
                            on_click = on_generate_report,
                            width=180
                        ),
                        ft.Button(
                            '转换LUT/调色盘',
                            on_click = on_change_palette,
                            width=180
                        ),
                        ft.Container(
                            content = select_all_checkbox,
                            # border = ft.Border.all(3, ft.Colors.BLUE),
                            width = 180,
                            border_radius = 10
                        )
                    ],
                ),
                main_container
            ]
        ),
        ft.Container(
            ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.Button(
                        "选择dji_irp路径", 
                        on_click=on_dji_irp_pick,
                        width=180
                    ),
                    dji_irp_textfield,
                ],
                margin=ft.Margin.only(top=10),
            ),
            border=ft.Border.only(top=ft.BorderSide(0.5, ft.Colors.OUTLINE_VARIANT))
        )
    )
    if platform.system() == 'Windows' and weasyprint_method != 'lib':
        page.add(
            ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.Button(
                        "选择weasyprint路径", 
                        on_click=on_weasyprint_pick,
                        width=180
                    ),
                    weasyprint_textfield,
                ]
            )
        )

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    ft.run(main)