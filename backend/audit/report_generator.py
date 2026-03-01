"""
ReportGenerator — generates PDF and JSON audit reports from session JSONL.
PDF uses reportlab (canvas-based). Cover page includes SHA-256 for integrity.
"""
import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from opentelemetry import trace

from backend.audit.audit_logger import AuditEvent, get_audit_logger

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("backend/audit/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA_VERSION = "1.0"


class ReportGenerator:
    async def generate(self, session_id: str) -> tuple[Path, Path]:
        """
        Generate PDF and JSON audit reports for a session.
        Returns (pdf_path, json_path).
        """
        audit = get_audit_logger()
        events = await audit.read_session_events(session_id)

        # Compute JSONL SHA-256 for integrity
        jsonl_path = audit.get_session_path(session_id)
        sha256 = await self._compute_sha256(jsonl_path)

        # Get current trace_id if available
        current_span = trace.get_current_span()
        trace_id = ""
        if current_span and current_span.get_span_context().trace_id:
            trace_id = format(current_span.get_span_context().trace_id, "032x")

        report_data = self._build_report_data(session_id, events, sha256, trace_id)

        # Generate both in parallel
        pdf_path = REPORTS_DIR / f"audit_report_{session_id}.pdf"
        json_path = REPORTS_DIR / f"audit_report_{session_id}.json"

        await asyncio.gather(
            asyncio.to_thread(self._generate_pdf, pdf_path, report_data, sha256),
            asyncio.to_thread(self._generate_json, json_path, report_data),
        )

        return pdf_path, json_path

    def _build_report_data(
        self,
        session_id: str,
        events: list[AuditEvent],
        sha256: str,
        trace_id: str = "",
    ) -> dict:
        """Reconstruct audit data from JSONL events."""
        event_types: dict[str, list] = {}
        for event in events:
            event_types.setdefault(event.event_type, []).append(event.model_dump())

        # Extract key metrics
        analysis_events = event_types.get("analysis.completed", [])
        flag_status = analysis_events[-1].get("flag_status") if analysis_events else "N/A"
        confidence = analysis_events[-1].get("confidence_score") if analysis_events else None

        ocr_corrections = len(event_types.get("ocr.field_corrected", []))
        documents_uploaded = len(event_types.get("document.uploaded", []))

        pii_masked_count = sum(1 for e in events if e.pii_masked)

        return {
            "schema_version": SCHEMA_VERSION,
            "session_id": session_id,
            "trace_id": trace_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "jsonl_sha256": sha256,
            "total_events": len(events),
            "event_type_counts": {k: len(v) for k, v in event_types.items()},
            "documents_uploaded": documents_uploaded,
            "ocr_corrections": ocr_corrections,
            "pii_masked_count": pii_masked_count,
            "final_flag_status": flag_status,
            "final_confidence_score": confidence,
            "events": [e.model_dump() for e in events],
            "event_type_breakdown": event_types,
        }

    @staticmethod
    async def _compute_sha256(path: Path) -> str:
        if not path.exists():
            return "N/A (no audit trail)"
        content = await asyncio.to_thread(path.read_bytes)
        return hashlib.sha256(content).hexdigest()

    def _generate_pdf(self, path: Path, data: dict, sha256: str):
        """Generate 16-section PDF with TOC using reportlab."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                HRFlowable, PageBreak,
            )
        except ImportError:
            logger.error("reportlab not installed — PDF generation skipped")
            path.write_text("PDF generation requires reportlab: pip install reportlab")
            return

        doc = SimpleDocTemplate(
            str(path),
            pagesize=letter,
            rightMargin=inch * 0.75,
            leftMargin=inch * 0.75,
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
        mono_style = ParagraphStyle(
            "MonoStyle", parent=styles["Code"], fontSize=8, fontName="Courier",
        )
        toc_style = ParagraphStyle(
            "TOCStyle", parent=styles["BodyText"],
            fontSize=11, leading=18, textColor=colors.HexColor("#4a90d9"),
        )

        etb = data.get("event_type_breakdown", {})
        story = []

        def _heading(num, title):
            story.append(Paragraph(f"{num}. {title}", heading_style))
            story.append(Spacer(1, 0.15 * inch))

        def _table(rows, col_widths=None):
            if not rows:
                story.append(Paragraph("No data available.", body_style))
                return
            cw = col_widths or [3 * inch, 3.5 * inch]
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
            ]))
            story.append(t)

        # ===================== 1. COVER PAGE =====================
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph("Tax AI — Audit Report", title_style))
        story.append(Spacer(1, 0.25 * inch))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#4a90d9")))
        story.append(Spacer(1, 0.25 * inch))

        cover_info = [
            ["Session ID:", data["session_id"]],
            ["Trace ID:", data.get("trace_id", "N/A") or "N/A"],
            ["Generated:", data["generated_at"]],
            ["Schema Version:", data["schema_version"]],
            ["SHA-256:", sha256[:32] + "..."],
            ["Total Events:", str(data["total_events"])],
            ["Final Flag Status:", data.get("final_flag_status", "N/A")],
        ]
        t = Table(cover_info, colWidths=[2 * inch, 4.5 * inch])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(PageBreak())

        # ===================== 2. TABLE OF CONTENTS =====================
        _heading(2, "Table of Contents")
        toc_items = [
            "1. Cover Page",
            "2. Table of Contents",
            "3. Executive Summary",
            "4. Document Inventory",
            "5. OCR Results",
            "6. User Corrections",
            "7. Income Summary",
            "8. Deductions Analysis",
            "9. Credits Applied",
            "10. Claude Analysis",
            "11. OpenAI RAG Analysis",
            "12. Dual-LLM Comparison",
            "13. Calculator Verification",
            "14. Agent Activity Log",
            "15. Telemetry Summary",
            "16. Appendix: Full Event Log",
        ]
        for item in toc_items:
            story.append(Paragraph(item, toc_style))
        story.append(PageBreak())

        # ===================== 3. EXECUTIVE SUMMARY =====================
        _heading(3, "Executive Summary")
        flag = data.get("final_flag_status", "N/A")
        conf = data.get("final_confidence_score")
        story.append(Paragraph(f"<b>Flag Status:</b> {flag}", body_style))
        story.append(Paragraph(
            f"<b>Confidence Score:</b> {conf:.1f}%" if conf else "<b>Confidence Score:</b> N/A",
            body_style,
        ))
        story.append(Paragraph(f"<b>Documents Uploaded:</b> {data.get('documents_uploaded', 0)}", body_style))
        story.append(Paragraph(f"<b>OCR Corrections:</b> {data.get('ocr_corrections', 0)}", body_style))
        story.append(Paragraph(f"<b>PII Masked:</b> {data.get('pii_masked_count', 0)} occurrences", body_style))

        # Extract liability from analysis events
        analysis_evts = etb.get("analysis.completed", [])
        if analysis_evts:
            story.append(Paragraph(
                f"<b>Analysis Summary:</b> {analysis_evts[-1].get('output_summary', 'N/A')}",
                body_style,
            ))
        story.append(PageBreak())

        # ===================== 4. DOCUMENT INVENTORY =====================
        _heading(4, "Document Inventory")
        doc_events = etb.get("document.uploaded", [])
        if doc_events:
            rows = [["Filename", "Type", "SHA-256 (prefix)", "Timestamp"]]
            for ev in doc_events:
                meta = ev.get("metadata", {})
                rows.append([
                    ev.get("input_summary", "")[:40],
                    meta.get("doc_type", "unknown"),
                    meta.get("sha256", "")[:16] + "...",
                    datetime.fromtimestamp(ev.get("timestamp", 0)).strftime("%H:%M:%S"),
                ])
            _table(rows, [2.5 * inch, 1.5 * inch, 1.5 * inch, 1 * inch])
        else:
            story.append(Paragraph("No documents uploaded.", body_style))
        story.append(PageBreak())

        # ===================== 5. OCR RESULTS =====================
        _heading(5, "OCR Results")
        ocr_events = etb.get("ocr.completed", [])
        if ocr_events:
            for ev in ocr_events:
                story.append(Paragraph(
                    f"File: {ev.get('input_summary', 'unknown')} — "
                    f"Fields extracted: {ev.get('metadata', {}).get('field_count', '?')}",
                    body_style,
                ))
        else:
            story.append(Paragraph("No OCR processing performed.", body_style))
        story.append(PageBreak())

        # ===================== 6. USER CORRECTIONS =====================
        _heading(6, "User Corrections")
        corr_events = etb.get("ocr.field_corrected", [])
        if corr_events:
            rows = [["Field", "Original", "Corrected"]]
            for ev in corr_events:
                rows.append([
                    ev.get("input_summary", "")[:30],
                    ev.get("input_summary", "").split("original=")[-1][:30] if "original=" in ev.get("input_summary", "") else "",
                    ev.get("output_summary", "")[:30],
                ])
            _table(rows, [2 * inch, 2.25 * inch, 2.25 * inch])
        else:
            story.append(Paragraph("No user corrections made.", body_style))
        story.append(PageBreak())

        # ===================== 7. INCOME SUMMARY =====================
        _heading(7, "Income Summary")
        story.append(Paragraph(
            "Income data is extracted from OCR results and user input. "
            "Categories include wages, interest, dividends, and other income.",
            body_style,
        ))
        story.append(PageBreak())

        # ===================== 8. DEDUCTIONS ANALYSIS =====================
        _heading(8, "Deductions Analysis")
        story.append(Paragraph(
            "Standard vs itemized deduction comparison as computed by the calculator tool.",
            body_style,
        ))
        story.append(PageBreak())

        # ===================== 9. CREDITS APPLIED =====================
        _heading(9, "Credits Applied")
        story.append(Paragraph(
            "Applicable tax credits identified by the dual-LLM analysis.",
            body_style,
        ))
        story.append(PageBreak())

        # ===================== 10. CLAUDE ANALYSIS =====================
        _heading(10, "Claude Analysis")
        # Extract from analysis.completed events
        if analysis_evts:
            last = analysis_evts[-1]
            story.append(Paragraph(f"<b>Flag:</b> {last.get('flag_status', 'N/A')}", body_style))
            story.append(Paragraph(
                f"<b>Confidence:</b> {last.get('confidence_score', 'N/A')}", body_style,
            ))
            story.append(Paragraph(
                f"<b>Output:</b> {last.get('output_summary', 'N/A')}", body_style,
            ))
        else:
            story.append(Paragraph("No Claude analysis data.", body_style))
        story.append(PageBreak())

        # ===================== 11. OPENAI RAG ANALYSIS =====================
        _heading(11, "OpenAI RAG Analysis")
        tool_events = etb.get("tool.completed", [])
        rag_events = [e for e in tool_events if e.get("tool_name") == "legal_rag_agent_tool"]
        if rag_events:
            for ev in rag_events:
                story.append(Paragraph(
                    f"Output: {ev.get('output_summary', 'N/A')[:200]}", body_style,
                ))
        else:
            story.append(Paragraph("No OpenAI RAG data.", body_style))
        story.append(PageBreak())

        # ===================== 12. DUAL-LLM COMPARISON =====================
        _heading(12, "Dual-LLM Comparison")
        scoring_events = etb.get("scoring.comparison", [])
        if scoring_events:
            last_sc = scoring_events[-1]
            meta = last_sc.get("metadata", {})
            rows = [["Metric", "Claude", "OpenAI"]]
            rows.append([
                "Confidence",
                f"{meta.get('claude_confidence', 'N/A')}%",
                f"{meta.get('openai_confidence', 'N/A')}%",
            ])
            rows.append([
                "Liability",
                f"${meta.get('claude_liability', 0):,.0f}" if meta.get("claude_liability") else "N/A",
                f"${meta.get('openai_liability', 0):,.0f}" if meta.get("openai_liability") else "N/A",
            ])
            rows.append(["Delta", f"{meta.get('liability_delta', 0):.1f}%", ""])
            _table(rows, [2 * inch, 2.25 * inch, 2.25 * inch])
        else:
            story.append(Paragraph("No scoring comparison data.", body_style))

        flag_events = etb.get("scoring.flag_assigned", [])
        if flag_events:
            story.append(Spacer(1, 0.1 * inch))
            story.append(Paragraph(
                f"<b>Flag Rationale:</b> {flag_events[-1].get('output_summary', 'N/A')}",
                body_style,
            ))
        story.append(PageBreak())

        # ===================== 13. CALCULATOR VERIFICATION =====================
        _heading(13, "Calculator Verification")
        calc_events = [e for e in tool_events if e.get("tool_name") == "calculator_tool"]
        if calc_events:
            for ev in calc_events:
                story.append(Paragraph(
                    f"Result: {ev.get('output_summary', 'N/A')[:200]}", body_style,
                ))
        else:
            story.append(Paragraph("No calculator verification data.", body_style))
        story.append(PageBreak())

        # ===================== 14. AGENT ACTIVITY LOG =====================
        _heading(14, "Agent Activity Log")
        cycle_started = etb.get("agent.cycle_started", [])
        cycle_completed = etb.get("agent.cycle_completed", [])
        story.append(Paragraph(f"<b>Total cycles started:</b> {len(cycle_started)}", body_style))
        story.append(Paragraph(f"<b>Total cycles completed:</b> {len(cycle_completed)}", body_style))
        story.append(Spacer(1, 0.1 * inch))

        invoked = etb.get("tool.invoked", [])
        completed = etb.get("tool.completed", [])
        failed = etb.get("tool.failed", [])
        story.append(Paragraph(f"<b>Tools invoked:</b> {len(invoked)}", body_style))
        story.append(Paragraph(f"<b>Tools completed:</b> {len(completed)}", body_style))
        story.append(Paragraph(f"<b>Tools failed:</b> {len(failed)}", body_style))

        if invoked:
            rows = [["Tool", "Input (truncated)", "Time"]]
            for ev in invoked[:20]:
                rows.append([
                    ev.get("tool_name", "?"),
                    ev.get("input_summary", "")[:40],
                    datetime.fromtimestamp(ev.get("timestamp", 0)).strftime("%H:%M:%S"),
                ])
            _table(rows, [2 * inch, 3 * inch, 1.5 * inch])
        story.append(PageBreak())

        # ===================== 15. TELEMETRY SUMMARY =====================
        _heading(15, "Telemetry Summary")
        story.append(Paragraph(f"<b>Trace ID:</b> {data.get('trace_id', 'N/A') or 'N/A'}", body_style))
        story.append(Paragraph(
            f"<b>Event type count:</b> {len(data.get('event_type_counts', {}))} distinct types",
            body_style,
        ))
        story.append(Paragraph(f"<b>Total events:</b> {data.get('total_events', 0)}", body_style))

        # Estimate total session time from first to last event
        events = data.get("events", [])
        if len(events) >= 2:
            first_ts = events[0].get("timestamp", 0)
            last_ts = events[-1].get("timestamp", 0)
            duration = last_ts - first_ts
            story.append(Paragraph(f"<b>Session duration:</b> {duration:.1f}s", body_style))

        # Event type breakdown table
        story.append(Spacer(1, 0.15 * inch))
        summary_data = [["Event Type", "Count"]] + [
            [k, str(v)] for k, v in sorted(data["event_type_counts"].items())
        ]
        _table(summary_data, [4 * inch, 2.5 * inch])
        story.append(PageBreak())

        # ===================== 16. APPENDIX: FULL EVENT LOG =====================
        _heading(16, "Appendix: Full Event Log")
        for event in data["events"]:
            ts = datetime.fromtimestamp(event.get("timestamp", 0)).strftime("%H:%M:%S")
            event_type = event.get("event_type", "unknown")
            summary = event.get("output_summary", event.get("input_summary", ""))
            story.append(Paragraph(
                f"<b>{ts}</b> [{event_type}] {(summary or '')[:120]}",
                body_style,
            ))
        story.append(Spacer(1, 0.25 * inch))

        doc.build(story)
        logger.info(f"PDF report generated: {path}")

    def _generate_json(self, path: Path, data: dict):
        """Write JSON report."""
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        logger.info(f"JSON report generated: {path}")
