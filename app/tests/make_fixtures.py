"""Creates test documents with KNOWN contents in tests/fixtures (no real data needed).

  spec_revc.pdf        3-page digital PDF (lookup facts, an injected instruction, unanswerable questions)
  datasheet_scan.pdf   IMAGE-ONLY PDF (no text layer) -> must be read with OCR
  mass_table.pdf       PDF with a ruled table
  rover.docx           Word file with a heading, a bullet list of 7 items and a paragraph
  design_pattern_list.pdf  copy of the user's real PDF if it exists in Downloads (numbered list of 10 patterns)
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
FIX.mkdir(exist_ok=True)
sys.path.insert(0, str(HERE))


def spec_pdf():
    from smoke_test import PAGES, make_pdf

    (FIX / "spec_revc.pdf").write_bytes(make_pdf(PAGES))


def scanned_pdf():
    import pymupdf
    from PIL import Image, ImageDraw, ImageFont

    lines = ["SENSOR DATASHEET", "", "Model: Orion Thermal Sensor",
             "Operating temperature range: -20 to 85 degrees Celsius.", "Supply voltage: 5 V DC.",
             "Accuracy is plus or minus 0.5 degrees.", "Warranty period: 3 years."]
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 38)
    except OSError:
        font = ImageFont.load_default()
    img = Image.new("RGB", (1240, 1754), "white")
    d = ImageDraw.Draw(img)
    y = 140
    for l in lines:
        d.text((100, y), l, fill="black", font=font)
        y += 80
    img = img.rotate(0.6, fillcolor="white")          # slight scan skew
    png = FIX / "datasheet_scan.png"
    img.save(png)
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, filename=str(png))
    doc.save(FIX / "datasheet_scan.pdf")
    png.unlink()


def table_pdf():
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 60), "Mass and power budget", fontsize=16)
    page.insert_text((50, 82), "The table below lists the budget of each subsystem of the Aurora satellite.", fontsize=10)
    rows = [["Subsystem", "Mass (kg)", "Power (W)"], ["Power", "12.5", "40"], ["Thermal", "8.4", "22"],
            ["Structure", "30.2", "0"], ["Payload", "15.7", "65"]]
    colw, x0, y0, rh = [170, 110, 110], 50, 110, 28
    for r, row in enumerate(rows):
        x = x0
        for c, cell in enumerate(row):
            rect = pymupdf.Rect(x, y0 + r * rh, x + colw[c], y0 + (r + 1) * rh)
            page.draw_rect(rect, width=0.8)
            page.insert_text((x + 6, y0 + r * rh + 19), cell, fontsize=11)
            x += colw[c]
    page.insert_text((50, y0 + len(rows) * rh + 28), "Table 1: Subsystem budget.", fontsize=10)
    doc.save(FIX / "mass_table.pdf")


def rover_docx():
    import docx

    d = docx.Document()
    d.add_heading("Rover Payload Overview", level=1)
    d.add_paragraph("The rover carries the following instruments:")
    for item in ["Lidar scanner", "Stereo camera", "Inertial measurement unit", "Spectrometer",
                 "Ground-penetrating radar", "Weather station", "Sample drill"]:
        d.add_paragraph(item, style="List Bullet")
    d.add_paragraph("Mission duration is 180 sols. The rover is powered by a solar array and a lithium battery.")
    d.save(FIX / "rover.docx")


def user_pdf():
    src = Path(r"C:\Users\Admin\Downloads\Design pattern list test.pdf")
    if src.exists():
        shutil.copy(src, FIX / "design_pattern_list.pdf")


def main():
    spec_pdf(); scanned_pdf(); table_pdf(); rover_docx(); user_pdf()
    print("fixtures:", sorted(p.name for p in FIX.iterdir()))


if __name__ == "__main__":
    main()
