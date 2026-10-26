import os
import pymupdf

pdf = r"G:\Codes\Voice AI\docs\btp_report\_verify\report.pdf"
out = r"C:\Users\Adarsh gopal\AppData\Local\Temp\opencode\report_pages"
os.makedirs(out, exist_ok=True)
doc = pymupdf.open(pdf)
print("pages", doc.page_count)
for i, page in enumerate(doc):
    pix = page.get_pixmap(dpi=90)
    pix.save(os.path.join(out, f"p{i+1:02d}.png"))
print("saved to", out)
