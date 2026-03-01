"""
TaxSummaryReport — IRS 1040-style tax form model and renderers.

Produces a detailed tax summary with income, deductions, credits,
bracket breakdown, FICA, dual-LLM scoring, and final liability.
"""
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


class BracketLine(BaseModel):
    rate: str
    bracket_min: float
    bracket_max: Optional[float] = None
    taxable_amount: float
    tax: float


class CreditLine(BaseModel):
    name: str
    amount: float
    credit_type: str  # "refundable" or "nonrefundable"


class TaxSummaryReport(BaseModel):
    # Header
    taxpayer_name: str
    filing_status: str
    tax_year: int = 2024
    profile_id: str = ""

    # Income
    wages: float = 0.0
    interest_income: float = 0.0
    dividend_income: float = 0.0
    other_income: float = 0.0
    total_income: float = 0.0

    # Adjustments
    se_tax_deduction: float = 0.0
    total_adjustments: float = 0.0
    agi: float = 0.0

    # Deductions
    standard_deduction: float = 0.0
    itemized_deductions: float = 0.0
    applied_deduction: float = 0.0
    deduction_method: str = "standard"
    taxable_income: float = 0.0

    # Tax Computation
    bracket_breakdown: List[BracketLine] = Field(default_factory=list)
    federal_tax: float = 0.0
    ss_tax: float = 0.0
    medicare_tax: float = 0.0
    additional_medicare_tax: float = 0.0
    total_fica: float = 0.0
    total_tax: float = 0.0

    # Credits
    credits_applied: List[CreditLine] = Field(default_factory=list)
    total_nonrefundable_credits: float = 0.0
    total_refundable_credits: float = 0.0
    total_credits: float = 0.0

    # Final
    tax_after_credits: float = 0.0
    total_liability: float = 0.0
    total_payments: float = 0.0
    refund_or_owed: float = 0.0

    # Dual-LLM Scoring
    claude_estimate: float = 0.0
    openai_estimate: float = 0.0
    consensus_liability: Optional[float] = None
    liability_delta_pct: float = 0.0
    flag_status: str = "N/A"
    scoring_rationale: str = ""

    # Effective rates
    effective_rate_pct: float = 0.0

    def render_text(self) -> str:
        """Render an IRS 1040-inspired plain-text tax form."""
        w = 72  # form width
        sep = "=" * w
        thin = "-" * w

        def dollar(val: float) -> str:
            if val < 0:
                return f"(${abs(val):>12,.2f})"
            return f" ${val:>12,.2f}"

        def line(num: int, label: str, val: float) -> str:
            return f"  {num:>3}.  {label:<42s} {dollar(val)}"

        lines = []

        # Header
        lines.append(sep)
        lines.append(f"{'IRS FORM 1040 — TAX SUMMARY':^{w}}")
        lines.append(f"{'Tax.AI Dual-LLM Analysis Report':^{w}}")
        lines.append(sep)
        lines.append(f"  Taxpayer:       {self.taxpayer_name}")
        lines.append(f"  Filing Status:  {self.filing_status}")
        lines.append(f"  Tax Year:       {self.tax_year}")
        lines.append(f"  Profile ID:     {self.profile_id}")
        lines.append(sep)

        # INCOME
        lines.append(f"{'INCOME':^{w}}")
        lines.append(thin)
        ln = 1
        lines.append(line(ln, "Wages, salaries, tips (W-2)", self.wages)); ln += 1
        lines.append(line(ln, "Taxable interest", self.interest_income)); ln += 1
        lines.append(line(ln, "Ordinary dividends", self.dividend_income)); ln += 1
        lines.append(line(ln, "Other income (Sched C, 1099, etc.)", self.other_income)); ln += 1
        lines.append(thin)
        lines.append(line(ln, "TOTAL INCOME", self.total_income)); ln += 1
        lines.append("")

        # ADJUSTMENTS
        lines.append(f"{'ADJUSTMENTS TO INCOME':^{w}}")
        lines.append(thin)
        lines.append(line(ln, "Self-employment tax deduction", self.se_tax_deduction)); ln += 1
        lines.append(line(ln, "Total adjustments", self.total_adjustments)); ln += 1
        lines.append(thin)
        lines.append(line(ln, "ADJUSTED GROSS INCOME (AGI)", self.agi)); ln += 1
        lines.append("")

        # DEDUCTIONS
        lines.append(f"{'DEDUCTIONS':^{w}}")
        lines.append(thin)
        lines.append(line(ln, "Standard deduction", self.standard_deduction)); ln += 1
        lines.append(line(ln, "Itemized deductions", self.itemized_deductions)); ln += 1
        lines.append(line(ln, f"Deduction applied ({self.deduction_method})", self.applied_deduction)); ln += 1
        lines.append(thin)
        lines.append(line(ln, "TAXABLE INCOME", self.taxable_income)); ln += 1
        lines.append("")

        # TAX COMPUTATION
        lines.append(f"{'TAX COMPUTATION':^{w}}")
        lines.append(thin)
        lines.append("  Bracket Breakdown:")
        lines.append(f"  {'Rate':<8s} {'Bracket':<24s} {'Taxable':<16s} {'Tax':>14s}")
        lines.append(f"  {'-'*8} {'-'*24} {'-'*16} {'-'*14}")
        for b in self.bracket_breakdown:
            hi = f"${b.bracket_max:,.0f}" if b.bracket_max else "+"
            rng = f"${b.bracket_min:,.0f} — {hi}"
            lines.append(
                f"  {b.rate:<8s} {rng:<24s} ${b.taxable_amount:>12,.2f}  ${b.tax:>11,.2f}"
            )
        lines.append(thin)
        lines.append(line(ln, "Federal income tax", self.federal_tax)); ln += 1
        lines.append(f"  {'':>5}  Effective rate: {self.effective_rate_pct:.2f}%")
        lines.append("")

        # FICA
        lines.append(f"{'FICA / SELF-EMPLOYMENT TAX':^{w}}")
        lines.append(thin)
        lines.append(line(ln, "Social Security tax (6.2%)", self.ss_tax)); ln += 1
        lines.append(line(ln, "Medicare tax (1.45%)", self.medicare_tax)); ln += 1
        lines.append(line(ln, "Additional Medicare tax (0.9%)", self.additional_medicare_tax)); ln += 1
        lines.append(thin)
        lines.append(line(ln, "TOTAL FICA", self.total_fica)); ln += 1
        lines.append("")

        # CREDITS
        lines.append(f"{'CREDITS':^{w}}")
        lines.append(thin)
        if self.credits_applied:
            for c in self.credits_applied:
                lines.append(line(ln, f"{c.name} ({c.credit_type})", c.amount)); ln += 1
        else:
            lines.append(line(ln, "(no credits applied)", 0.0)); ln += 1
        lines.append(thin)
        lines.append(line(ln, "TOTAL CREDITS", self.total_credits)); ln += 1
        lines.append("")

        # SUMMARY
        lines.append(sep)
        lines.append(f"{'FINAL TAX SUMMARY':^{w}}")
        lines.append(sep)
        lines.append(line(ln, "Federal income tax", self.federal_tax)); ln += 1
        lines.append(line(ln, "Less: credits", -self.total_credits)); ln += 1
        lines.append(line(ln, "Tax after credits", self.tax_after_credits)); ln += 1
        lines.append(line(ln, "FICA taxes", self.total_fica)); ln += 1
        lines.append(thin)
        lines.append(line(ln, "TOTAL TAX LIABILITY", self.total_liability)); ln += 1
        lines.append(line(ln, "Total payments / withholding", self.total_payments)); ln += 1
        lines.append(thin)
        owed_label = "REFUND" if self.refund_or_owed < 0 else "AMOUNT OWED"
        lines.append(line(ln, owed_label, abs(self.refund_or_owed))); ln += 1
        lines.append("")

        # DUAL-LLM SECTION
        lines.append(sep)
        lines.append(f"{'DUAL-LLM SCORING ANALYSIS':^{w}}")
        lines.append(sep)
        lines.append(f"  Claude estimate:        {dollar(self.claude_estimate)}")
        lines.append(f"  OpenAI estimate:        {dollar(self.openai_estimate)}")
        if self.consensus_liability is not None:
            lines.append(f"  Consensus liability:    {dollar(self.consensus_liability)}")
        lines.append(f"  Liability delta:         {self.liability_delta_pct:.1f}%")
        lines.append(f"  Flag status:             {self.flag_status}")
        lines.append(f"  Rationale:  {self.scoring_rationale}")
        lines.append(sep)
        lines.append("")

        return "\n".join(lines)

    def render_pdf(self, path: Path) -> None:
        """Render a PDF with IRS 1040-style sections using ReportLab."""
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, PageBreak,
        )

        doc = SimpleDocTemplate(
            str(path),
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=inch,
            bottomMargin=inch,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleStyle", parent=styles["Title"],
            fontSize=20, textColor=colors.HexColor("#1a1a2e"),
        )
        heading_style = ParagraphStyle(
            "HeadingStyle", parent=styles["Heading2"],
            fontSize=13, textColor=colors.HexColor("#16213e"),
        )
        body_style = styles["BodyText"]

        story: list = []

        def _heading(title: str):
            story.append(Spacer(1, 0.15 * inch))
            story.append(Paragraph(title, heading_style))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#4a90d9")))
            story.append(Spacer(1, 0.1 * inch))

        def _kv_table(rows: list[list[str]], col_widths=None):
            cw = col_widths or [4.0 * inch, 2.5 * inch]
            t = Table(rows, colWidths=cw)
            t.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ]))
            story.append(t)

        def _dollar(val: float) -> str:
            if val < 0:
                return f"(${abs(val):,.2f})"
            return f"${val:,.2f}"

        # ========== COVER ==========
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph("IRS Form 1040 — Tax Summary", title_style))
        story.append(Paragraph("Tax.AI Dual-LLM Analysis Report", body_style))
        story.append(Spacer(1, 0.15 * inch))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#4a90d9")))
        story.append(Spacer(1, 0.25 * inch))

        info_rows = [
            ["Taxpayer", self.taxpayer_name],
            ["Filing Status", self.filing_status],
            ["Tax Year", str(self.tax_year)],
            ["Profile ID", self.profile_id],
        ]
        t = Table(info_rows, colWidths=[2 * inch, 4.5 * inch])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3 * inch))

        # ========== INCOME ==========
        _heading("Income")
        _kv_table([
            ["Item", "Amount"],
            ["Wages, salaries, tips (W-2)", _dollar(self.wages)],
            ["Taxable interest", _dollar(self.interest_income)],
            ["Ordinary dividends", _dollar(self.dividend_income)],
            ["Other income (Sched C, 1099, etc.)", _dollar(self.other_income)],
            ["TOTAL INCOME", _dollar(self.total_income)],
        ])

        # ========== ADJUSTMENTS ==========
        _heading("Adjustments to Income")
        _kv_table([
            ["Adjustment", "Amount"],
            ["Self-employment tax deduction", _dollar(self.se_tax_deduction)],
            ["Total adjustments", _dollar(self.total_adjustments)],
            ["Adjusted Gross Income (AGI)", _dollar(self.agi)],
        ])

        # ========== DEDUCTIONS ==========
        _heading("Deductions")
        _kv_table([
            ["Deduction", "Amount"],
            ["Standard deduction", _dollar(self.standard_deduction)],
            ["Itemized deductions", _dollar(self.itemized_deductions)],
            [f"Applied ({self.deduction_method})", _dollar(self.applied_deduction)],
            ["TAXABLE INCOME", _dollar(self.taxable_income)],
        ])

        # ========== TAX COMPUTATION ==========
        _heading("Tax Computation — Bracket Breakdown")
        bracket_rows = [["Rate", "Bracket", "Taxable Amount", "Tax"]]
        for b in self.bracket_breakdown:
            hi = f"${b.bracket_max:,.0f}" if b.bracket_max else "—"
            bracket_rows.append([
                b.rate,
                f"${b.bracket_min:,.0f} — {hi}",
                _dollar(b.taxable_amount),
                _dollar(b.tax),
            ])
        bracket_rows.append(["", "", "Federal Tax", _dollar(self.federal_tax)])
        _kv_table(bracket_rows, [1.2 * inch, 2.0 * inch, 1.8 * inch, 1.5 * inch])
        story.append(Paragraph(
            f"Effective rate: {self.effective_rate_pct:.2f}%", body_style,
        ))

        # ========== FICA ==========
        _heading("FICA / Self-Employment Tax")
        _kv_table([
            ["Component", "Amount"],
            ["Social Security tax (6.2%)", _dollar(self.ss_tax)],
            ["Medicare tax (1.45%)", _dollar(self.medicare_tax)],
            ["Additional Medicare (0.9%)", _dollar(self.additional_medicare_tax)],
            ["TOTAL FICA", _dollar(self.total_fica)],
        ])

        # ========== CREDITS ==========
        _heading("Credits")
        credit_rows = [["Credit", "Type", "Amount"]]
        if self.credits_applied:
            for c in self.credits_applied:
                credit_rows.append([c.name, c.credit_type, _dollar(c.amount)])
        else:
            credit_rows.append(["(none)", "", "$0.00"])
        credit_rows.append(["TOTAL CREDITS", "", _dollar(self.total_credits)])
        _kv_table(credit_rows, [3 * inch, 1.5 * inch, 2 * inch])

        story.append(PageBreak())

        # ========== FINAL SUMMARY ==========
        _heading("Final Tax Summary")
        _kv_table([
            ["Item", "Amount"],
            ["Federal income tax", _dollar(self.federal_tax)],
            ["Less: credits", f"({_dollar(self.total_credits)})"],
            ["Tax after credits", _dollar(self.tax_after_credits)],
            ["FICA taxes", _dollar(self.total_fica)],
            ["TOTAL TAX LIABILITY", _dollar(self.total_liability)],
            ["Total payments / withholding", _dollar(self.total_payments)],
            ["REFUND / AMOUNT OWED", _dollar(self.refund_or_owed)],
        ])

        # ========== DUAL-LLM ==========
        _heading("Dual-LLM Scoring Analysis")
        _kv_table([
            ["Metric", "Value"],
            ["Claude estimate", _dollar(self.claude_estimate)],
            ["OpenAI estimate", _dollar(self.openai_estimate)],
            ["Consensus liability", _dollar(self.consensus_liability) if self.consensus_liability is not None else "N/A"],
            ["Liability delta", f"{self.liability_delta_pct:.1f}%"],
            ["Flag status", self.flag_status],
        ])
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(f"<b>Rationale:</b> {self.scoring_rationale}", body_style))

        doc.build(story)
