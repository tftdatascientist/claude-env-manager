"""Generuje ikony Claude Manager (białe CM na niebieskim tle, wzorzec RAZD)."""

import io
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

BLUE_BG = "#1565C0"
WHITE_FG = "white"
ASSETS = Path(__file__).parent / "assets"


def _render_cm(size: int) -> QPixmap:
    """Rysuje 'CM' białe litery na niebieskim tle — analogicznie do RAZD 'R'."""
    px = QPixmap(size, size)
    px.fill(QColor(BLUE_BG))
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor(WHITE_FG))

    # Rozmiar czcionki: mniejszy niż RAZD (0.60*size) bo mamy 2 litery — 0.42*size
    font_size = max(6, int(size * 0.42))
    painter.setFont(QFont("Arial", font_size, QFont.Weight.Bold))
    painter.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "CM")
    painter.end()
    return px


def _render_cm_tray(size: int) -> QPixmap:
    """Ikona tray — takie samo CM, tylko upewniony font dla małych rozmiarów."""
    px = QPixmap(size, size)
    px.fill(QColor(BLUE_BG))
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor(WHITE_FG))
    font_size = max(5, int(size * 0.42))
    painter.setFont(QFont("Arial", font_size, QFont.Weight.Bold))
    painter.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "CM")
    painter.end()
    return px


def _qpx_to_pil(px: "QPixmap"):
    from PIL import Image as _Image
    from PySide6.QtCore import QBuffer, QIODevice
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    px.save(buf, "PNG")
    buf.close()
    return _Image.open(io.BytesIO(buf.data().data())).convert("RGBA").copy()


def _save_ico_pillow(render_fn, sizes: list[int], output: Path) -> bool:
    """Zapisuje wielowarstwowy ICO przez ręczne sklejenie nagłówka ICO z PNG-ami."""
    try:
        import struct
        images = [_qpx_to_pil(render_fn(sz)) for sz in sizes]

        # Budujemy ICO ręcznie: nagłówek + directory + dane PNG
        n = len(images)
        png_datas: list[bytes] = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, "PNG")
            png_datas.append(buf.getvalue())

        header_size = 6
        dir_entry_size = 16
        data_offset = header_size + dir_entry_size * n

        ico = io.BytesIO()
        # ICO header
        ico.write(struct.pack("<HHH", 0, 1, n))

        current_offset = data_offset
        for img, png in zip(images, png_datas):
            w = img.width if img.width < 256 else 0
            h = img.height if img.height < 256 else 0
            ico.write(struct.pack(
                "<BBBBHHII",
                w, h,      # width, height (0 = 256)
                0,         # color count
                0,         # reserved
                1,         # planes
                32,        # bpp
                len(png),  # size of image data
                current_offset,
            ))
            current_offset += len(png)

        for png in png_datas:
            ico.write(png)

        output.write_bytes(ico.getvalue())
        return True
    except ImportError:
        return False


def _save_ico_qt_fallback(render_fn, output: Path) -> None:
    px = render_fn(256)
    if not px.save(str(output), "ICO"):
        output = output.with_suffix(".png")
        px.save(str(output), "PNG")
        print(f"  Pillow niedostępny, zapisano PNG: {output}")


def generate_main_icon() -> Path:
    """Ikona główna CM: 16/32/48/256px — pasek zadań, pulpit, okno."""
    output = ASSETS / "cm.ico"
    sizes = [16, 32, 48, 256]
    if _save_ico_pillow(_render_cm, sizes, output):
        print(f"  [OK] {output} ({'/'.join(str(s) for s in sizes)}px)")
    else:
        _save_ico_qt_fallback(_render_cm, output)
        print(f"  [OK] {output} (256px, Pillow niedostępny)")
    return output


def generate_tray_icon() -> Path:
    """Ikona tray CM: 16/32/48px — mała ikona w tray i zminimalizowana."""
    output = ASSETS / "cm_tray.ico"
    sizes = [16, 32, 48]
    if _save_ico_pillow(_render_cm_tray, sizes, output):
        print(f"  [OK] {output} ({'/'.join(str(s) for s in sizes)}px)")
    else:
        _save_ico_qt_fallback(_render_cm_tray, output)
        print(f"  [OK] {output} (fallback)")
    return output


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    ASSETS.mkdir(exist_ok=True)
    print("Generowanie ikon Claude Manager (niebieskie tło, białe CM)...")
    generate_main_icon()
    generate_tray_icon()
    print("Gotowe.")


if __name__ == "__main__":
    main()
