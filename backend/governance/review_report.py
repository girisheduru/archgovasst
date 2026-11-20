"""Format a final governance review as a downloadable PDF."""

from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

INK = colors.HexColor("#15283D")
MUTED = colors.HexColor("#45596D")


def _page_footer(canvas, document):
    canvas.saveState()
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(document.leftMargin, 30, "Architecture Governance Assistant")
    canvas.drawRightString(A4[0] - document.rightMargin, 30, f"Page {document.page}")
    canvas.restoreState()


def render_review_report(review: dict) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, title="Final architecture governance report",
        leftMargin=48, rightMargin=48, topMargin=44, bottomMargin=54,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle", fontName="Helvetica-Bold", fontSize=22, leading=26,
        textColor=INK, spaceAfter=14, keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="ReportBody", fontSize=10, leading=14, textColor=INK, spaceAfter=5,
    ))
    for name in ("Heading2", "Heading3"):
        styles[name].textColor = INK
        styles[name].keepWithNext = True

    story = [Paragraph("Final architecture governance report", styles["ReportTitle"])]

    def add(text, style="ReportBody", label=""):
        safe_text = "<br/>".join(escape(line) for line in str(text).splitlines())
        prefix = f"<b>{label}</b> " if label else ""
        story.append(Paragraph(prefix + safe_text, styles[style]))

    add(review["stage"].capitalize(), label="Outcome")
    add(review["filename"], label="Document")
    add(review["document_type"], label="Document type")
    add(review["review_id"], label="Review ID")
    add(review["as_of"], label="Standards as of")
    add(f'{review["declared_tier"]} declared / {review["risk_tier"]} assessed', label="Risk tier")

    findings = review["findings"]
    checkpoints = {"confirm_evidence": "Evidence confirmation", "approve_report": "Report approval"}
    evidenced = sum(bool(row["evidence"]) for row in findings)
    add("Standards comparison", "Heading2")
    add(f"{len(findings)} rules reviewed, {evidenced} with evidence, "
        f"{len(findings) - evidenced} not evidenced.")
    add("Cited text supports a requirement. Confirming that a control is in "
        "place requires implementation evidence. Missing evidence can raise "
        "the assessed risk tier.")
    for row in findings:
        add(f'{row["rule_id"]} / {row["standard"]}', "Heading3")
        add(row["effective_date"], label="Effective date")
        add(row["rule_quote"], label="Standard requirement")
        add(row["evidence_required"], label="Evidence required")
        if evidence := row["evidence"]:
            citation = f'{evidence["source"]}: “{evidence["quote"]}”'
            if filename := evidence.get("document"):
                add(f"{filename} / {citation}", label="Supporting evidence")
            else:
                add(citation, label="Design evidence")
        else:
            add(f'Not evidenced. {row["gap_risk"].capitalize()} risk evidence gap.',
                label="Design evidence")
        for entry in review["audit"]:
            if comment := entry.get("comments", {}).get(row["rule_id"]):
                checkpoint = checkpoints[entry["checkpoint"]]
                add(f'{entry["reviewer"]} / {checkpoint}\n{comment}', label="Reviewer comment")
        story.append(Spacer(1, 6))

    add("Decision history", "Heading2")
    for entry in review["audit"]:
        add(checkpoints[entry["checkpoint"]], "Heading3")
        decision = "Approved" if entry["decision"] == "approve" else "Rejected"
        add(f'{decision} by {entry["reviewer"]} on {entry["at"]}')
        if entry["note"]:
            add(entry["note"], label="Note")

    document.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return output.getvalue()
