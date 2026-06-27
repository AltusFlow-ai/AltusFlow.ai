"""
generate_report.py
Reads reports/report_data.json produced by hubspot_pull.py
and generates the branded AltusFlow PDF report.
"""

import os, json, io, sys
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, KeepTogether, PageBreak,
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib import colors

# ── Brand tokens ───────────────────────────────────────────────────────────────
TEAL         = colors.HexColor('#1D9E75')
TEAL_LIGHT   = colors.HexColor('#E1F5EE')
TEAL_MID     = colors.HexColor('#0F6E56')
PURPLE       = colors.HexColor('#534AB7')
PURPLE_LIGHT = colors.HexColor('#EEEDFE')
CORAL        = colors.HexColor('#D85A30')
CORAL_LIGHT  = colors.HexColor('#FAECE7')
GRAY_TEXT    = colors.HexColor('#5F5E5A')
GRAY_LIGHT   = colors.HexColor('#F1EFE8')
GRAY_MID     = colors.HexColor('#D3D1C7')
BLACK        = colors.HexColor('#2C2C2A')
WHITE        = colors.white

W, H   = letter
MARGIN = 0.6 * inch
CW     = W - 2 * MARGIN

# ── Style helper ───────────────────────────────────────────────────────────────
def ps(name, **kw):
    d = dict(fontName="Helvetica", fontSize=9, textColor=BLACK, leading=14)
    d.update(kw)
    return ParagraphStyle(name, **d)

P_BODY  = ps("body",  fontSize=9,  textColor=GRAY_TEXT, leading=15)
P_H2    = ps("h2",    fontSize=11, fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=3)
P_SMALL = ps("sm",    fontSize=7.5, textColor=GRAY_TEXT, leading=11)

# ── Custom flowables ───────────────────────────────────────────────────────────
class AccentBar(Flowable):
    def __init__(self, w, h=2.5, c=TEAL):
        super().__init__(); self._w=w; self._h=h; self._c=c
    def wrap(self, *a): return self._w, self._h
    def draw(self):
        self.canv.setFillColor(self._c)
        self.canv.rect(0, 0, self._w, self._h, fill=1, stroke=0)

class KPIGrid(Flowable):
    def __init__(self, kpis, width):
        super().__init__(); self.kpis=kpis; self._w=width
    def wrap(self, *a): return self._w, 80
    def draw(self):
        c = self.canv
        n  = len(self.kpis)
        cw = (self._w - (n - 1) * 8) / n
        for i, (label, val, delta, direction) in enumerate(self.kpis):
            x = i * (cw + 8)
            c.setFillColor(GRAY_LIGHT)
            c.roundRect(x, 0, cw, 76, 5, fill=1, stroke=0)
            c.setFont("Helvetica", 6.5); c.setFillColor(GRAY_TEXT)
            c.drawString(x + 8, 62, label.upper())
            c.setFont("Helvetica-Bold", 17); c.setFillColor(BLACK)
            c.drawString(x + 8, 38, str(val))
            dc = TEAL_MID if direction == "up" else (CORAL if direction == "down" else GRAY_TEXT)
            c.setFont("Helvetica", 7.5); c.setFillColor(dc)
            suffix = " vs prev" if direction != "flat" else ""
            c.drawString(x + 8, 10, str(delta) + suffix)

class PipelineBar(Flowable):
    def __init__(self, stages, width):
        super().__init__(); self.stages=stages; self._w=width
    def wrap(self, *a): return self._w, 58
    def draw(self):
        c  = self.canv
        n  = len(self.stages)
        bw = (self._w - (n - 1) * 10) / n
        bg = [GRAY_LIGHT, GRAY_LIGHT, TEAL_LIGHT, TEAL_LIGHT, TEAL_LIGHT]
        tc = [BLACK, BLACK, TEAL_MID, TEAL_MID, TEAL_MID]
        for i, (label, count) in enumerate(self.stages):
            x = i * (bw + 10)
            c.setFillColor(bg[min(i, 4)])
            c.roundRect(x, 0, bw, 54, 5, fill=1, stroke=0)
            c.setFillColor(tc[min(i, 4)]); c.setFont("Helvetica-Bold", 15)
            c.drawCentredString(x + bw / 2, 30, str(count))
            c.setFont("Helvetica", 6.5); c.setFillColor(GRAY_TEXT)
            c.drawCentredString(x + bw / 2, 10, label)
            if i < n - 1:
                ax = x + bw + 2; ay = 27
                c.setStrokeColor(GRAY_MID); c.setLineWidth(0.7)
                c.line(ax, ay, ax + 6, ay)
                c.setFillColor(GRAY_MID)
                p = c.beginPath()
                p.moveTo(ax+6, ay+3); p.lineTo(ax+10, ay); p.lineTo(ax+6, ay-3)
                p.close(); c.drawPath(p, fill=1, stroke=0)

class FunnelViz(Flowable):
    def __init__(self, stages, width):
        super().__init__(); self.stages=stages; self._w=width
    def wrap(self, *a): return self._w, 145
    def draw(self):
        c = self.canv
        rh = 25; gap = 5; max_val = self.stages[0][1]
        bar_x = 108; bar_w = self._w - bar_x - 48
        palette = [TEAL, TEAL, PURPLE, PURPLE, CORAL]
        for i, (label, val) in enumerate(self.stages):
            y   = self._w  # unused — recalc
            y   = 145 - (i + 1) * (rh + gap)
            pct = val / max_val if max_val else 0
            c.setFillColor(GRAY_LIGHT)
            c.roundRect(bar_x, y, bar_w, rh, 3, fill=1, stroke=0)
            c.setFillColor(palette[min(i, 4)])
            c.roundRect(bar_x, y, max(bar_w * pct, 4), rh, 3, fill=1, stroke=0)
            c.setFont("Helvetica", 7.5); c.setFillColor(GRAY_TEXT)
            c.drawRightString(bar_x - 6, y + 8, label)
            c.setFont("Helvetica-Bold", 7.5); c.setFillColor(BLACK)
            c.drawString(bar_x + bar_w * pct + 6, y + 8, f"{val:,}")

# ── Page header/footer ─────────────────────────────────────────────────────────
def on_page(canvas, doc, data):
    canvas.saveState()
    canvas.setFillColor(BLACK)
    canvas.rect(0, H - 0.42 * inch, W, 0.42 * inch, fill=1, stroke=0)
    canvas.setFillColor(TEAL)
    canvas.rect(0, H - 0.44 * inch, 0.16 * inch, 0.02 * inch, fill=1, stroke=0)
    canvas.setFillColor(WHITE); canvas.setFont("Helvetica-Bold", 8.5)
    canvas.drawString(MARGIN, H - 0.27 * inch, "ALTUSFLOW")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(W - MARGIN, H - 0.27 * inch,
                           f"{data['client_name']}  ·  {data['month']}")
    canvas.setFillColor(GRAY_MID)
    canvas.rect(MARGIN, 0.32 * inch, CW, 0.4, fill=1, stroke=0)
    canvas.setFont("Helvetica", 6.5); canvas.setFillColor(GRAY_TEXT)
    canvas.drawString(MARGIN, 0.20 * inch,
                      f"Confidential  ·  {data['client_id']}  ·  {data['prepared_by']}")
    canvas.drawRightString(W - MARGIN, 0.20 * inch, f"Page {doc.page}")
    canvas.restoreState()

# ── Build PDF ──────────────────────────────────────────────────────────────────
def build_report(data, output_path):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=0.65 * inch, bottomMargin=0.55 * inch,
    )

    def _page(canvas, doc):
        on_page(canvas, doc, data)

    s = []

    # Title
    s.append(Spacer(1, 0.1 * inch))
    s.append(Paragraph("<b>Monthly performance report</b>",
                        ps("t", fontSize=18, fontName="Helvetica-Bold", leading=22)))
    s.append(Spacer(1, 3))
    s.append(Paragraph(f"{data['client_name']}  ·  {data['month']}",
                        ps("ts", fontSize=10, textColor=GRAY_TEXT)))
    s.append(Spacer(1, 8))
    s.append(AccentBar(CW))
    s.append(Spacer(1, 0.14 * inch))

    # Executive summary (AI-generated narrative if present, else auto-text)
    s.append(Paragraph("Executive summary", P_H2))
    summary = data.get("summary") or (
        f"{data['client_name']} recorded {data['raw']['leads_this']} new leads "
        f"and {data['raw']['closed_this']} closed deals in {data['month']}. "
        f"Full vertical breakdown and pipeline analysis below."
    )
    s.append(Paragraph(summary, P_BODY))
    s.append(Spacer(1, 8))

    # Close rate flag (auto-inserts only when direction == "down")
    if data.get("close_rate_dir") == "down":
        flag_tbl = Table([[Paragraph(
            f"Flag: Close rate dropped {data['close_rate_delta']} to "
            f"{data['close_rate_val']}. See priority recommendation on page 2.",
            ps("f", fontSize=8, fontName="Helvetica-Bold",
               textColor=colors.HexColor('#712B13'))
        )]], colWidths=[CW])
        flag_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), CORAL_LIGHT),
            ("LEFTPADDING", (0,0), (-1,-1), 12), ("RIGHTPADDING", (0,0), (-1,-1), 12),
            ("TOPPADDING",  (0,0), (-1,-1), 9),  ("BOTTOMPADDING",(0,0), (-1,-1), 9),
            ("LINEBEFORE",  (0,0), (0,-1),  3, CORAL),
        ]))
        s.append(flag_tbl)
    s.append(Spacer(1, 0.18 * inch))

    # KPIs
    s.append(Paragraph("Key performance indicators", P_H2))
    s.append(Spacer(1, 5))
    s.append(KPIGrid(data["kpis"], CW))
    s.append(Spacer(1, 0.18 * inch))

    # Pipeline
    s.append(Paragraph("Pipeline snapshot", P_H2))
    s.append(Spacer(1, 5))
    s.append(PipelineBar(data["pipeline"], CW))
    s.append(Spacer(1, 0.18 * inch))

    # Funnel + vertical split
    vl    = data["vertical_leads"]
    total = sum(vl.values()) or 1
    funnel_w = CW * 0.60

    legend_items = []
    vert_colors  = [TEAL, PURPLE, CORAL]
    for idx, (vname, vleads) in enumerate(vl.items()):
        pct = round(vleads / total * 100)
        hex_str = vert_colors[idx].hexval()[2:]
        legend_items.append(Paragraph(
            f'<font color="#{hex_str}"><b>{vname}</b></font>  {vleads} leads  ({pct}%)',
            ps(f"li{idx}", fontSize=8, leading=16, textColor=GRAY_TEXT)
        ))

    chart_tbl = Table([[
        [Paragraph("Conversion funnel", P_H2), Spacer(1,5),
         FunnelViz(data["funnel"], funnel_w)],
        [Paragraph("Lead source split", P_H2), Spacer(1,12)] + legend_items,
    ]], colWidths=[funnel_w, CW - funnel_w])
    chart_tbl.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (0,-1),  20),
    ]))
    s.append(chart_tbl)

    # Page 2 — vertical detail
    s.append(PageBreak())
    s.append(Spacer(1, 0.08 * inch))
    s.append(Paragraph("Vertical performance breakdown", P_H2))
    s.append(Spacer(1, 8))

    vert_meta = [
        ("Inbound Magnet",    vl.get("Inbound Magnet",0),    TEAL,   TEAL_LIGHT),
        ("Outbound Hunter",   vl.get("Outbound Hunter",0),   PURPLE, PURPLE_LIGHT),
        ("Conversion Engine", vl.get("Conversion Engine",0), CORAL,  CORAL_LIGHT),
    ]
    vert_narratives = data.get("vertical_narratives", {})
    default_texts   = {
        "Inbound Magnet":    "Meta ad campaigns drove this month's Inbound Magnet results. Review creative performance and CPL trends in the dashboard.",
        "Outbound Hunter":   "Intent-based outbound sequences ran this month. Review signal phrases and pitch conversion rates.",
        "Conversion Engine": "AI chat assistant handled inbound site traffic. Review qualification scores and session drop-off points.",
    }

    for vname, vleads, vcol, vlight in vert_meta:
        hdr = Table([[
            Paragraph(f"<b>{vname}</b>",
                      ps(f"vh{vname}", fontSize=9, fontName="Helvetica-Bold", textColor=WHITE)),
            Paragraph(f"{vleads} leads",
                      ps(f"vs{vname}", fontSize=8, textColor=WHITE, alignment=TA_RIGHT)),
        ]], colWidths=[CW * 0.75, CW * 0.25])
        hdr.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), vcol),
            ("LEFTPADDING",   (0,0), (-1,-1), 10), ("RIGHTPADDING",(0,0),(-1,-1), 10),
            ("TOPPADDING",    (0,0), (-1,-1), 7),  ("BOTTOMPADDING",(0,0),(-1,-1), 7),
        ]))
        body_text = vert_narratives.get(vname, default_texts.get(vname, ""))
        bdy = Table([[Paragraph(body_text, P_BODY)]], colWidths=[CW])
        bdy.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), vlight),
            ("LEFTPADDING",   (0,0), (-1,-1), 10), ("RIGHTPADDING",(0,0),(-1,-1), 10),
            ("TOPPADDING",    (0,0), (-1,-1), 8),  ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ]))
        s.append(KeepTogether([hdr, bdy]))
        s.append(Spacer(1, 10))

    # Outbound activity table
    activity = data.get("outbound_activity", [])
    if activity:
        s.append(Spacer(1, 4))
        s.append(Paragraph("Outbound Hunter — recent activity", P_H2))
        s.append(Spacer(1, 5))
        rows = [[
            Paragraph("<b>Prospect</b>",  ps("th", fontSize=8, fontName="Helvetica-Bold", textColor=GRAY_TEXT)),
            Paragraph("<b>Signal phrase</b>", ps("th2", fontSize=8, fontName="Helvetica-Bold", textColor=GRAY_TEXT)),
            Paragraph("<b>Status</b>",    ps("th3", fontSize=8, fontName="Helvetica-Bold", textColor=GRAY_TEXT)),
        ]]
        for row in activity[:8]:
            status_col = TEAL_MID if "booked" in row["status"].lower() else (
                         PURPLE   if "sent"   in row["status"].lower() else GRAY_TEXT)
            rows.append([
                Paragraph(f"<b>{row['name']}</b><br/>"
                          f"<font size='7' color='#888780'>{row.get('title','')} · {row.get('company','')}</font>",
                          ps("tc", fontSize=8, leading=13, textColor=BLACK)),
                Paragraph(f'"{row["trigger"]}"',
                          ps("tq", fontSize=8, textColor=GRAY_TEXT, leading=12)),
                Paragraph(row["status"],
                          ps("ts2", fontSize=8, textColor=status_col)),
            ])
        act_tbl = Table(rows, colWidths=[CW*0.35, CW*0.42, CW*0.23])
        act_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0),  GRAY_LIGHT),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ("RIGHTPADDING",  (0,0), (-1,-1), 8),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LINEBELOW",     (0,0), (-1,-2), 0.4, GRAY_MID),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ]))
        s.append(act_tbl)

    # Priority recommendation
    s.append(Spacer(1, 0.14 * inch))
    s.append(AccentBar(CW, 1, GRAY_MID))
    s.append(Spacer(1, 0.12 * inch))
    s.append(Paragraph("Priority recommendation", P_H2))
    s.append(Spacer(1, 4))
    rec_text = data.get("recommendation") or (
        "Review pipeline stage conversion rates. Focus on the Meeting Held → Closed Won "
        "transition if close rate is below 35%. AltusFlow will flag priority actions "
        "in the Week 1 check-in."
    )
    rec = Table([[Paragraph(rec_text, P_BODY)]], colWidths=[CW])
    rec.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), TEAL_LIGHT),
        ("LEFTPADDING",   (0,0), (-1,-1), 14), ("RIGHTPADDING", (0,0),(-1,-1), 14),
        ("TOPPADDING",    (0,0), (-1,-1), 12), ("BOTTOMPADDING",(0,0),(-1,-1), 12),
        ("LINEBEFORE",    (0,0), (0,-1),  3,   TEAL),
    ]))
    s.append(rec)
    s.append(Spacer(1, 0.28 * inch))
    s.append(AccentBar(CW, 0.5, GRAY_MID))
    s.append(Spacer(1, 6))
    s.append(Paragraph(
        f"Auto-generated from HubSpot CRM data for portal {data['client_id']}. "
        f"All metrics reflect activity within the {data['month']} reporting window.",
        ps("fn", fontSize=7, textColor=GRAY_TEXT, leading=11)
    ))

    doc.build(s, onFirstPage=_page, onLaterPages=_page)
    with open(output_path, "wb") as f:
        f.write(buf.getvalue())
    print(f"Report written → {output_path}")


if __name__ == "__main__":
    data_path = os.environ.get("DATA_OUTPUT_PATH", "reports/report_data.json")
    if not os.path.exists(data_path):
        print(f"ERROR: {data_path} not found. Run hubspot_pull.py first.")
        sys.exit(1)
    with open(data_path) as f:
        data = json.load(f)
    month_slug = data["month"].replace(" ", "_")
    out = f"reports/AltusFlow_{data['client_id']}_{month_slug}.pdf"
    os.makedirs("reports", exist_ok=True)
    build_report(data, out)
