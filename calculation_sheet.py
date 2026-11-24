"""Create a printable calculation sheet from a validated steel beam design."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Table,
                                TableStyle, PageBreak, Flowable, KeepTogether)


class BeamDiagrams(Flowable):
    def __init__(self, design, result, section, uniforms):
        super().__init__()
        self.width, self.height = 500, 460
        self.design, self.result, self.section, self.uniforms = design, result, section, uniforms

    def draw(self):
        c = self.canv
        design, result, section = self.design, self.result, self.section
        span = design["span"]
        left, right = 55, 480
        xcoord = lambda x: left + (right-left)*x/span
        navy = colors.HexColor("#1f3a5f")
        c.setFillColor(navy); c.setFont("Helvetica-Bold", 10)
        c.drawString(0, 446, "Beam and total-load diagrams")
        ybeam = 410
        c.setStrokeColor(navy); c.setLineWidth(4); c.line(left, ybeam, right, ybeam)
        c.setLineWidth(1)
        if design["support"] == "Simply supported":
            for x in (left, right):
                p = c.beginPath(); p.moveTo(x, ybeam-2); p.lineTo(x-7, ybeam-14); p.lineTo(x+7, ybeam-14); p.close()
                c.drawPath(p, stroke=1, fill=0)
        else:
            c.setLineWidth(3); c.line(left, ybeam-16, left, ybeam+16); c.setLineWidth(1)
        c.setFillColor(colors.HexColor("#465363")); c.setFont("Helvetica", 8)
        c.drawString(left, 385, "0 ft")
        c.drawRightString(right, 385, f"{span:g} ft")
        c.drawCentredString((left+right)/2, 385, "Loads and positions listed on the input pages")
        positions = {span*i/240 for i in range(241)}
        positions.update(p["x"] for p in design["points"])
        positions.update(x for u in self.uniforms for x in (u["a"], u["b"]))
        positions = sorted(positions)
        jumps = {p["x"] for p in design["points"] if p["P"] and 0 < p["x"] < span}
        specs = [
            ("Shear V (kip)", colors.HexColor("#178a8a"), lambda x, side: result["V"](x, side), 330),
            ("Moment M (kip-ft)", colors.HexColor("#2f6fb3"), lambda x, side: result["M"](x), 220),
            ("Total deflection (in, down positive)", colors.HexColor("#7e57c2"),
             lambda x, side: result["d"](x, 29000, section["Ix"]), 110),
        ]
        for title, color, fn, top in specs:
            samples = []
            for x in positions:
                sides = (-1, 1) if x in jumps else ((-1,) if x == span else (1,))
                samples.extend((x, fn(x, side)) for side in sides)
            lo = min(0, *(v for _, v in samples)); hi = max(0, *(v for _, v in samples))
            if hi-lo < 1e-15: lo, hi = -1, 1
            bottom = top-65
            def ycoord(v):
                # Deflection is shown downward; moment and shear are positive upward.
                frac = (v-lo)/(hi-lo)
                return top-frac*(top-bottom) if title.startswith("Total") else bottom+frac*(top-bottom)
            c.setFillColor(color); c.setFont("Helvetica-Bold", 9); c.drawString(0, top+14, title)
            c.setStrokeColor(colors.HexColor("#b7c1cd")); c.setLineWidth(.6)
            c.line(left, ycoord(0), right, ycoord(0))
            c.setFillColor(colors.HexColor("#465363")); c.setFont("Helvetica", 7)
            c.drawRightString(left-5, ycoord(0)-2, "0")
            c.drawRightString(right, top+14, f"min {min(v for _, v in samples):.3f}   max {max(v for _, v in samples):.3f}")
            path = c.beginPath()
            for i, (x, v) in enumerate(samples):
                (path.moveTo if i == 0 else path.lineTo)(xcoord(x), ycoord(v))
            c.setStrokeColor(color); c.setLineWidth(1.3); c.drawPath(path)
        c.setFillColor(colors.HexColor("#465363")); c.setFont("Helvetica", 8)
        for i in range(5):
            x = span*i/4; c.drawCentredString(xcoord(x), 27, f"{x:g}")
        c.drawCentredString((left+right)/2, 13, "Distance along beam x (ft)")


def build_calculation_sheet(path, design, section, analyze):
    """Generate a PDF, using the same analysis and assumptions as the app."""
    L = design["span"]
    points = design["points"]
    uniforms = list(design["uniforms"])
    if design["self_weight"]:
        uniforms.append({"a": 0, "b": L, "w": section["weight_plf"]/1000, "type": "Dead"})
    total = analyze(design["support"], L, points, uniforms, 29000, section["Ix"])
    live = analyze(design["support"], L, [p for p in points if p["type"] == "Live"],
                   [u for u in design["uniforms"] if u["type"] == "Live"], 29000, section["Ix"])
    fy = {"A992": 50, "A36": 36}.get(design["grade"], design["fy"])
    fb = total["mmax"][0]*12/section["Sx"]; Fb = .66*fy
    fv = total["vmax"][0]/(section["d"]*section["tw"]); Fv = .4*fy
    limit = (L if design["support"] == "Simply supported" else 2*L)*12/design["limit"]
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=colors.HexColor("#1f3a5f"), alignment=0, spaceAfter=6)
    h = ParagraphStyle("ReportHeading", parent=styles["Heading2"], fontSize=10, leading=13, textColor=colors.HexColor("#1f3a5f"), spaceBefore=10, spaceAfter=5)
    body = ParagraphStyle("ReportBody", parent=styles["BodyText"], fontSize=9, leading=13, spaceAfter=5)
    small = ParagraphStyle("ReportSmall", parent=body, fontSize=8, leading=11)
    def table(rows, widths, header=False):
        t = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        commands = [("FONTNAME", (0,0), (-1,-1), "Helvetica"), ("FONTSIZE", (0,0), (-1,-1), 8),
                    ("VALIGN", (0,0), (-1,-1), "TOP"), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                    ("TOPPADDING", (0,0), (-1,-1), 4), ("LINEBELOW", (0,0), (-1,-1), .25, colors.HexColor("#dfe4ea"))]
        if header: commands += [("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#edf2f7"))]
        t.setStyle(TableStyle(commands)); return t
    story = [Paragraph("Beam calculation sheet", title),
             Paragraph("ASD | US customary units | Steel W-shape", small),
             Paragraph("Inputs", h)]
    rows = [
        ["Support", design["support"], "Span", f"{L:g} ft"],
        ["Section", design["shape"], "Grade / Fy", f"{design['grade']} / {fy:g} ksi"],
        ["Section properties", f"A = {section['A']:g} in2; Ix = {section['Ix']:g} in4", "Section modulus", f"Sx = {section['Sx']:g} in3"],
        ["Web / depth", f"tw = {section['tw']:g} in; d = {section['d']:g} in", "Elastic modulus", "E = 29,000 ksi"],
        ["Self-weight", f"{'On' if design['self_weight'] else 'Off'} ({section['weight_plf']:g} plf)", "Live limit", f"L / {design['limit']:g}" + (" (L = 2 x cantilever length)" if design['support'] != "Simply supported" else "")],
    ]
    story.append(table(rows, [90, 180, 95, 135]))
    load_rows = [["Load", "Type", "Position / extent (ft)", "Magnitude"]]
    load_rows += [["Point", p["type"], f"x = {p['x']:g}", f"{p['P']:g} kip"] for p in points]
    load_rows += [["Uniform", u["type"], f"{u['a']:g} to {u['b']:g}", f"{u['w']:g} kip/ft"] for u in design["uniforms"]]
    if design["self_weight"]: load_rows.append(["Self-weight", "Dead", f"0 to {L:g}", f"{section['weight_plf']/1000:g} kip/ft"])
    if len(load_rows) == 1: load_rows.append(["None", "-", "-", "-"])
    story += [Paragraph("Loads (downward)", h), table(load_rows, [90, 75, 175, 160], True)]
    reaction = (f"Left reaction = {total['RA']:.3f} kip; right reaction = {total['RB']:.3f} kip"
                if design["support"] == "Simply supported" else
                f"Fixed vertical reaction = {total['RA']:.3f} kip; internal fixed-end moment = {total['M0']:.3f} kip-ft")
    results = [Paragraph("Results and checks", h), Paragraph(reaction, body), Paragraph(
        f"Max |V| = {total['vmax'][0]:.3f} kip at x = {total['vmax'][1]:.3f} ft; "
        f"max |M| = {total['mmax'][0]:.3f} kip-ft at x = {total['mmax'][1]:.3f} ft.<br/>"
        f"Max total deflection = {total['dmax'][0]:.4f} in at x = {total['dmax'][1]:.3f} ft; "
        f"max live deflection = {live['dmax'][0]:.4f} in at x = {live['dmax'][1]:.3f} ft.", body)]
    checks = [("Bending", fb, Fb, "ksi"), ("Shear", fv, Fv, "ksi"), ("Live deflection", live["dmax"][0], limit, "in")]
    check_rows = [["Check", "Demand", "Allowable", "Ratio", "Result"]]
    check_rows += [[name, f"{value:.4f} {unit}", f"{allow:.4f} {unit}", f"{value/allow:.3f}", "PASS" if value/allow <= 1+1e-9 else "FAIL"] for name, value, allow, unit in checks]
    results += [table(check_rows, [125, 110, 110, 75, 80], True),
              Paragraph("Bending: fb = |M|max x 12 / Sx; Fb = 0.66 Fy. Shear: fv = |V|max / (d x tw); Fv = 0.4 Fy. Deflection uses live load only.", small),
              Paragraph("ASD; bending and shear use total load. Steel section assumed compact and fully laterally braced; buckling is not checked. Positive shear is upward on the left face, positive moment is sagging, and deflection is positive downward. Educational tool; not for design of record.", small)]
    story += [KeepTogether(results), PageBreak(), BeamDiagrams(design, total, section, uniforms)]
    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.HexColor("#64707d"))
        canvas.drawString(42, 25, "Beam Designer | Educational tool - not for design of record")
        canvas.drawRightString(letter[0]-42, 25, f"Page {doc.page}")
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=56, rightMargin=56, topMargin=45, bottomMargin=45,
                            title="Beam calculation sheet", author="Beam Designer")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
