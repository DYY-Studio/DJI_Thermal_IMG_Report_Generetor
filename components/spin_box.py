import flet as ft, asyncio

@ft.control
class SpinBox(ft.Row):
    value: float = 0.0
    step: float = 1.0
    min_val: float = 0.0
    max_val: float = 100.0
    precision: int = 0
    on_change: ft.Event = None

    def build(self):
        # 1. 规范：直接操作 self 的属性，不使用 return
        self.spacing = 0
        self.vertical_alignment = ft.CrossAxisAlignment.CENTER
        self._is_holding = False  # 状态锁

        self.tf = ft.TextField(
            value=self._format(self.value),
            width=70, height=38,
            text_size=13, content_padding=5,
            text_align=ft.TextAlign.CENTER,
            on_submit=self._on_manual_submit,
            on_blur=self._on_manual_submit,
            input_filter=ft.InputFilter(allow=True, regex_string=r"^-?\d*\.?\d*$", replacement_string="")
        )

        self.stepup_btn = self._create_stepper_button(ft.Icons.ADD, self.step)
        self.stepdown_btn = self._create_stepper_button(ft.Icons.REMOVE, -self.step)

        # 组装控件
        self.controls = [
            self.stepdown_btn,
            self.tf,
            self.stepup_btn,
        ]

    def _create_stepper_button(self, icon: ft.IconData, delta: float):
        # 使用 GestureDetector 捕获更底层的按下和抬起动作
        return ft.GestureDetector(
            content=ft.Container(
                content=ft.Icon(icon, size=18, color=ft.Colors.BLUE_GREY_700),
                padding=8,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border_radius=4,
            ),
            on_tap=lambda _: self._modify_value(delta),
            on_long_press_start=lambda _: self._start_pressing(delta),
            on_long_press_end=lambda _: self._stop_pressing(),
            on_exit=lambda _: self._stop_pressing(),
        )

    def _start_pressing(self, delta: float):
        self._is_holding = True
        self.current_delta = delta
        
        self.page.run_task(self._hold_loop)

    def _stop_pressing(self):
        self._is_holding = False

    async def _hold_loop(self):
        while self._is_holding:
            self._modify_value(self.current_delta)
            await asyncio.sleep(0.05)

    def _modify_value(self, delta: float, manual: bool = False):
        old_val = self.value
        new_val = max(self.min_val, min(self.max_val, old_val + delta))

        if new_val >= self.max_val:
            self.page.run_task(self._flash_error)
            self.stepup_btn.content.opacity = 0.3
            self.stepup_btn.update()
            self._is_holding = False
        elif new_val <= self.min_val:
            self.page.run_task(self._flash_error)
            self.stepdown_btn.content.opacity = 0.3
            self.stepdown_btn.update()
            self._is_holding = False
        else:
            if self.stepup_btn.content.opacity < 1.0:
                self.stepup_btn.content.opacity = 1.0
                self.stepup_btn.update()
            if self.stepdown_btn.content.opacity < 1.0:
                self.stepdown_btn.content.opacity = 1.0
                self.stepdown_btn.update()

        # 只有在数值真正改变时才刷新 UI，减少闪烁
        if new_val != old_val or manual:
            self.value = round(new_val, self.precision)
            self.tf.value = self._format(self.value)
            self.tf.update()
            
            if self.on_change:
                # 模拟事件传递
                self.on_change(ft.ControlEvent(control=self, name="change", data=str(self.value)))

    async def _flash_error(self):
        self.tf.bgcolor = ft.Colors.RED_100
        self.tf.update()
        await asyncio.sleep(0.1)
        self.tf.bgcolor = ft.Colors.TRANSPARENT
        self.tf.update()

    def _format(self, val):
        return f"{val:.{self.precision}f}" if self.precision > 0 else str(int(val))

    def _on_manual_submit(self, e):
        try:
            input_val = float(self.tf.value)
            self._modify_value(input_val - self.value, manual = True)
        except ValueError:
            self.tf.value = self._format(self.value)
            self.update()

if __name__ == '__main__':
    async def main(page: ft.Page):
        page.add(SpinBox(precision=2, step=0.01, value=5.0, max_val=10.0))

    ft.run(main)