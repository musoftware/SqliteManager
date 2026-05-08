"""
widgets/splash_screen.py — Professional Animated Splash Screen.

Shown during startup while heavy modules load.
Features: progress bar, animated dots, fade-in/out.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property, QRect
from PySide6.QtGui import QPainter, QPixmap, QColor, QFont, QLinearGradient, QBrush, QPen
from PySide6.QtWidgets import QSplashScreen, QProgressBar, QApplication

from app.version import VERSION, APP_NAME, APP_DESCRIPTION


class SplashScreen(QSplashScreen):
    """
    Animated splash screen with:
    - Background image (or generated dark gradient)
    - App name, version, description
    - Animated progress bar
    - Loading status message
    """

    def __init__(self, pixmap: QPixmap | None = None):
        if pixmap is None or pixmap.isNull():
            pixmap = self._generate_pixmap()

        super().__init__(pixmap, Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self._progress = 0
        self._message = "Initializing…"
        self._dot_count = 0

        # Animated dots timer
        self._dot_timer = QTimer(self)
        self._dot_timer.timeout.connect(self._animate_dots)
        self._dot_timer.start(400)

    def _generate_pixmap(self) -> QPixmap:
        """Generate a high-quality gradient splash pixmap if no image found."""
        W, H = 680, 380
        px = QPixmap(W, H)
        px.fill(Qt.transparent)

        p = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing)

        # Background gradient
        grad = QLinearGradient(0, 0, W, H)
        grad.setColorAt(0, QColor("#181825"))
        grad.setColorAt(1, QColor("#1e1e2e"))
        p.fillRect(0, 0, W, H, grad)

        # Subtle border glow
        pen = QPen(QColor("#cba6f7"))
        pen.setWidth(2)
        p.setPen(pen)
        p.drawRoundedRect(2, 2, W - 4, H - 4, 12, 12)

        # Inner border
        pen2 = QPen(QColor("#313244"))
        pen2.setWidth(1)
        p.setPen(pen2)
        p.drawRoundedRect(6, 6, W - 12, H - 12, 10, 10)

        # Database icon (circle + lines)
        cx, cy, r = W // 2, 130, 55
        p.setBrush(QBrush(QColor("#1e1e2e")))
        p.setPen(QPen(QColor("#cba6f7"), 3))
        # Cylinder top ellipse
        p.drawEllipse(cx - r, cy - 20, r * 2, 40)
        # Cylinder body
        p.drawRect(cx - r, cy, r * 2, 60)
        # Cylinder bottom
        p.drawEllipse(cx - r, cy + 40, r * 2, 40)

        # Glowing accent ellipses
        p.setBrush(QColor(203, 166, 247, 60))
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - r - 10, cy - 30, (r + 10) * 2, 20)

        # Lightning bolt
        bolt_color = QColor("#f9e2af")
        p.setPen(QPen(bolt_color, 3))
        p.setBrush(bolt_color)
        bolt_pts = [
            (cx + 5, cy + 5), (cx - 8, cy + 30),
            (cx + 2, cy + 30), (cx - 5, cy + 55),
            (cx + 14, cy + 25), (cx + 4, cy + 25),
        ]
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        poly = QPolygon([QPoint(x, y) for x, y in bolt_pts])
        p.drawPolygon(poly)

        # App name
        font = QFont("Segoe UI", 28, QFont.Bold)
        p.setFont(font)
        p.setPen(QColor("#cdd6f4"))
        p.drawText(QRect(0, 210, W, 50), Qt.AlignHCenter | Qt.AlignVCenter, APP_NAME)

        # Description
        font2 = QFont("Segoe UI", 11)
        p.setFont(font2)
        p.setPen(QColor("#7f849c"))
        p.drawText(QRect(0, 258, W, 30), Qt.AlignHCenter | Qt.AlignVCenter, APP_DESCRIPTION)

        # Version
        font3 = QFont("Consolas", 9)
        p.setFont(font3)
        p.setPen(QColor("#585b70"))
        p.drawText(QRect(16, H - 30, 200, 20), Qt.AlignLeft | Qt.AlignVCenter, f"v{VERSION}")

        p.end()
        return px

    def drawContents(self, painter: QPainter) -> None:
        """Override to draw dynamic content (progress bar, message)."""
        W = self.width()
        H = self.height()

        # Progress bar background
        bar_y = H - 12
        bar_h = 6
        bar_margin = 20
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#313244"))
        painter.drawRoundedRect(bar_margin, bar_y, W - bar_margin * 2, bar_h, 3, 3)

        # Progress fill gradient
        fill_w = int((W - bar_margin * 2) * self._progress / 100)
        if fill_w > 0:
            g = QLinearGradient(bar_margin, 0, bar_margin + fill_w, 0)
            g.setColorAt(0, QColor("#89b4fa"))
            g.setColorAt(1, QColor("#cba6f7"))
            painter.setBrush(g)
            painter.drawRoundedRect(bar_margin, bar_y, fill_w, bar_h, 3, 3)

        # Status message
        dots = "." * self._dot_count
        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        painter.setPen(QColor("#7f849c"))
        painter.drawText(
            QRect(bar_margin, H - 32, W - bar_margin * 2, 18),
            Qt.AlignRight | Qt.AlignVCenter,
            self._message + dots,
        )

    def set_progress(self, value: int, message: str = "") -> None:
        self._progress = max(0, min(100, value))
        if message:
            self._message = message
        self.repaint()
        QApplication.processEvents()

    def _animate_dots(self) -> None:
        self._dot_count = (self._dot_count + 1) % 4
        self.repaint()

    def finish_and_close(self, window) -> None:
        self.set_progress(100, "Ready")
        QTimer.singleShot(300, lambda: self.finish(window))
