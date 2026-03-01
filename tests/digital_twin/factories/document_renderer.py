"""
DocumentRenderer — generates synthetic tax document PDFs using reportlab.
Supports W-2 and 1099-NEC templates.
"""
import io
from pathlib import Path
from typing import Optional


def _try_reportlab():
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        return True
    except ImportError:
        return False


class DocumentRenderer:
    def render(
        self,
        profile,  # TaxpayerProfile
        quality: str = "perfect",  # perfect, realistic, degraded
        output_dir: str = "/tmp",
    ) -> Path:
        """
        Render a synthetic tax document PDF.
        quality: perfect (clean OCR), realistic (minor noise), degraded (low confidence)
        Returns path to generated PDF.
        """
        output_path = Path(output_dir) / f"{profile.profile_id}_{profile.filing_status.replace(' ', '_')}.pdf"

        if not _try_reportlab():
            # Fallback: write a text file
            text_content = self._generate_text(profile, quality)
            txt_path = output_path.with_suffix(".txt")
            txt_path.write_text(text_content)
            return txt_path

        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors

        doc = SimpleDocTemplate(str(output_path), pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph(f"Form W-2 / 1099 — Tax Year {profile.tax_year}", styles["Title"]))
        story.append(Spacer(1, 20))

        data = [
            ["Field", "Value"],
            ["Taxpayer Name:", profile.name],
            ["Filing Status:", profile.filing_status],
            ["Tax Year:", str(profile.tax_year)],
            ["Box 1 — Wages:", f"${profile.wages:,.2f}"],
            ["Box 2 — Fed Tax Withheld:", f"${profile.ground_truth_liability * 0.9:,.2f}"],
            ["Other Income:", f"${profile.other_income:,.2f}"],
        ]

        # Add noise for degraded quality
        if quality == "degraded":
            data[4][1] = f"${profile.wages:,.2f}".replace("5", "S")  # OCR noise

        t = Table(data, colWidths=[3 * 72, 3 * 72])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        doc.build(story)
        return output_path

    def _generate_text(self, profile, quality: str) -> str:
        return f"""TAX DOCUMENT — {profile.tax_year}
Taxpayer: {profile.name}
Filing Status: {profile.filing_status}
Wages: ${profile.wages:,.2f}
Other Income: ${profile.other_income:,.2f}
Itemized Deductions: ${profile.itemized_deductions:,.2f}
"""
