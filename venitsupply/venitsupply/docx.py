# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal Word (.docx) writer (no outside library): converts the simple HTML the reports produce
(p, br, b, i, u, span, table/tr/td/th, ol/li) into an editable Word document in TH SarabunPSK."""
from __future__ import annotations

import re
import zipfile
from html.parser import HTMLParser
from xml.sax.saxutils import escape

FONT = "TH SarabunPSK"
BASE_PT = 16


def _pt(style: str, default):
    m = re.search(r"font-size\s*:\s*([\d.]+)\s*pt", style or "")
    return float(m.group(1)) if m else default


def _attr(attrs, key, default=""):
    for k, v in attrs:
        if k == key:
            return v if v is not None else ""
    return default


class _Para:
    def __init__(self, align="", indent=0.0, size=None, space_after=0):
        self.align, self.indent, self.size, self.after = align, indent, size, space_after
        self.runs: list[tuple] = []          # (text|None for break, bold, italic, underline, size, color)

    def empty(self):
        return not any(r[0] and r[0].strip() for r in self.runs)


class _Conv(HTMLParser):
    def __init__(self, base_pt):
        super().__init__(convert_charrefs=True)
        self.base = base_pt
        self.body: list = []
        self.stack = [self.body]            # where paragraphs go (body or a table cell)
        self.tables: list = []
        self.p: _Para | None = None
        self.bold = self.ital = self.und = 0
        self.size = [None]
        self.color = [None]
        self.align = [""]
        self.lists: list[list[int]] = []

    # ---- helpers
    def _open_p(self, align="", indent=0.0, size=None, after=0):
        self._close_p()
        self.p = _Para(align or self.align[-1], indent, size, after)

    def _close_p(self):
        if self.p is not None:
            self.stack[-1].append(self.p)
            self.p = None

    def _ensure_p(self):
        if self.p is None:
            self._open_p()

    def _scale(self, html_pt):
        return None if html_pt is None else round(html_pt * BASE_PT / self.base * 2) / 2

    # ---- parser callbacks
    def handle_starttag(self, tag, attrs):
        style = _attr(attrs, "style")
        if tag in ("html", "body"):
            self.base = _pt(style, self.base)
        elif tag == "p":
            al = _attr(attrs, "align") or (re.search(r"text-align\s*:\s*(\w+)", style or "") or [None, ""])[1]
            m = re.search(r"text-indent\s*:\s*([\d.]+)\s*em", style or "")
            self._open_p(al, float(m.group(1)) if m else 0.0, self._scale(_pt(style, None)),
                         after=0 if "margin:0" in (style or "").replace(" ", "") else 60)
            if "font-size" in (style or ""):
                self.size.append(self._scale(_pt(style, None)))
            else:
                self.size.append(self.size[-1])
        elif tag == "br":
            self._ensure_p()
            self.p.runs.append((None, 0, 0, 0, None, None))
        elif tag in ("b", "strong", "th"):
            if tag == "th":
                self._cell(attrs, header=True)
            self.bold += 1
        elif tag in ("i", "em"):
            self.ital += 1
        elif tag == "u":
            self.und += 1
        elif tag in ("span", "font"):
            self.size.append(self._scale(_pt(style, None)) or self.size[-1])
            m = re.search(r"color\s*:\s*#([0-9A-Fa-f]{6})", style or "")
            self.color.append(m.group(1) if m else self.color[-1])
        elif tag == "table":
            self._close_p()
            t = dict(border=_attr(attrs, "border", "0") not in ("", "0"), rows=[], width=_attr(attrs, "width"))
            self.stack[-1].append(t)
            self.tables.append(t)
        elif tag == "tr" and self.tables:
            self.tables[-1]["rows"].append([])
        elif tag == "td":
            self._cell(attrs)
        elif tag in ("ol", "ul"):
            self._close_p()
            self.lists.append([0 if tag == "ol" else -1])
        elif tag == "li":
            self._open_p()
            if self.lists:
                lst = self.lists[-1]
                if lst[0] >= 0:
                    lst[0] += 1
                    self.p.runs.append((f"{lst[0]}. ", self.bold, 0, 0, self.size[-1], self.color[-1]))
                else:
                    self.p.runs.append(("• ", self.bold, 0, 0, self.size[-1], self.color[-1]))
        elif tag == "div":
            self._close_p()
            self.align.append(_attr(attrs, "align") or self.align[-1])

    def _cell(self, attrs, header=False):
        if not self.tables:
            return
        self._close_p()
        if not self.tables[-1]["rows"]:
            self.tables[-1]["rows"].append([])
        cell = dict(paras=[], align=_attr(attrs, "align"), valign=_attr(attrs, "valign"),
                    span=int(_attr(attrs, "colspan", "1") or 1), width=_attr(attrs, "width"), header=header,
                    shade=None)
        st = _attr(attrs, "style")
        m = re.search(r"background\s*:\s*#([0-9A-Fa-f]{6})", st or "")
        if m:
            cell["shade"] = m.group(1)
        self.tables[-1]["rows"][-1].append(cell)
        self.stack.append(cell["paras"])
        self.align.append(cell["align"] or ("center" if header else ""))

    def handle_endtag(self, tag):
        if tag == "p":
            self._close_p()
            if len(self.size) > 1:
                self.size.pop()
        elif tag in ("b", "strong"):
            self.bold = max(0, self.bold - 1)
        elif tag in ("i", "em"):
            self.ital = max(0, self.ital - 1)
        elif tag == "u":
            self.und = max(0, self.und - 1)
        elif tag in ("span", "font"):
            if len(self.size) > 1:
                self.size.pop()
            if len(self.color) > 1:
                self.color.pop()
        elif tag in ("td", "th"):
            if tag == "th":
                self.bold = max(0, self.bold - 1)
            self._close_p()
            if len(self.stack) > 1:
                self.stack.pop()
            if len(self.align) > 1:
                self.align.pop()
        elif tag == "table":
            self._close_p()
            if self.tables:
                self.tables.pop()
        elif tag == "li":
            self._close_p()
        elif tag in ("ol", "ul"):
            self._close_p()
            if self.lists:
                self.lists.pop()
        elif tag == "div":
            self._close_p()
            if len(self.align) > 1:
                self.align.pop()

    def handle_data(self, data):
        if not data:
            return
        text = re.sub(r"[ \t\r\n]+", " ", data)
        if not text.strip() and self.p is None:
            return
        self._ensure_p()
        self.p.runs.append((text, self.bold, self.ital, self.und, self.size[-1], self.color[-1]))

    def close(self):
        super().close()
        self._close_p()


# ------------------------------------------------------------------ XML
def _run_xml(text, bold, ital, und, size, color):
    sz = int(round((size or BASE_PT) * 2))
    pr = [f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:eastAsia="{FONT}" w:cs="{FONT}"/>']
    if bold:
        pr.append("<w:b/><w:bCs/>")
    if ital:
        pr.append("<w:i/><w:iCs/>")
    if und:
        pr.append('<w:u w:val="single"/>')
    if color:
        pr.append(f'<w:color w:val="{color}"/>')
    pr.append(f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/><w:lang w:val="th-TH" w:bidi="th-TH"/>')
    rpr = "<w:rPr>" + "".join(pr) + "</w:rPr>"
    if text is None:
        return f"<w:r>{rpr}<w:br/></w:r>"
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def _para_xml(p: _Para, cell=False):
    jc = {"center": "center", "right": "right", "justify": "both"}.get((p.align or "").lower(), "")
    ppr = ['<w:spacing w:before="0" w:after="%d" w:line="240" w:lineRule="auto"/>' % (0 if cell else p.after)]
    if jc:
        ppr.append(f'<w:jc w:val="{jc}"/>')
    if p.indent:
        ppr.append(f'<w:ind w:firstLine="{int(p.indent * 320)}"/>')
    runs = list(p.runs)
    while runs and runs[0][0] is not None and not runs[0][0].strip() and len(runs) > 1:
        runs.pop(0)
    if runs and runs[0][0]:
        runs[0] = (runs[0][0].lstrip(),) + runs[0][1:]
    body = "".join(_run_xml(*r) for r in runs) or _run_xml("", 0, 0, 0, p.size, None)
    return f'<w:p><w:pPr>{"".join(ppr)}</w:pPr>{body}</w:p>'


def _table_xml(t, page_w):
    rows = [r for r in t["rows"] if r]
    if not rows:
        return ""
    ncol = max(sum(c["span"] for c in r) for r in rows)
    widths = [page_w // ncol] * ncol
    first = rows[0]
    if sum(c["span"] for c in first) == ncol:
        ws = []
        for c in first:
            m = re.match(r"(\d+)%", c["width"] or "")
            ws += [int(page_w * int(m.group(1)) / 100 / c["span"]) if m else 0] * c["span"]
        if any(ws):
            rest = page_w - sum(ws)
            zero = [i for i, w in enumerate(ws) if not w]
            for i in zero:
                ws[i] = max(400, rest // len(zero)) if zero else ws[i]
            widths = ws
    b = "single" if t["border"] else "nil"
    borders = "".join(f'<w:{s} w:val="{b}" w:sz="4" w:space="0" w:color="000000"/>'
                      for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="{page_w}" w:type="dxa"/><w:tblBorders>{borders}</w:tblBorders>'
           '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="57" w:type="dxa"/>'
           '<w:right w:w="57" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>'
           + "".join(f'<w:gridCol w:w="{w}"/>' for w in widths) + "</w:tblGrid>"]
    for r in rows:
        out.append("<w:tr><w:trPr><w:cantSplit/></w:trPr>")
        col = 0
        for c in r:
            w = sum(widths[col:col + c["span"]]) or widths[-1]
            col += c["span"]
            pr = f'<w:tcW w:w="{w}" w:type="dxa"/>'
            if c["span"] > 1:
                pr += f'<w:gridSpan w:val="{c["span"]}"/>'
            if c["shade"]:
                pr += f'<w:shd w:val="clear" w:color="auto" w:fill="{c["shade"]}"/>'
            va = {"middle": "center", "top": "top", "bottom": "bottom"}.get(c["valign"] or "", "center")
            pr += f'<w:vAlign w:val="{va}"/>'
            paras = [p for p in c["paras"] if isinstance(p, _Para)] or [_Para(c["align"])]
            inner = "".join(_para_xml(p, cell=True) if isinstance(p, _Para) else _table_xml(p, w)
                            for p in (c["paras"] or paras))
            if not inner.rstrip().endswith("</w:p>"):
                inner += "<w:p/>"
            out.append(f"<w:tc><w:tcPr>{pr}</w:tcPr>{inner}</w:tc>")
        for _ in range(ncol - col):
            out.append(f'<w:tc><w:tcPr><w:tcW w:w="{widths[-1]}" w:type="dxa"/></w:tcPr><w:p/></w:tc>')
        out.append("</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def write(path, html: str, landscape=False, base_pt=14.0) -> None:
    conv = _Conv(base_pt)
    conv.feed(html)
    conv.close()
    pw, ph = (16838, 11906) if landscape else (11906, 16838)
    left, right, top, bottom = (1134, 1134, 1134, 1134) if landscape else (1701, 1134, 1418, 1134)
    page_w = pw - left - right
    parts = []
    for blk in conv.body:
        if isinstance(blk, _Para):
            parts.append(_para_xml(blk))
        else:
            parts.append(_table_xml(blk, page_w))
            parts.append('<w:p><w:pPr><w:spacing w:after="0"/></w:pPr></w:p>')
    orient = ' w:orient="landscape"' if landscape else ""
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
           'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>'
           + "".join(parts)
           + f'<w:sectPr><w:pgSz w:w="{pw}" w:h="{ph}"{orient}/>'
           f'<w:pgMar w:top="{top}" w:right="{right}" w:bottom="{bottom}" w:left="{left}" w:header="567" '
           'w:footer="567" w:gutter="0"/></w:sectPr></w:body></w:document>')
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults>'
              f'<w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:eastAsia="{FONT}" w:cs="{FONT}"/>'
              f'<w:sz w:val="{BASE_PT * 2}"/><w:szCs w:val="{BASE_PT * 2}"/><w:lang w:val="th-TH" w:bidi="th-TH"/>'
              '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
              '</w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
              '<w:name w:val="Normal"/></w:style></w:styles>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                   '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/_rels/document.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", styles)
