import flet as ft, pathlib
from dataclasses import field

@ft.control(isolated=True)
class GalleryItem(ft.Container):
    img_url: str | None = None
    is_selected: bool = False
    img_border_radius: int = 0
    files_in_grid: dict[str, bool] = field(
        default_factory=dict
    )

    def build(self):
        self.check_mark = ft.Icon(
            ft.icons.Icons.CHECK_CIRCLE, 
            visible=self.is_selected
        )

        self.content = ft.Column(
            controls=[
                ft.Stack(
                    controls=[
                        ft.Image(
                            src=self.img_url, 
                            border_radius=self.img_border_radius,
                            fit=ft.BoxFit.CONTAIN,
                            expand=True
                        ),
                        self.check_mark,
                    ],
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Text(
                    pathlib.Path(self.img_url).name, 
                    text_align=ft.TextAlign.CENTER, 
                    overflow=ft.TextOverflow.ELLIPSIS,
                    max_lines=2,
                ),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
        self.on_click = self.toggle_selection

    def toggle_selection(self, e):
        self.is_selected = not self.is_selected
        self.check_mark.visible = self.is_selected
        self.border = ft.Border.all(3, ft.Colors.BLUE) if self.is_selected else None
        self.files_in_grid[self.url] = self.is_selected
        self.update()