import os, sys, glob
import win32com.client

docx = r"G:\Codes\Voice AI\docs\btp_report\B.Tech_Project_Report_Lexa.docx"
pdf = r"G:\Codes\Voice AI\docs\btp_report\_verify\report.pdf"
os.makedirs(os.path.dirname(pdf), exist_ok=True)

word = win32com.client.DispatchEx("Word.Application")
word.Visible = False
word.DisplayAlerts = 0
doc = word.Documents.Open(docx, ReadOnly=False)
try:
    # update fields (none expected, but harmless)
    doc.Fields.Update()
    doc.SaveAs(pdf, FileFormat=17)
    print("pages:", doc.ComputeStatistics(2))  # wdStatisticPages
finally:
    doc.Close(False)
    word.Quit()
print("pdf:", pdf, os.path.getsize(pdf))
