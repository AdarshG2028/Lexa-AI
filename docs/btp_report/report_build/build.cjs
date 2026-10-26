/* Build the B.Tech project report from the official 2026 template structure.
 * Formatting rules taken from the template:
 *   main heading 16 pt, sub heading 14 pt, body 12 pt, caption 11 pt,
 *   references 10 pt, Times New Roman, line spacing 1.15, justified body.
 */
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell,
  WidthType, AlignmentType, BorderStyle, Footer, PageNumber, NumberFormat,
  ShadingType, VerticalAlign, TableLayoutType, LevelFormat, LineRuleType,
} = require("docx");

const content = [
  ...require("./content1.cjs"),
  ...require("./content2.cjs"),
  ...require("./content3.cjs"),
];

const ROOT = path.resolve(__dirname, "..");
const FIG_DIR = path.join(ROOT, "figures", "trim");
const PAGEMAP_PATH = path.join(__dirname, "pagemap.json");
const PAGEMAP = fs.existsSync(PAGEMAP_PATH)
  ? JSON.parse(fs.readFileSync(PAGEMAP_PATH, "utf8"))
  : { front: {}, chapters: {}, figs: {}, tables: {} };
const MEDIA_DIR = path.join(ROOT, "template_media");
const OUT = path.join(ROOT, "B.Tech_Project_Report_Lexa.docx");

const FONT = "Times New Roman";
const PAGE_W = 11906; // A4 width, twips
const PAGE_H = 16838;
const MARGIN = 1440;
const CONTENT_W = PAGE_W - 2 * MARGIN; // 9026

/* ------------------------------------------------------------------ styles */
const styles = {
  default: {
    document: {
      run: { font: FONT, size: 24, color: "000000" },
      paragraph: { spacing: { line: 276, lineRule: LineRuleType.AUTO } },
    },
  },
  paragraphStyles: [
    {
      id: "BTPH1",
      name: "BTP Heading 1",
      basedOn: "Normal",
      next: "Normal",
      quickFormat: true,
      run: { font: FONT, size: 32, bold: true, color: "000000" },
      paragraph: {
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 300, line: 276, lineRule: LineRuleType.AUTO },
        outlineLevel: 0,
        keepNext: true,
      },
    },
    {
      id: "BTPH2",
      name: "BTP Heading 2",
      basedOn: "Normal",
      next: "Normal",
      quickFormat: true,
      run: { font: FONT, size: 28, bold: true, color: "000000" },
      paragraph: {
        alignment: AlignmentType.LEFT,
        spacing: { before: 240, after: 100, line: 276, lineRule: LineRuleType.AUTO },
        outlineLevel: 1,
        keepNext: true,
      },
    },
    {
      id: "BTPCaption",
      name: "BTP Caption",
      basedOn: "Normal",
      next: "Normal",
      run: { font: FONT, size: 22, color: "000000" },
      paragraph: {
        alignment: AlignmentType.CENTER,
        spacing: { before: 80, after: 200, line: 240, lineRule: LineRuleType.AUTO },
      },
    },
  ],
};

/* --------------------------------------------------------------- helpers */
function splitInline(text) {
  // supports **bold** and *italic*; content uses neither heavily but keep it general
  const parts = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push({ text: text.slice(last, m.index) });
    const tok = m[0];
    if (tok.startsWith("**")) parts.push({ text: tok.slice(2, -2), bold: true });
    else parts.push({ text: tok.slice(1, -1), italics: true });
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push({ text: text.slice(last) });
  return parts;
}

function runs(text, opts = {}) {
  const parts = splitInline(text);
  return parts.map(
    (p) =>
      new TextRun({
        text: p.text,
        bold: opts.bold || p.bold,
        italics: opts.italics || p.italics,
        font: opts.font || FONT,
        size: opts.size || 24,
        color: opts.color || "000000",
      })
  );
}

function body(text, opts = {}) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { before: 0, after: 120, line: 276, lineRule: LineRuleType.AUTO },
    indent: opts.indent,
    keepNext: opts.keepNext === true,
    children: runs(text, opts),
  });
}

function h1(text, opts = {}) {
  return new Paragraph({
    style: "BTPH1",
    pageBreakBefore: opts.pageBreak !== false,
    children: [new TextRun({ text, font: FONT, size: 32, bold: true })],
  });
}

function h2(text) {
  return new Paragraph({
    style: "BTPH2",
    children: [new TextRun({ text, font: FONT, size: 28, bold: true })],
  });
}

function caption(label, text, opts = {}) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: {
      before: opts.before === undefined ? 80 : opts.before,
      after: opts.after === undefined ? 200 : opts.after,
      line: 240,
      lineRule: LineRuleType.AUTO,
    },
    keepNext: opts.keepNext === true,
    children: [
      new TextRun({ text: label + ": ", font: FONT, size: 22, bold: true }),
      new TextRun({ text, font: FONT, size: 22 }),
    ],
  });
}

function blank(size = 24, after = 0) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after, line: 240, lineRule: LineRuleType.AUTO },
    children: [new TextRun({ text: "", font: FONT, size })],
  });
}

function centerLine(text, opts = {}) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: opts.after === undefined ? 60 : opts.after, line: 276, lineRule: LineRuleType.AUTO },
    children: runs(text, { size: opts.size || 24, bold: opts.bold }),
  });
}

function tableFrom(t) {
  const keepTogether = t.rows.length <= 7;
  const fs_ = t.small ? 20 : 22;
  const vpad = t.small ? 45 : 70;
  let widths = t.widths.slice();
  let sum = widths.reduce((a, b) => a + b, 0);
  const limit = CONTENT_W - 20;
  if (sum > limit) {
    const f = limit / sum;
    widths = widths.map((w) => Math.round(w * f));
    sum = widths.reduce((a, b) => a + b, 0);
  }

  const styleCell = (text, w, header, keepNext) =>
    new TableCell({
      width: { size: w, type: WidthType.DXA },
      verticalAlign: VerticalAlign.CENTER,
      shading: header ? { type: ShadingType.CLEAR, fill: "D9E2F3", color: "auto" } : undefined,
      margins: { top: vpad, bottom: vpad, left: 90, right: 90 },
      children: [
        new Paragraph({
          alignment: header ? AlignmentType.CENTER : AlignmentType.LEFT,
          spacing: { before: 0, after: 0, line: 240, lineRule: LineRuleType.AUTO },
          keepNext: keepNext === true,
          children: [
            new TextRun({
              text,
              font: FONT,
              size: fs_,
              bold: !!header,
            }),
          ],
        }),
      ],
    });

  const rows = [
    new TableRow({
      tableHeader: true,
      cantSplit: true,
      children: t.head.map((h, i) => styleCell(h, widths[i], true, keepTogether)),
    }),
    ...t.rows.map(
      (r, ri) =>
        new TableRow({
          cantSplit: true,
          children: r.map((c, i) =>
            styleCell(c, widths[i], false, keepTogether && ri < t.rows.length - 1)
          ),
        })
    ),
  ];

  const blocks = [caption("Table " + t.n, t.caption, { keepNext: true, after: 120 })];
  blocks.push(
    new Table({
      columnWidths: widths,
      width: { size: sum, type: WidthType.DXA },
      alignment: AlignmentType.CENTER,
      layout: TableLayoutType.FIXED,
      borders: {
        top: { style: BorderStyle.SINGLE, size: 4, color: "7F7F7F" },
        bottom: { style: BorderStyle.SINGLE, size: 4, color: "7F7F7F" },
        left: { style: BorderStyle.SINGLE, size: 4, color: "A6A6A6" },
        right: { style: BorderStyle.SINGLE, size: 4, color: "A6A6A6" },
        insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "BFBFBF" },
        insideVertical: { style: BorderStyle.SINGLE, size: 2, color: "BFBFBF" },
      },
      rows,
    })
  );
  blocks.push(blank(12, 60));
  return blocks;
}

const FIG_WIDTHS = {
  "fig01_architecture.png": 6.2,
  "fig02_sequence.png": 6.2,
  "fig03_pronunciation.png": 6.2,
  "fig04_er.png": 6.2,
  "fig05_context_dfd.png": 6.2,
  "fig06_level1_dfd.png": 6.2,
  "fig07_video_workflow.png": 5.4,
  "fig08_language_bridge.png": 6.2,
  "fig09_deployment.png": 6.2,
  "fig10_frontend_flow.png": 6.2,
};

function figure(f) {
  const p = path.join(FIG_DIR, f.file);
  const buf = fs.readFileSync(p);
  const w = buf.readUInt32BE(16);
  const h = buf.readUInt32BE(20);
  const dispW = Math.round((FIG_WIDTHS[f.file] || 6.0) * 96);
  const dispH = Math.round((dispW * h) / w);
  const img = new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 0, line: 240, lineRule: LineRuleType.AUTO },
    keepNext: true,
    children: [
      new ImageRun({ data: buf, type: "png", transformation: { width: dispW, height: dispH } }),
    ],
  });
  return [img, caption("Fig. " + f.n, f.caption, { before: 60, after: 240 })];
}

function bulletList(items, numbered, instance) {
  return items.map(
    (it) =>
      new Paragraph({
        numbering: numbered
          ? { reference: "num-list", level: 0, instance }
          : { reference: "bullet-list", level: 0 },
        alignment: AlignmentType.JUSTIFIED,
        spacing: { before: 0, after: 80, line: 276, lineRule: LineRuleType.AUTO },
        children: runs(it),
      })
  );
}

/* -------------------------------------------------- front matter builders */
function titlePage() {
  const logo = fs.readFileSync(path.join(MEDIA_DIR, "image1.jpeg"));
  return [
    blank(24, 0),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 160, line: 240, lineRule: LineRuleType.AUTO },
      children: [
        new ImageRun({ data: logo, type: "jpg", transformation: { width: 112, height: 112 } }),
      ],
    }),
    centerLine("LEXA: AN AI VOICE CONVERSATION AND SPEECH COACH", { bold: true, size: 32, after: 220 }),
    centerLine("PROJECT REPORT [Phase-I/II/III]", { bold: true, after: 220 }),
    centerLine("Submitted in partial fulfillment for the award of the degree of", { after: 80 }),
    centerLine("BACHELOR OF TECHNOLOGY", { bold: true, after: 80 }),
    centerLine("Department of Information Technology", { after: 260 }),
    centerLine("Submitted to", { after: 80 }),
    centerLine("INDIAN INSTITUTE OF INFORMATION TECHNOLOGY", { bold: true, after: 40 }),
    centerLine("BHOPAL (M.P.)", { bold: true, after: 300 }),
    centerLine("Submitted by", { after: 80 }),
    centerLine("Name of the student1 (Scholar number and Semester)", { after: 40 }),
    centerLine("Name of the student2 (Scholar number and Semester)", { after: 300 }),
    centerLine("Under the supervision of", { after: 80 }),
    centerLine("Name of the supervisor", { after: 40 }),
    centerLine("Designation of the supervisor", { after: 40 }),
    centerLine("(Name of Department)", { after: 320 }),
    centerLine("Month & Year", { after: 320 }),
    centerLine("INDIAN INSTITUTE OF INFORMATION TECHNOLOGY", { bold: true, after: 40 }),
    centerLine("BHOPAL (M.P.)", { bold: true, after: 0 }),
  ];
}

function signatureTable(left, right) {
  const cell = (text) =>
    new TableCell({
      width: { size: 4513, type: WidthType.DXA },
      margins: { top: 40, bottom: 40, left: 0, right: 80 },
      children: text.split("\n").map(
        (line) =>
          new Paragraph({
            spacing: { before: 0, after: 40, line: 240, lineRule: LineRuleType.AUTO },
            children: [new TextRun({ text: line, font: FONT, size: 24, bold: /Coordinator|Supervisor/.test(line) })],
          })
      ),
    });
  return new Table({
    columnWidths: [4513, 4513],
    width: { size: 9026, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    borders: {
      top: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      bottom: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      insideHorizontal: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      insideVertical: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
    },
    rows: [new TableRow({ children: [cell(left), cell(right)] })],
  });
}

function certificatePage() {
  return [
    h1("CERTIFICATE", { pageBreak: false }),
    blank(24, 60),
    body(
      "This is to certify that the work embodied in this report entitled “PROJECT TITLE” has been satisfactorily completed by STUDENT NAME (SCHOLAR NO.) It is a bonafide piece of work, carried out under our guidance in the Department of Information Technology, Indian Institute of Information Technology, Bhopal for the partial fulfillment of the Bachelor of Engineering during the academic year 202_-__."
    ),
    blank(24, 240),
    new Paragraph({
      spacing: { before: 0, after: 60, line: 276, lineRule: LineRuleType.AUTO },
      children: [new TextRun({ text: "Date:", font: FONT, size: 24 })],
    }),
    blank(24, 720),
    signatureTable(
      "Head/Department Coordinator,\nDepartment of IT,\nIIIT Bhopal (M.P.)",
      "Name of Supervisor(s),\nDesignation,\nDepartment,\nIIIT Bhopal (M.P.)"
    ),
  ];
}

function declarationPage() {
  return [
    h1("DECLARATION", { pageBreak: true }),
    blank(24, 60),
    body(
      "We hereby declare that the following major project synopsis entitled “PROJECT TITLE” presented in the is the partial fulfillment of the requirements for the award of the degree of Bachelor of Technology in Information Technology. It is an authentic documentation of our original work carried out under the able guidance of Name of Supervisors. The work has been carried out entirely at the Indian Institute of Information Technology, Bhopal. The project work presented has not been submitted in part or whole to award of any degree or professional diploma in any other institute or organization."
    ),
    body(
      "We, with this, declare that the facts mentioned above are true to the best of our knowledge. In case of any unlikely discrepancy that may occur, we will be the ones to take responsibility."
    ),
    blank(24, 900),
    new Table({
      columnWidths: [6000, 3026],
      width: { size: 9026, type: WidthType.DXA },
      layout: TableLayoutType.FIXED,
      borders: {
        top: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        bottom: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        insideHorizontal: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        insideVertical: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      },
      rows: [
        ["Name of the student1 (Scholar number)", "Sign of student1"],
        ["Name of the student2 (Scholar number)", "Sign of student2"],
      ].map(
        (r) =>
          new TableRow({
            children: r.map(
              (c, i) =>
                new TableCell({
                  width: { size: i === 0 ? 6000 : 3026, type: WidthType.DXA },
                  margins: { top: 240, bottom: 40, left: 0, right: 80 },
                  children: [
                    new Paragraph({
                      spacing: { before: 0, after: 40, line: 240, lineRule: LineRuleType.AUTO },
                      children: [new TextRun({ text: c, font: FONT, size: 24 })],
                    }),
                  ],
                })
            ),
          })
      ),
    }),
  ];
}

function acknowledgementPage() {
  const paras = [
    "We, [Student 1 Name] and [Student 2 Name], would like to express our sincere gratitude to everyone who supported and guided us throughout the successful completion of our minor project titled \"[Project Title]\".",
    "First and foremost, we would like to extend our heartfelt thanks to our esteemed Director, [Director's Name], for providing us with the necessary resources and facilities for conducting our project. His/her encouragement and vision played a key role in helping us accomplish our goals.",
    "We are deeply grateful to our Project Guide, [Guide's Name], for his/her constant guidance, invaluable suggestions, and expert advice throughout the project. His/her knowledge and insights helped us enhance the quality of our work, and his/her support kept us motivated during difficult times.",
    "Our sincere thanks to the Department Coordinator, [Coordinator's Name], for the valuable support and encouragement provided during completion of the project.",
    "We would also like to express our gratitude to all the faculties of the [Department Name] for their valuable guidance and support in clarifying doubts and providing us with the right direction throughout the smooth execution of our project.",
    "A special thanks to our friends for their continuous support, valuable suggestions, and helping us during various stages of the project. Their insights and encouragement motivated us to keep working on the project with enthusiasm.",
    "Last but certainly not the least, we would like to express our deepest gratitude to our parents and family members for their love, patience, and continuous moral support throughout the course of this project. Their understanding and encouragement were the driving force behind our efforts.",
    "We are truly thankful to everyone who directly or indirectly contributed to the success of this project. Without their assistance and support, this project would not have been possible.",
  ];
  return [
    h1("ACKNOWLEDGEMENT", { pageBreak: true }),
    blank(24, 40),
    ...paras.map((p) => body(p)),
    blank(24, 200),
    body("[Student 1 Name]"),
    body("[Student 2 Name]"),
    body("[Roll Numbers]"),
  ];
}

function areaOfWorkPage() {
  const paras = [
    "The work reported in this project lies in the area of applied speech and language engineering, at the intersection of automatic speech recognition, natural language processing, phonetics and web application development. Its subject is computer-assisted language learning: the use of speech and language models not to replace a teacher, but to give a learner a structured account of their own spoken performance.",
    "On the speech side, the project covers the acquisition and normalisation of audio, voice-activity detection in the browser, routing between speech-recognition providers according to the language being spoken, and phoneme-level acoustic analysis using a self-supervised speech model. On the language side, it covers conversational response generation, structured extraction of grammatical and lexical feedback, and the validation of that feedback against the learner's transcript. The language-bridge component extends the work to multilingual and code-mixed settings, where the learner's language, its script and its English loanwords all have to be modelled explicitly.",
    "On the software side, the project is a full-stack web system. It includes a typed HTTP API, asynchronous database persistence, replaceable provider adapters with graceful fallback, deterministic scoring, an offline test suite, a React front end with server-side rendering, and a containerised deployment on managed infrastructure. The engineering emphasis is on dependability and explainability: every score must be traceable to evidence, and every optional component must degrade without breaking a session.",
    "The project therefore belongs to the broader area of intelligent tutoring and speech-enabled interfaces, with a specific contribution in making multi-dimensional spoken-language feedback practical on modest, commodity infrastructure.",
  ];
  return [h1("AREA OF WORK", { pageBreak: true }), blank(24, 40), ...paras.map((p) => body(p))];
}

/* ------------------------------------------------------------- TOC tables */
const FRONT_PAGES = PAGEMAP.front || {};
const CHAPTER_PAGES = PAGEMAP.chapters || {};
const TOC_ROWS = [
  ["—", "Certificate", FRONT_PAGES["Certificate"] || ""],
  ["—", "Declaration", FRONT_PAGES["Declaration"] || ""],
  ["—", "Acknowledgement", FRONT_PAGES["Acknowledgement"] || ""],
  ["—", "Area of Work", FRONT_PAGES["Area of Work"] || ""],
  ["—", "List of Figures", FRONT_PAGES["List of Figures"] || ""],
  ["—", "List of Tables", FRONT_PAGES["List of Tables"] || ""],
  ["—", "Abstract", CHAPTER_PAGES["abstract"] || "1"],
  ["1", "Introduction", CHAPTER_PAGES["1"] || ""],
  ["2", "Literature Review", CHAPTER_PAGES["2"] || ""],
  ["3", "Problem Definition and Objectives", CHAPTER_PAGES["3"] || ""],
  ["4", "Proposed Methodology and Work Description", CHAPTER_PAGES["4"] || ""],
  ["5", "Proposed Algorithms", CHAPTER_PAGES["5"] || ""],
  ["6", "Proposed Flowchart, Block Diagram and Data-Flow Diagrams", CHAPTER_PAGES["6"] || ""],
  ["7", "Implementation: Tools, Technology and Code", CHAPTER_PAGES["7"] || ""],
  ["8", "Result Discussion and Analysis", CHAPTER_PAGES["8"] || ""],
  ["9", "Conclusion and Future Scope", CHAPTER_PAGES["9"] || ""],
  ["10", "References", CHAPTER_PAGES["10"] || ""],
];

function listTable(head, rows, widths) {
  const cell = (text, w, bold, align) =>
    new TableCell({
      width: { size: w, type: WidthType.DXA },
      margins: { top: 70, bottom: 70, left: 100, right: 100 },
      children: [
        new Paragraph({
          alignment: align,
          spacing: { before: 0, after: 0, line: 240, lineRule: LineRuleType.AUTO },
          children: [new TextRun({ text, font: FONT, size: 22, bold })],
        }),
      ],
    });
  const trs = [
    new TableRow({
      tableHeader: true,
      children: head.map((h, i) => cell(h, widths[i], true, AlignmentType.CENTER)),
    }),
    ...rows.map(
      (r, ri) =>
        new TableRow({
          children: r.map((c, i) =>
            cell(
              c,
              widths[i],
              false,
              i === 0 ? AlignmentType.CENTER : i === 2 ? AlignmentType.CENTER : AlignmentType.LEFT
            )
          ),
        })
    ),
  ];
  return new Table({
    columnWidths: widths,
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: "7F7F7F" },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "7F7F7F" },
      left: { style: BorderStyle.SINGLE, size: 4, color: "A6A6A6" },
      right: { style: BorderStyle.SINGLE, size: 4, color: "A6A6A6" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "BFBFBF" },
      insideVertical: { style: BorderStyle.SINGLE, size: 2, color: "BFBFBF" },
    },
    rows: trs,
  });
}

function tocPage() {
  return [
    h1("TABLE OF CONTENT", { pageBreak: true }),
    blank(24, 100),
    listTable(
      ["S. No.", "Title", "Page No."],
      TOC_ROWS,
      [1000, 6800, 1200]
    ),
  ];
}

function figuresPage() {
  const figs = content.filter((c) => c.t === "fig");
  const rows = figs.map((f) => [String(f.n), f.caption, (PAGEMAP.figs || {})[String(f.n)] || ""]);
  return [
    h1("LIST OF FIGURES", { pageBreak: true }),
    blank(24, 100),
    listTable(["Fig. No.", "Description", "Page No."], rows, [1100, 6700, 1200]),
  ];
}

function tablesPage() {
  const tbls = content.filter((c) => c.t === "tbl");
  const rows = tbls.map((t) => [String(t.n), t.caption, (PAGEMAP.tables || {})[String(t.n)] || ""]);
  return [
    h1("LIST OF TABLES", { pageBreak: true }),
    blank(24, 100),
    listTable(["Table No.", "Description", "Page No."], rows, [1200, 6600, 1200]),
  ];
}

/* --------------------------------------------------------------- body map */
function renderBody() {
  const out = [];
  let olInstance = 0;
  for (let bi = 0; bi < content.length; bi++) {
    const block = content[bi];
    const next = content[bi + 1];
    switch (block.t) {
      case "h1":
        out.push(h1(block.x, { pageBreak: true }));
        break;
      case "h2":
        out.push(h2(block.x));
        break;
      case "p":
        out.push(body(block.x, { keepNext: next && next.t === "tbl" }));
        break;
      case "eq":
        out.push(
          new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { before: 120, after: 160, line: 240, lineRule: LineRuleType.AUTO },
            children: [new TextRun({ text: block.x, font: FONT, size: 24, italics: true })],
          })
        );
        break;
      case "ul":
        out.push(...bulletList(block.items, false));
        break;
      case "ol":
        olInstance += 1;
        out.push(...bulletList(block.items, true, olInstance));
        break;
      case "fig":
        out.push(...figure(block));
        break;
      case "tbl":
        out.push(...tableFrom(block));
        break;
      case "ref":
        out.push(
          new Paragraph({
            alignment: AlignmentType.JUSTIFIED,
            spacing: { before: 0, after: 40, line: 240, lineRule: LineRuleType.AUTO },
            indent: { left: 567, hanging: 567 },
            children: [new TextRun({ text: block.x, font: FONT, size: 20 })],
          })
        );
        break;
      default:
        throw new Error("Unknown block type: " + block.t);
    }
  }
  return out;
}

/* --------------------------------------------------------------- document */
const footer = new Footer({
  children: [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 0 },
      children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 20 })],
    }),
  ],
});

const doc = new Document({
  creator: "B.Tech Project Report",
  title: "Lexa: An AI Voice Conversation and Speech Coach",
  description: "B.Tech project report",
  styles,
  numbering: {
    config: [
      {
        reference: "bullet-list",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
      {
        reference: "num-list",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN, header: 720, footer: 720 },
        },
      },
      children: titlePage(),
    },
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN, header: 720, footer: 720 },
          pageNumbers: { start: 1, formatType: NumberFormat.LOWER_ROMAN },
        },
      },
      footers: { default: footer },
      children: [
        ...certificatePage(),
        ...declarationPage(),
        ...acknowledgementPage(),
        ...areaOfWorkPage(),
        ...tocPage(),
        ...figuresPage(),
        ...tablesPage(),
      ],
    },
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN, header: 720, footer: 720 },
          pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL },
        },
      },
      footers: { default: footer },
      children: renderBody(),
    },
  ],
});

Packer.toBuffer(doc)
  .then((buf) => {
    fs.writeFileSync(OUT, buf);
    console.log("Wrote", OUT, buf.length, "bytes");
    console.log("Figures:", content.filter((c) => c.t === "fig").length, "Tables:", content.filter((c) => c.t === "tbl").length);
  })
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
