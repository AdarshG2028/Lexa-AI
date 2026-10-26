import zipfile, re, io, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
src = r"G:\downloads\Downloads\B.Tech  Project format - 2026.docx"
z = zipfile.ZipFile(src)
xml = z.read("word/document.xml").decode("utf-8")

# Extract paragraphs and table cell texts in document order.
body = xml.split("<w:body>", 1)[1]
out = []
depth_tbl = 0
pos = 0
# crude walk: handle tables by listing their cells
pattern = re.compile(r"<w:tbl>.*?</w:tbl>|<w:p\b[^>]*/>|<w:p\b.*?</w:p>", re.S)
for m in pattern.finditer(body):
    if m.start() < pos:
        continue
    frag = m.group(0)
    if frag.startswith("<w:tbl>"):
        rows = re.findall(r"<w:tr\b.*?</w:tr>", frag, re.S)
        out.append("[TABLE]")
        for r in rows:
            cells = re.findall(r"<w:tc>.*?</w:tc>", r, re.S)
            celltexts = []
            for c in cells:
                ts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", c, re.S)
                celltexts.append("".join(ts).strip())
            out.append("  | " + " | ".join(celltexts))
        out.append("[/TABLE]")
        pos = m.end()
        continue
    texts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", frag, re.S)
    t = "".join(texts)
    style = re.search(r'<w:pStyle w:val="([^"]+)"', frag)
    s = style.group(1) if style else ""
    br = "PAGEBREAK " if 'w:type="page"' in frag else ""
    # bold check
    bold = "BOLD " if "<w:b/>" in frag and not frag.startswith("<w:tbl") else ""
    align = re.search(r'<w:jc w:val="([^"]+)"', frag)
    a = align.group(1) if align else ""
    if t.strip() or br:
        out.append(f"[{s}|{a}|{bold}{br}]{t}")
    else:
        out.append("")

print("\n".join(out))
