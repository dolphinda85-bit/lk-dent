from __future__ import annotations

import argparse
import io
import json
import re
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

PAGE_WIDTH = 595.2756
PAGE_HEIGHT = 841.8898
FONT_REGULAR = "DP-Times"
FONT_BOLD = "DP-Times-Bold"


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
    )


def register_fonts() -> None:
    regular = Path("C:/Windows/Fonts/times.ttf")
    bold = Path("C:/Windows/Fonts/timesbd.ttf")
    if not regular.exists() or not bold.exists():
        raise FileNotFoundError("Не найдены шрифты Times New Roman в C:/Windows/Fonts")
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(regular)))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold)))


def split_words(text: str, width: float, font: str, size: float) -> list[str]:
    result: list[str] = []
    for paragraph in normalize_text(text).splitlines() or [""]:
        words = paragraph.split()
        if not words:
            result.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if pdfmetrics.stringWidth(candidate, font, size) <= width:
                current = candidate
            else:
                result.append(current)
                current = word
        result.append(current)
    return result


def draw_box(
    c: canvas.Canvas,
    text: str,
    x: float,
    top: float,
    width: float,
    height: float,
    size: float = 7.4,
    leading: float | None = None,
    font: str = FONT_REGULAR,
    max_lines: int | None = None,
) -> int:
    leading = leading or size * 1.18
    lines = split_words(text, width, font, size)
    allowed = max(1, int(height // leading))
    if max_lines is not None:
        allowed = min(allowed, max_lines)
    if len(lines) > allowed:
        raise ValueError(f"Текст не помещается в область: {text[:80]!r}; строк {len(lines)}, доступно {allowed}")
    c.setFont(font, size)
    y = PAGE_HEIGHT - top - size
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return len(lines)


def draw_center(c: canvas.Canvas, text: str, x: float, top: float, size: float = 8.0, font: str = FONT_BOLD) -> None:
    c.setFont(font, size)
    c.drawCentredString(x, PAGE_HEIGHT - top - size, normalize_text(text))


def date_parts(value: str) -> tuple[str, str, str]:
    dt = datetime.fromisoformat(value)
    return dt.strftime("%d"), dt.strftime("%m"), dt.strftime("%Y")


def short_date(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%d.%m.%Y")


def draw_form_date(
    c: canvas.Canvas,
    value: str,
    day_x: float,
    month_x: float,
    year_x: float,
    top: float,
    size: float = 7.2,
) -> None:
    day, month, year = date_parts(value)
    draw_box(c, day, day_x, top, 18, 12, size)
    draw_box(c, month, month_x, top, 28, 12, size)
    draw_box(c, year[-2:], year_x, top, 18, 12, size)


def tooth_code(tooth: dict) -> str:
    conditions = set(tooth.get("conditions") or [])
    if tooth.get("basis") == "implant":
        return "5"
    if tooth.get("basis") == "pontic":
        return "9"
    if tooth.get("presence") == "absent":
        return "4"
    if "root_remnant" in conditions:
        return "R"
    if "crown" in conditions:
        return "7"
    if "caries" in conditions:
        return "1"
    if "filling" in conditions:
        return "3"
    if "intact" in conditions:
        return "0"
    return ""


def get_plan(record: dict, form_line: str) -> str:
    for item in record.get("treatmentPlan", []):
        if item.get("formLine") == form_line:
            return item.get("text", "")
    return ""


def watermark(c: canvas.Canvas) -> None:
    c.saveState()
    c.setFillColor(Color(0.42, 0.42, 0.42))
    c.setFont(FONT_BOLD, 6.2)
    c.drawRightString(PAGE_WIDTH - 22, PAGE_HEIGHT - 13, "ТЕСТОВОЕ ЗАПОЛНЕНИЕ")
    c.restoreState()


def draw_page_1(c: canvas.Canvas, data: dict) -> None:
    record = data["clinicalRecord"]
    watermark(c)
    draw_box(c, datetime.fromisoformat(data["visit"]["dateTime"]).strftime("%d.%m."), 320, 25, 55, 14, 8.0)
    draw_box(c, datetime.fromisoformat(data["visit"]["dateTime"]).strftime("%y"), 397, 25, 16, 14, 8.0)

    teeth = {int(t["fdi"]): t for t in record.get("dentalFormula", [])}
    upper = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28]
    lower = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]
    grid_x = 297.65
    cell_w = 17.0
    for index, fdi in enumerate(upper):
        draw_center(c, tooth_code(teeth.get(fdi, {})), grid_x + cell_w * (index + 0.5), 61, 8.0)
    for index, fdi in enumerate(lower):
        draw_center(c, tooth_code(teeth.get(fdi, {})), grid_x + cell_w * (index + 0.5), 160, 8.0)

    kpu = (record.get("indices") or {}).get("kpu") or {}
    draw_box(c, str(kpu.get("k", "")), 41, 234, 10, 12, 7.4)
    draw_box(c, str(kpu.get("p", "")), 66, 234, 10, 12, 7.4)
    draw_box(c, str(kpu.get("u", "")), 91, 234, 10, 12, 7.4)
    draw_box(c, str(kpu.get("total", "")), 126, 234, 18, 12, 7.4)
    ohi = (record.get("indices") or {}).get("ohiS") or {}
    draw_center(c, str(ohi.get("total", "")).replace(".", ","), 486, 300, 9.0)

    draw_box(c, get_plan(record, "hygiene_training"), 271, 480, 296, 12, 6.8)
    draw_box(c, get_plan(record, "professional_hygiene"), 116, 493, 451, 12, 6.8)
    draw_box(c, "зуб 17", 177, 542, 390, 12, 7.0)
    draw_box(c, "зуб 37", 147, 616, 420, 12, 7.0)
    draw_box(c, "дентальная имплантация в области 36 и 37", 94, 665, 473, 12, 6.8)
    draw_box(c, "Коронки и мостовидные протезы из ДЦ; 3 этапа; ПММА-прототип", 170, 678, 397, 12, 6.5)
    draw_box(c, "КЛКТ области 36 и 37 по показаниям", 240, 702, 327, 12, 6.8)
    draw_form_date(c, data["visit"]["dateTime"], 45, 62, 112, 737, 7.0)


def draw_page_2(c: canvas.Canvas, data: dict) -> None:
    record = data["clinicalRecord"]
    watermark(c)
    draw_form_date(c, data["visit"]["dateTime"], 439, 459, 515, 22, 7.0)
    draw_box(c, record.get("complaints", ""), 28, 52, 540, 27, 7.4, 9.0)
    draw_box(c, record.get("presentIllness", ""), 109, 88, 459, 39, 7.1, 8.4)

    health_tops = [166, 178, 190, 203, 215, 227, 240, 252, 264, 277, 289]
    health = record.get("generalHealthChecklist", [])
    for index, item in enumerate(health[: len(health_tops)]):
        answer = item.get("answer")
        if answer == "yes":
            draw_center(c, "X", 281, health_tops[index], 7.0)
        elif answer == "no":
            draw_center(c, "X", 332, health_tops[index], 7.0)
        if answer == "yes" and item.get("details"):
            draw_box(c, item["details"], 362, health_tops[index] - 1, 202, 11, 5.8)

    ext = record.get("externalExamDetails") or {}
    draw_box(c, ext.get("faceConfiguration", ""), 118, 313, 450, 16, 7.2)
    draw_box(c, ext.get("skinAndLips", ""), 195, 333, 373, 25, 7.0, 8.2)
    draw_box(c, ext.get("lymphNodes", ""), 180, 364, 388, 17, 7.0)
    draw_box(c, ext.get("tmj", ""), 174, 384, 394, 35, 7.0, 8.2)
    draw_box(c, record.get("bite", ""), 75, 434, 493, 20, 7.2)
    draw_box(c, record.get("dentalConditionText", ""), 28, 470.5, 540, 66, 6.8, 14.17)
    draw_box(c, record.get("periodontium", ""), 28, 550, 540, 35, 7.0, 8.2)
    draw_box(c, record.get("oralMucosa", ""), 28, 604, 540, 35, 7.0, 8.2)

    diagnostics = []
    for item in record.get("diagnostics", []):
        tooth = f"{item.get('toothFdi')}: " if item.get("toothFdi") else ""
        diagnostics.append(tooth + item.get("result", ""))
    draw_box(c, " ".join(diagnostics), 28, 660.5, 540, 44, 6.6, 14.17)
    diagnosis_text = " ".join(item.get("text", "") for item in record.get("diagnoses", []))
    draw_box(c, diagnosis_text, 28, 712, 540, 84, 7.0, 8.3)


def build_diary_text(data: dict) -> str:
    record = data["clinicalRecord"]
    diagnoses = " ".join(x.get("text", "") for x in record.get("diagnoses", []))
    performed_items = record.get("treatmentPerformed", [])
    performed = " ".join(x.get("text", "") for x in performed_items)
    recommendations = " ".join(record.get("recommendations", []))
    return (
        f"{short_date(data['visit']['dateTime'])}. Жалобы: {record.get('complaints', '')}\n"
        f"Status localis: {record.get('localStatus', '')}\n"
        f"Диагноз: {diagnoses}\n"
        f"ЛЕЧЕНИЕ: {performed}\n"
        f"РЕКОМЕНДАЦИИ: {recommendations}"
    )


def construction_summary(data: dict) -> str:
    result = []
    for item in data["clinicalRecord"].get("prostheticConstructions", []):
        supports = ", ".join(str(x) for x in item.get("supports", []))
        pontics = ", ".join(str(x) for x in item.get("pontics", []))
        if item.get("type") == "crown":
            result.append(f"Одиночные коронки ДЦ: {supports}.")
        elif item.get("type") == "implant_bridge":
            result.append(f"Имплант-мост: опоры {supports}; понтик {pontics}; винтовая фиксация.")
        else:
            result.append(f"Мост: опоры {supports}; понтик {pontics}.")
    return " ".join(result)


def draw_page_3(c: canvas.Canvas, data: dict) -> None:
    record = data["clinicalRecord"]
    watermark(c)
    draw_box(c, build_diary_text(data), 31, 70, 369, 285, 6.5, 12.9)
    draw_box(c, "планируется", 188, 487, 380, 14, 7.0)
    draw_box(c, "зуб 17", 205, 540, 363, 14, 7.0)
    draw_box(c, "зуб 37", 148, 620, 420, 14, 7.0)
    draw_box(c, "область 36 и 37", 190, 673, 378, 14, 7.0)
    draw_form_date(c, data["visit"]["dateTime"], 80, 97, 145, 729, 6.8)


def draw_page_4(c: canvas.Canvas, data: dict) -> None:
    watermark(c)
    draw_box(c, "11-16, 21-25, 27, 32-34, 41-45, 47", 94, 481, 210, 14, 5.9)
    draw_box(c, "25-27; 32,33,41,42; 45-47", 130, 516, 174, 14, 5.8)
    draw_box(c, "11-16, 21-24, 34, 43, 44", 94, 563, 210, 14, 6.0)
    draw_box(c, "25-27; 32,33,41,42; 45-47", 130, 598, 174, 14, 5.8)
    draw_box(c, "36,37; понтик 35", 182, 610, 122, 14, 5.8)
    draw_form_date(c, data["visit"]["dateTime"], 79, 95, 142, 692, 6.7)


def create_overlay(data: dict) -> PdfReader:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(PAGE_WIDTH, PAGE_HEIGHT), pageCompression=1)
    for draw_page in (draw_page_1, draw_page_2, draw_page_3, draw_page_4):
        draw_page(c, data)
        c.showPage()
    c.save()
    buffer.seek(0)
    return PdfReader(buffer)


def fill_pdf(template: Path, data_path: Path, output: Path) -> None:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    if data.get("status") != "approved":
        raise ValueError("PDF разрешено формировать только для записи со статусом approved")
    register_fonts()
    base = PdfReader(str(template))
    if len(base.pages) != 4:
        raise ValueError(f"Ожидалось 4 страницы шаблона, получено {len(base.pages)}")
    overlay = create_overlay(data)
    writer = PdfWriter()
    for page, layer in zip(base.pages, overlay.pages):
        page.merge_page(layer)
        writer.add_page(page)
    writer.add_metadata(
        {
            "/Title": "Форма 043/у - тестовое заполнение DentProtocol BY",
            "/Subject": f"Карта {data['cardId']}, редакция {data['revision']}",
            "/Author": "DentProtocol BY",
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        writer.write(stream)


def main() -> None:
    parser = argparse.ArgumentParser(description="Заполнение статического PDF формы 043/у v6")
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fill_pdf(args.template, args.data, args.output)


if __name__ == "__main__":
    main()
