#!/usr/bin/env python3
"""Icon generation script for STT Desktop Client.

Generates multi-size PNG icons and SVG programmatically for proper
desktop integration on Linux (KDE Plasma, GNOME).

This script creates icons using QPainter (no external SVG dependencies),
following the same approach as the system tray icon in tray_app.py.
"""
import sys
from pathlib import Path

# Qt imports for programmatic icon generation
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication


def create_microphone_pixmap(size: int) -> QPixmap:
    """Create a microphone icon pixmap programmatically.

    This function uses QPainter to draw the microphone icon at any size,
    following the same design as the system tray icon in tray_app.py.

    Args:
        size: The width and height of the icon in pixels

    Returns:
        QPixmap containing the rendered icon
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Colors - matching the tray icon design
    bg_color = QColor(74, 144, 217)  # Blue background
    stroke_color = QColor(44, 95, 141)  # Darker blue stroke
    white = QColor(255, 255, 255)  # White icon elements

    # Scale dimensions based on size
    scale = size / 64.0  # Base design is 64x64

    # Circle background
    center = size // 2
    radius = int(size // 2 - 2 * scale)
    painter.setBrush(bg_color)
    painter.setPen(QPen(stroke_color, max(1, int(2 * scale))))
    painter.drawEllipse(center - radius, center - radius, radius * 2, radius * 2)

    # Microphone body (rounded rectangle)
    mic_width = int(12 * scale)
    mic_height = int(20 * scale)
    mic_x = center - mic_width // 2
    mic_y = int(center - 8 * scale)
    painter.setBrush(white)
    painter.setPen(QPen(stroke_color, max(1, int(1.5 * scale))))
    painter.drawRoundedRect(mic_x, mic_y, mic_width, mic_height,
                           int(6 * scale), int(6 * scale))

    # Microphone grille lines
    painter.setPen(QPen(QColor(224, 224, 224), max(1, int(1 * scale))))
    line_spacing = max(3, int(4 * scale))
    for y in range(mic_y + int(6 * scale), mic_y + mic_height - 2, line_spacing):
        painter.drawLine(mic_x + max(1, int(2 * scale)), y,
                        mic_x + mic_width - max(1, int(2 * scale)), y)

    # Microphone stand
    pen = QPen(white, max(2, int(3 * scale)))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    stand_bottom = mic_y + mic_height + int(8 * scale)
    painter.drawLine(center, mic_y + mic_height, center, stand_bottom)
    painter.drawLine(center - int(6 * scale), stand_bottom,
                    center + int(6 * scale), stand_bottom)

    # Sound waves
    pen = QPen(white, max(1, int(2 * scale)))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    # First wave
    wave1_x = int(center + 10 * scale)
    wave1_size = int(8 * scale)
    painter.drawArc(wave1_x, int(center - 6 * scale), wave1_size,
                   int(12 * scale), 140 * 16, 80 * 16)
    # Second wave
    wave2_x = int(center + 16 * scale)
    wave2_size = int(12 * scale)
    painter.drawArc(wave2_x, int(center - 8 * scale), wave2_size,
                   int(16 * scale), 140 * 16, 80 * 16)

    painter.end()
    return pixmap


def create_svg_content(size: int = 256) -> str:
    """Create SVG content for the microphone icon.

    Generates an SVG string that matches the programmatic icon design.

    Args:
        size: The viewBox size (default 256 for good scaling)

    Returns:
        SVG string content
    """
    # Use base size of 256 for SVG coordinate system
    base_size = size
    center = base_size // 2

    # Scale factors (based on 64px design)
    scale = base_size / 64.0

    # Calculate dimensions
    radius = int(base_size // 2 - 2 * scale)
    mic_width = int(12 * scale)
    mic_height = int(20 * scale)
    mic_x = center - mic_width // 2
    mic_y = int(center - 8 * scale)
    stand_bottom = mic_y + mic_height + int(8 * scale)
    wave1_x = int(center + 10 * scale)
    wave2_x = int(center + 16 * scale)

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{size}" height="{size}" viewBox="0 0 {base_size} {base_size}"
     xmlns="http://www.w3.org/2000/svg">
  <!-- Circle background -->
  <circle cx="{center}" cy="{center}" r="{radius}"
          fill="#4A90D9" stroke="#2C5F8D" stroke-width="{max(1, 2*scale)}"/>

  <!-- Microphone body -->
  <rect x="{mic_x}" y="{mic_y}" width="{mic_width}" height="{mic_height}"
        rx="{6*scale}" ry="{6*scale}"
        fill="#FFFFFF" stroke="#2C5F8D" stroke-width="{max(1, 1.5*scale)}"/>

  <!-- Microphone grille lines -->
  <g stroke="#E0E0E0" stroke-width="{max(1, scale)}">
    <line x1="{mic_x + 2*scale}" y1="{mic_y + 6*scale}"
          x2="{mic_x + mic_width - 2*scale}" y2="{mic_y + 6*scale}"/>
    <line x1="{mic_x + 2*scale}" y1="{mic_y + 10*scale}"
          x2="{mic_x + mic_width - 2*scale}" y2="{mic_y + 10*scale}"/>
    <line x1="{mic_x + 2*scale}" y1="{mic_y + 14*scale}"
          x2="{mic_x + mic_width - 2*scale}" y2="{mic_y + 14*scale}"/>
  </g>

  <!-- Microphone stand -->
  <line x1="{center}" y1="{mic_y + mic_height}" x2="{center}" y2="{stand_bottom}"
        stroke="#FFFFFF" stroke-width="{max(2, 3*scale)}" stroke-linecap="round"/>
  <line x1="{center - 6*scale}" y1="{stand_bottom}"
        x2="{center + 6*scale}" y2="{stand_bottom}"
        stroke="#FFFFFF" stroke-width="{max(2, 3*scale)}" stroke-linecap="round"/>

  <!-- Sound waves -->
  <path d="M {wave1_x} {center - 6*scale}
           A {4*scale} {6*scale} 0 0 1 {wave1_x} {center + 6*scale}"
        fill="none" stroke="#FFFFFF" stroke-width="{max(1, 2*scale)}" stroke-linecap="round"/>
  <path d="M {wave2_x} {center - 8*scale}
           A {6*scale} {8*scale} 0 0 1 {wave2_x} {center + 8*scale}"
        fill="none" stroke="#FFFFFF" stroke-width="{max(1, 2*scale)}" stroke-linecap="round"/>
</svg>'''
    return svg


def main():
    """Generate icons in multiple sizes programmatically."""
    # Create QApplication (required for QPixmap)
    app = QApplication(sys.argv)

    # Paths
    script_dir = Path(__file__).parent
    output_dir = script_dir

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Icon sizes to generate (PNG)
    sizes = [48, 64, 128, 256]

    # Generate PNG icons for each size
    for size in sizes:
        pixmap = create_microphone_pixmap(size)

        # Save to top-level directory with size suffix
        output_path = output_dir / f"stt-recorder-{size}x{size}.png"
        if pixmap.save(str(output_path), "PNG"):
            print(f"Generated: {output_path}")
        else:
            print(f"Error: Failed to save {output_path}", file=sys.stderr)
            sys.exit(1)

    # Create hicolor icon theme structure
    # Standard Linux icon theme directories
    theme_sizes = {
        48: "48x48/apps/stt-recorder.png",
        64: "64x64/apps/stt-recorder.png",
        128: "128x128/apps/stt-recorder.png",
        256: "256x256/apps/stt-recorder.png",
    }

    for size, rel_path in theme_sizes.items():
        subdir = output_dir / Path(rel_path).parent
        subdir.mkdir(parents=True, exist_ok=True)

        pixmap = create_microphone_pixmap(size)
        output_path = output_dir / rel_path
        if pixmap.save(str(output_path), "PNG"):
            print(f"Generated: {output_path}")
        else:
            print(f"Error: Failed to save {output_path}", file=sys.stderr)
            sys.exit(1)

    # Generate SVG icons (both top-level and in scalable/apps directory)
    svg_content = create_svg_content(256)

    # Top-level SVG
    svg_top = output_dir / "stt-recorder.svg"
    svg_top.write_text(svg_content, encoding='utf-8')
    print(f"Generated: {svg_top}")

    # Scalable directory SVG (for hicolor icon theme)
    scalable_dir = output_dir / "scalable" / "apps"
    scalable_dir.mkdir(parents=True, exist_ok=True)

    svg_output = scalable_dir / "stt-recorder.svg"
    svg_output.write_text(svg_content, encoding='utf-8')
    print(f"Generated: {svg_output}")

    print(f"\nIcon generation complete! Icons saved to: {output_dir}")
    print(f"Generated sizes: {', '.join(f'{s}x{s}' for s in sizes)}")
    print("Plus scalable SVG for hicolor icon theme.")


if __name__ == "__main__":
    main()
