import json
import re
import pymupdf

PDF = r"G:\Codes\Voice AI\docs\btp_report\_verify\report.pdf"
OUT = r"G:\Codes\Voice AI\docs\btp_report\report_build\pagemap.json"

doc = pymupdf.open(PDF)
texts = [p.get_text() for p in doc]

def find(needle, start=0):
    for i in range(start, len(texts)):
        if needle in texts[i]:
            return i + 1  # 1-based PDF page
    return None

ROMAN = ["", "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]

front = {}
for title, needle in [
    ("Certificate", "CERTIFICATE"),
    ("Declaration", "DECLARATION"),
    ("Acknowledgement", "ACKNOWLEDGEMENT"),
    ("Area of Work", "AREA OF WORK"),
    ("Table of Content", "TABLE OF CONTENT"),
    ("List of Figures", "LIST OF FIGURES"),
    ("List of Tables", "LIST OF TABLES"),
]:
    p = find(needle)
    front[title] = ROMAN[p - 1] if p and p - 1 < len(ROMAN) else ""

chapters = {}
chapter_titles = {
    "1": "1. INTRODUCTION",
    "2": "2. LITERATURE REVIEW",
    "3": "3. PROBLEM DEFINITION AND OBJECTIVES",
    "4": "4. PROPOSED METHODOLOGY AND WORK DESCRIPTION",
    "5": "5. PROPOSED ALGORITHMS",
    "6": "6. PROPOSED FLOWCHART",
    "7": "7. IMPLEMENTATION: TOOLS, TECHNOLOGY AND CODE",
    "8": "8. RESULT DISCUSSION AND ANALYSIS",
    "9": "9. CONCLUSION AND FUTURE SCOPE",
    "10": "REFERENCES",
}
for num, needle in chapter_titles.items():
    p = find(needle, 8)
    chapters[num] = str(p - 8) if p else ""

figs = {}
for n in range(1, 11):
    p = find(f"Fig. {n}:", 8)
    figs[str(n)] = str(p - 8) if p else ""

tables = {}
for n in range(1, 13):
    p = find(f"Table {n}:", 8)
    tables[str(n)] = str(p - 8) if p else ""

data = {"front": front, "chapters": chapters, "figs": figs, "tables": tables}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2)
print(json.dumps(data, indent=2))
