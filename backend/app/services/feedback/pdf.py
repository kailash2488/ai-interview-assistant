"""Report -> PDF with PyMuPDF's HTML layout (no extra dependency). All text is escaped: answers and
model output are untrusted and must never be able to inject markup."""
import io
from html import escape

import pymupdf

from app.schemas.report import DIMENSION_LABELS, ReportBody

CSS = """
body { font-family: sans-serif; font-size: 10pt; color: #1e293b; }
h1 { font-size: 20pt; margin-bottom: 2pt; }
h2 { font-size: 13pt; margin-top: 16pt; margin-bottom: 4pt; color: #0f172a; }
h3 { font-size: 10.5pt; margin-top: 10pt; margin-bottom: 2pt; }
p { margin-top: 2pt; margin-bottom: 4pt; }
.muted { color: #64748b; font-size: 9pt; }
.score { font-size: 34pt; font-weight: bold; margin: 0; }
td, th { padding: 2pt 4pt; vertical-align: top; }
th { text-align: left; font-size: 9pt; color: #64748b; }
.q { margin-top: 8pt; padding-top: 4pt; border-top: 1px solid #cbd5e1; }
.answer { background-color: #f1f5f9; padding: 4pt; }
.sample { background-color: #ecfdf5; padding: 4pt; }
.note { color: #92400e; font-size: 8.5pt; }
li { margin-bottom: 2pt; }
"""


def _e(text: object) -> str:
    return escape(str(text), quote=True)


BAR_PT = 150  # full-scale bar length


def _bars(rows: list[tuple[str, int]]) -> str:
    out = ['<table width="100%">']
    for label, value in rows:
        v = max(0, min(100, value))
        fill, rest = max(v * BAR_PT / 100, 0.5), max((100 - v) * BAR_PT / 100, 0.5)
        out.append(
            f'<tr><td width="30%">{_e(label)}</td><td><table><tr>'
            f'<td style="width:{fill:.1f}pt; height:7pt; background-color:{"#2a78d6" if v else "#e2e8f0"};"></td>'
            f'<td style="width:{rest:.1f}pt; height:7pt; background-color:#e2e8f0;"></td>'
            f'<td style="width:30pt;"><b>{v}</b></td>'
            f'</tr></table></td></tr>'
        )
    out.append("</table>")
    return "".join(out)


def build_html(body: ReportBody, title: str, created: str) -> str:
    h: list[str] = [f"<h1>Feedback report</h1><p class='muted'>{_e(title)} · {_e(body.target_role)} · {_e(created)}</p>"]
    h.append(f"<p class='score'>{body.overall_score}<span class='muted'> / 100</span></p>")
    h.append(f"<p><b>{_e(body.verdict)}</b></p><p>{_e(body.summary)}</p>")
    c = body.coverage
    h.append(f"<p class='muted'>{_e(body.verdict_basis)} {c.evaluated} of {c.planned_topics} planned topics scored; {c.unanswered} unanswered.</p>")

    h.append("<h2>Score by topic</h2>" + _bars([(a.name, a.score_percent) for a in sorted(body.areas, key=lambda a: -a.score_percent)]))
    h.append("<h2>Score by rubric dimension</h2>" + _bars([(DIMENSION_LABELS.get(k, k), v) for k, v in body.dimension_scores.items()]))

    h.append("<h2>Top strengths</h2>")
    h.append("<ol>" + "".join(f"<li><b>{_e(s.title)}</b>. {_e(s.detail)}</li>" for s in body.strengths) + "</ol>" if body.strengths
             else "<p class='muted'>No topic scored high enough to count as a strength yet.</p>")
    h.append("<h2>Top areas to improve</h2><ol>" + "".join(f"<li><b>{_e(s.title)}</b>. {_e(s.detail)}</li>" for s in body.improvements) + "</ol>")

    h.append("<h2>Your improvement plan</h2>")
    for step in body.improvement_plan:
        h.append(f"<h3>{_e(step.timeframe)}: {_e(step.focus)}</h3><ul>" + "".join(f"<li>{_e(a)}</li>" for a in step.actions) + "</ul>")

    h.append("<h2>How you communicated</h2><ul>" + "".join(f"<li>{_e(o)}</li>" for o in body.communication.observations) + "</ul>")
    v = body.communication.voice
    if v:
        pace = f"about {v.avg_wpm} words per minute" if v.avg_wpm else "pace not measurable"
        h.append(f"<p class='muted'>Spoken answers: {v.answers}; {pace}; {v.total_pauses} long pauses (longest {v.longest_pause:g}s).</p>")

    h.append("<h2>Question by question</h2>")
    for q in body.questions:
        h.append(f"<div class='q'><h3>{q.order_no}. {_e(q.topic)}{' (follow-up)' if q.is_follow_up else ''} &mdash; {q.score_percent}/100</h3>")
        h.append(f"<p><b>Question:</b> {_e(q.question)}</p><p class='answer'><b>Your answer:</b> {_e(q.answer)}</p>")
        h.append(f"<p><b>Feedback:</b> {_e(q.feedback)}</p>")
        if q.missing_points:
            h.append("<p><b>What was missing:</b> " + _e("; ".join(q.missing_points)) + "</p>")
        h.append("<table width='100%'>" + "".join(
            f"<tr><td width='24%'>{_e(DIMENSION_LABELS.get(k, k))}</td><td width='9%'><b>{d.score}/5</b></td>"
            f"<td class='muted'>{_e('“' + d.quote + '”') if d.quote else 'No supporting quote'}</td></tr>" for k, d in q.dimensions.items()) + "</table>")
        for n in q.notes:
            h.append(f"<p class='note'>{_e(n)}</p>")
        if q.sample_answer:
            h.append(f"<p class='sample'><b>A stronger answer:</b> {_e(q.sample_answer)}</p>")
        h.append("</div>")
    return "".join(h)


def render_report_pdf(body: ReportBody, title: str, created: str) -> bytes:
    story = pymupdf.Story(html=build_html(body, title, created), user_css=CSS)
    buffer = io.BytesIO()
    writer = pymupdf.DocumentWriter(buffer)
    page = pymupdf.paper_rect("a4")
    area = page + (40, 40, -40, -44)
    more = 1
    while more:
        device = writer.begin_page(page)
        more, _ = story.place(area)
        story.draw(device)
        writer.end_page()
    writer.close()
    return buffer.getvalue()
