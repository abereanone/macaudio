"""Generate the Word documents for the 'Bad News First' teaching.

    theGospel-TEACHER.docx   the guide — HAND-EDITED IN WORD, not rebuilt by default
    theGospel-STUDENT.docx   the two-page handout, front and back of one sheet

The teacher guide is now maintained in Word. The TEACHER dict below has been
reverse-engineered from that file so the two stay in step, but running this
script will NOT touch the .docx unless --teacher is passed explicitly.

Usage:
    python .videos/make_docs.py              # handout only (safe)
    python .videos/make_docs.py --teacher    # also rebuild the guide, discarding Word edits
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

HERE = Path(__file__).resolve().parent

RUBRIC = RGBColor(0x9B, 0x22, 0x26)   # madder red - scripture references only
INK = RGBColor(0x16, 0x18, 0x1C)
INK_SOFT = RGBColor(0x4A, 0x4F, 0x58)
INK_FAINT = RGBColor(0x76, 0x7C, 0x86)
SLATE = RGBColor(0x45, 0x59, 0x6B)

SERIF = "Georgia"
SANS = "Calibri"

# --- low-level docx helpers --------------------------------------------------

_PPR_AFTER = ("w:shd", "w:tabs", "w:spacing", "w:ind", "w:jc",
              "w:rPr", "w:sectPr", "w:pPrChange")


def _border(par, edge: str, color: str, sz: int = 6, space: int = 4) -> None:
    """Put a single border on one edge of a paragraph."""
    pPr = par._p.get_or_add_pPr()
    pbdr = pPr.find(qn("w:pBdr"))
    if pbdr is None:
        pbdr = OxmlElement("w:pBdr")
        pPr.insert_element_before(pbdr, *_PPR_AFTER)
    el = OxmlElement(f"w:{edge}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(sz))
    el.set(qn("w:space"), str(space))
    el.set(qn("w:color"), color)
    pbdr.append(el)


def para(doc, space_before=0, space_after=6, left=0.0, keep=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    if left:
        pf.left_indent = Inches(left)
    pf.keep_together = True
    if keep:
        pf.keep_with_next = True
    return p


def run(p, text, *, font=SANS, size=10.5, bold=False, italic=False,
        color=INK, caps=False, spacing=None):
    r = p.add_run(text)
    r.font.name = font
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    r.font.all_caps = caps
    if spacing is not None:                      # letter-spacing, in twentieths of a pt
        rPr = r._element.get_or_add_rPr()
        el = OxmlElement("w:spacing")
        el.set(qn("w:val"), str(spacing))
        rPr.append(el)
    return r


def rich(p, parts):
    """parts: list of (text, kwargs) applied as runs on one paragraph."""
    for text, kw in parts:
        run(p, text, **kw)


def label(doc, text, color=INK_FAINT, space_before=10, space_after=3):
    p = para(doc, space_before=space_before, space_after=space_after, keep=True)
    run(p, text, size=7.5, bold=True, color=color, caps=True, spacing=24)
    return p


def heading(doc, text, size=17, space_before=16, space_after=6):
    p = para(doc, space_before=space_before, space_after=space_after, keep=True)
    run(p, text, font=SERIF, size=size, color=INK)
    return p


def bullet(doc, parts):
    p = para(doc, space_after=5, left=0.25)
    p.paragraph_format.first_line_indent = Inches(-0.16)
    run(p, "—  ", size=10.5, color=INK_FAINT)
    rich(p, parts)
    return p


def writeline(doc, n=1, gap=17):
    """n ruled lines to write on."""
    for _ in range(n):
        p = para(doc, space_before=gap, space_after=0)
        _border(p, "bottom", "AAAAAA", sz=4, space=2)
        run(p, "", size=10.5)


def blank(n=12):
    return "_" * n


def sidebar(doc, color_hex, entries, head=None, head_color=SLATE):
    """A left-ruled block: (text_parts, indent_level) entries."""
    if head:
        p = para(doc, space_before=10, space_after=4, left=0.16, keep=True)
        _border(p, "left", color_hex, sz=12, space=8)
        run(p, head, size=7.5, bold=True, color=head_color, caps=True, spacing=24)
    for parts, sub in entries:
        p = para(doc, space_after=4, left=0.16 + (0.18 if sub else 0))
        _border(p, "left", color_hex, sz=12, space=8)
        rich(p, parts)


def page_setup(doc, title_left, title_right):
    s = doc.sections[0]
    s.page_width, s.page_height = Inches(8.5), Inches(11)
    s.left_margin = s.right_margin = Inches(0.85)
    s.top_margin = Inches(0.8)
    s.bottom_margin = Inches(0.8)

    hp = s.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    hp.add_run("")
    run(hp, title_left, size=7.5, color=INK_FAINT, caps=True, spacing=24)
    run(hp, "\t\t", size=7.5)
    run(hp, title_right, size=7.5, color=INK_FAINT, caps=True, spacing=24)
    _border(hp, "bottom", "DEDEDA", sz=4, space=6)


def masthead(doc, badge, student=False):
    if student:                                   # compact: the sheet has two pages only
        p = para(doc, space_after=2)
        run(p, "Good News, but Bad News ", font=SERIF, size=20, color=INK)
        run(p, "First", font=SERIF, size=20, italic=True, color=RUBRIC)
        run(p, "     Romans 1 & 10", size=8, color=INK_FAINT, caps=True, spacing=22)

        p = para(doc, space_after=6)
        run(p, "Name " + blank(30) + "     Date " + blank(14),
            size=10, color=INK_FAINT)

        p = para(doc, space_before=2, space_after=8)
        _border(p, "bottom", "16181C", sz=8, space=2)
        return

    p = para(doc, space_after=10)
    run(p, badge, size=8, bold=True, color=RUBRIC, caps=True, spacing=28)
    run(p, "      Romans 1 & 10      Michael Coughlin",
        size=8, color=INK_FAINT, caps=True, spacing=24)

    p = para(doc, space_after=4)
    run(p, "Good News, but Bad News ", font=SERIF, size=30, color=INK)
    run(p, "First", font=SERIF, size=30, italic=True, color=RUBRIC)

    p = para(doc, space_after=10)
    run(p, "Why nobody believes the gospel until they know what it saves them "
           "from — and why we tell it to everyone, now.",
        font=SERIF, size=12.5, color=INK_SOFT)

    p = para(doc, space_before=6, space_after=0)
    run(p, "Part One  22 min, as recorded      Part Two  20 min, the how      "
           "Method  taught by question",
        size=8, color=INK_FAINT, spacing=8)
    p = para(doc, space_before=8, space_after=14)
    _border(p, "bottom", "16181C", sz=8, space=2)


# --- content -----------------------------------------------------------------

MOVEMENTS = [
    dict(
        num="I", mins="2 min",
        part="Part One — The gospel & why the bad news comes first",
        title="Set Apart for the Gospel of God",
        texts=["Romans 1:1–2", "Romans 1:3–4"],
    ),
    dict(
        num="II", mins="2 min",
        title="Not Ashamed of It",
        texts=["Romans 1:15", "Romans 1:16", "Romans 1:17", "Habakkuk 2:4"],
    ),
    dict(
        num="III", mins="2 min",
        title="So What Is the Gospel?",
        texts=["1 Corinthians 15:3–4", "Romans 1:3–4 returns"],
    ),
    dict(
        num="IV", mins="3 min",
        title="Saved From What?",
        texts=["Exodus 20:15", "Exodus 20"],
    ),
    dict(
        num="V", mins="4 min", hinge=True,
        title="Nobody Takes Medicine They Don't Need",
        texts=["Ephesians 2:1", "Romans 8:8", "Romans 6:23"],
    ),
    dict(
        num="VI", mins="2 min",
        title="But They Don't Want to Hear It",
        texts=["Leviticus 19:18", "Matthew 22:39"],
    ),
    dict(
        num="VII", mins="3 min",
        title="Who Told You to Do This?",
        texts=["Romans 10:9", "Romans 10:13–15", "Romans 10:17",
               "Matthew 28:19–20", "Colossians 1:28"],
    ),
    dict(
        num="VIII", mins="2 min",
        title="If Not Everyone is Elect, then Why Preach to Everyone?",
        texts=["Ephesians 1:4", "Romans 10:13 returns"],
    ),
    dict(
        num="IX", mins="2 min",
        title="There May Not Be a Next Year",
        texts=["James 4:13–15", "Luke 12:16–21", "Ephesians 2:1–3", "John 3:18",
               "John 3:36", "Romans 5:12", "Colossians 2:13"],
    ),

    # ---- Part Two: new material, not from the recording ----
    dict(
        num="X", mins="6 min",
        part="Part Two — So how do we actually do it?",
        title="Ways In",
        texts=["Acts 8:5", "Acts 8:30–35", "Acts 2:14", "2 Timothy 4:2",
               "Acts 16:25", "Colossians 3:16", "1 Corinthians 14:24–25",
               "Matthew 5:16", "1 Peter 2:12",
               "Acts 17:22–31", "Acts 16:30–31", "1 Peter 3:15", "Colossians 4:5–6"],
    ),
    dict(
        num="XI", mins="6 min", hinge=True,
        title="Using the Law Lawfully",
        texts=["1 Timothy 1:8", "Galatians 3:24", "Romans 3:20",
               "Romans 2:15", "Matthew 5:21–28"],
    ),
    dict(
        num="XII", mins="5 min",
        title="Getting to the Cross",
        texts=["Mark 1:15", "Acts 17:30", "John 14:6", "Acts 4:12",
               "1 Thessalonians 1:9", "Exodus 20:3",
               "1 Corinthians 15:3–4", "Romans 10:9"],
    ),
    dict(
        num="XIII", mins="3 min",
        title="When It Comes Back at You",
        texts=["2 Timothy 2:24–25", "1 Peter 3:15", "Proverbs 15:1"],
    ),
    dict(
        num="XIV", mins="4 min",
        title="Afterward",
        texts=["Matthew 28:19–20", "Acts 2:41–42", "Ephesians 4:11–16",
               "Hebrews 10:24–25", "Galatians 6:2", "Hebrews 13:17",
               "1 Corinthians 3:6–7", "Romans 10:14–15"],
    ),
]

INDEX = [
    ("Romans 1:1", "I", "Servant, called apostle, set apart for the gospel of God", True),
    ("Romans 1:2", "I", "Promised beforehand through the prophets", True),
    ("Romans 1:3–4", "I · VII", "David's line in the flesh; declared Son of God by resurrection", True),
    ("Romans 1:15", "II", "Eager to preach it", True),
    ("Romans 1:16", "II", "Not ashamed — the power of God for salvation", True),
    ("Romans 1:17", "II", "The righteousness of God revealed, by faith", True),
    ("Habakkuk 2:4", "II", "Quoted inside Rom. 1:17 — the righteous shall live by faith", False),
    ("1 Corinthians 15:3–4", "III", "Died, buried, raised — according to the Scriptures", True),
    ("Exodus 20:15", "IV", "“You shall not steal” — the law defines sin", True),
    ("Exodus 20", "IV", "The Decalogue as a whole; and there is more than the Ten", False),
    ("Romans 6:23", "V", "The wages of sin is death", True),
    ("Ephesians 2:1", "V", "Dead in sin", True),
    ("Romans 8:8", "V", "Cannot please God", True),
    ("Leviticus 19:18", "VI", "Love your neighbor as yourself", False),
    ("Matthew 22:39", "VI", "The second commandment, as Jesus gives it", False),
    ("Matthew 28:19–20", "VII", "Go and make disciples of all nations", False),
    ("Romans 10:9", "VII", "Confess with your mouth, believe in your heart", True),
    ("Romans 10:11", "VII", "Never put to shame — quoting Isaiah 28:16", True),
    ("Romans 10:13", "VII · VIII", "Everyone who calls on the Lord will be saved — quoting Joel 2:32", True),
    ("Romans 10:14–15", "VII", "The chain: call, believe, hear, preach, sent — quoting Isaiah 52:7", True),
    ("Romans 10:17", "VII", "Faith comes by hearing, hearing by the word of Christ", True),
    ("Colossians 1:28", "VII", "We proclaim Him — to present everyone complete in Christ", True),
    ("Ephesians 1:4", "VIII", "Chosen in Him before the foundation of the world", True),
    ("Ephesians 2:1–3", "IX", "Dead in trespasses; by nature children of wrath", False),
    ("John 3:18", "IX", "The one who does not believe is condemned already", False),
    ("John 3:36", "IX", "The wrath of God remains on him", False),
    ("Romans 5:12", "IX", "Death spread to all", False),
    ("Colossians 2:13", "IX", "Dead in your trespasses — supporting text", False),
    ("James 4:13–15", "IX", "“Next year we will go…” — the arrogance of delay", True),
    ("Luke 12:16–21", "IX", "The rich fool — this night your soul is required of you", False),
    (None, "Part Two — the how", None, False),
    ("Acts 8:5", "X", "Philip proclaims Christ to a crowd — the declaration", False),
    ("Acts 8:30–35", "X", "The same man opens with a question — starts where the man is", False),
    ("Acts 2:14", "X", "Peter stands up and lifts his voice at Pentecost", False),
    ("2 Timothy 4:2", "X", "Preach the word, in season and out of season", False),
    ("Acts 16:25", "X", "Praying and singing at midnight — the prisoners were listening", False),
    ("Acts 16:17", "X", "The slave girl announces the way of salvation for days", False),
    ("Colossians 3:16", "X", "Teaching and admonishing one another in psalms and hymns", False),
    ("Ephesians 5:19", "X", "Addressing one another in psalms, hymns, spiritual songs", False),
    ("1 Corinthians 14:24–25", "X", "The outsider walks in, is convicted, and worships", False),
    ("Matthew 5:16", "X", "Good works so they glorify the Father — which presupposes they know Him", False),
    ("1 Peter 2:12", "X", "Honorable conduct so they see and glorify God — same requirement", False),
    ("Acts 17:22–31", "X", "Paul at Athens — observation into declaration", False),
    ("Acts 16:30–31", "X", "The jailer asks; Paul answers flatly", False),
    ("1 Peter 3:15", "X · XIII", "Prepared to give a defense, with gentleness and respect", False),
    ("Colossians 4:5–6", "X", "Wisdom toward outsiders; how to answer each person", False),
    ("1 Timothy 1:8", "XI", "The law is good if one uses it lawfully", False),
    ("Galatians 3:24", "XI", "The law as guardian, leading to Christ", False),
    ("Romans 3:20", "XI", "Through the law comes the knowledge of sin", False),
    ("Romans 2:15", "XI", "Conscience also bearing witness — the target", False),
    ("Matthew 5:21–28", "XI", "Christ raises the standard rather than lowering it", False),
    ("Mark 1:15", "XII", "Repent and believe the gospel", False),
    ("Acts 17:30", "XII", "God commands all people everywhere to repent", False),
    ("John 14:6", "XII", "The way, the truth, the life — no one comes to the Father but by Him", False),
    ("Acts 4:12", "XII", "No other name under heaven by which we must be saved", False),
    ("1 Thessalonians 1:9", "XII", "Turned to God from idols, to serve the living and true God", False),
    ("Exodus 20:3", "XII", "No other gods before Me — the first commandment, returning", False),
    ("2 Timothy 2:24–25", "XIII", "Not quarrelsome; God may perhaps grant repentance", False),
    ("Proverbs 15:1", "XIII", "A soft answer turns away wrath", False),
    ("Matthew 28:19–20", "VII · XIV", "Make disciples, baptizing and teaching — not merely converts", False),
    ("Acts 2:41–42", "XIV", "Baptized, and devoted to teaching, fellowship, bread, and prayer", False),
    ("Ephesians 4:11–16", "XIV", "Pastors and teachers given to equip; no longer children", False),
    ("Hebrews 10:24–25", "XIV", "Not neglecting to meet together; stirring one another up", False),
    ("Galatians 6:2", "XIV", "Bear one another's burdens", False),
    ("Hebrews 13:17", "XIV", "Leaders who keep watch over your souls", False),
    ("1 Corinthians 3:6–7", "XIV", "One plants, another waters, God gives the growth", False),
]

# The student handout is built from this instead of each movement's teacher notes.
# It is deliberately spare: two fill-in lines per movement, no note ruling except at
# the very end, so the whole thing lands on one double-sided sheet.
# Part One fills the front, Part Two the back.
STUDENT = {
    # Part One fills the front of the sheet. I and II track the text as it is read
    # aloud, since the guide carries no notes there.
    "I": ["Paul — a " + blank(9) + " of Christ Jesus, called to be an " + blank(9) +
          ", set apart for the gospel " + blank(6) + " God.",
          "The Son, descended from " + blank(8) + " in the flesh; declared Son of God with "
          "power by His " + blank(12) + "."],
    "II": ["v. 16 — I am not " + blank(9) + " of the gospel; it is the " + blank(9) +
           " of God for salvation to everyone who " + blank(9) + ".",
           "v. 17 — in it the " + blank(14) + " of God is revealed, from faith to faith."],
    "III": ["“Gospel” means " + blank(12) + ".",
            "He " + blank(9) + " for sins, was " + blank(9) + ", and " + blank(9) +
            " again — according to the Scriptures."],
    "IV": ["Sin is " + blank(11) + " against a " + blank(11) +
           " — and the standard is God's.",
           "The standard Jesus kept was the " + blank(9) + " law of God (in addition to the " +
           blank(11) + " law)."],
    "V": ["The bad news is " + blank(8) + " the gospel — but it cannot be skipped.",
          "Would you take medicine for a disease you don't have? So — do you have a " +
          blank(10) + "?",
          "Without the " + blank(9) + " news, people have no reason to believe the " +
          blank(9) + " news."],
    "VI": ["To love your " + blank(11) + " as yourself is to want them to know. Not telling "
           "them would itself be " + blank(8) + "."],
    "VII": ["Call → " + blank(9) + " → " + blank(9) + " → " + blank(9) + " → sent.",
            "Faith comes by " + blank(11) + ", and hearing by the " + blank(10) +
            " of Christ."],
    "VIII": ["We cannot know who the " + blank(9) + " are — so we give the gospel " +
             blank(15) + "."],
    "IX": ["Nobody starts " + blank(11) + ". Apart from Christ a person is already " +
           blank(9) + ".",
           "John 3:18 — condemned " + blank(11) + ".   Luke 12:20 — this night your " +
           blank(9) + " is required of you."],

    # Part Two fills the back.
    "X": ["Proclamation — Acts 8:5.   A question — Acts 8:30.   Overheard " + blank(9) +
          " — Acts 16:25.",
          "Col 3:16 — our singing is " + blank(10) + " and " + blank(11) + " one another.",
          "Matt 5:16 — good works so they glorify the " + blank(8) +
          ". Nobody glorifies a God they cannot " + blank(8) + ".",
          "You do not need the right personality. You need a first " + blank(11) + "."],
    "XI": ["The law is good if used " + blank(11) + " — it is a " + blank(9) +
           ", not a ladder.",
           "Matt 5 — anger equated to " + blank(9) + "; lust equated to " + blank(9) + ".",
           "Aim at the " + blank(11) + ", not the argument."],
    "XII": ["The call is " + blank(9) + " and " + blank(9) + ".",
            "John 14:6 — no one comes to the Father " + blank(11) +
            ".   Acts 4:12 — no other " + blank(8) + ".",
            "1 Thess 1:9 — they turned to God " + blank(6) +
            " idols. Adding Christ to a shelf of other gods is not " + blank(11) + "."],
    "XIII": ["Not " + blank(11) + ", but kind — because God may perhaps grant " +
             blank(11) + "."],
    "XIV": ["Matt 28:19–20 — make " + blank(9) + ", baptizing and " + blank(9) +
            " them. The commission does not end at belief.",
            "We are not recruiting " + blank(9) + " — but a believer " + blank(7) +
            " the church.",
            "One plants, another waters — " + blank(6) + " gives the growth. Our hope: the " +
            blank(8) + " will certainly come."],
}

# The teacher guide. Outline of what was actually taught — the claims, the questions
# asked, the answers given, the texts. No delivery advice: see CUES for that, which is
# kept for reference and is deliberately NOT emitted into the Word document.
TEACHER = {
    # I and II carry no notes: the text is simply read aloud.
    "I": [],
    "II": [],
    "III": [
        ("b", "The word means good news."),
        ("ask", "The sequence"),
        ("q", "So what's the gospel?"),
        ("a", "Good news."),
        ("q", "Good news of what?"),
        ("a", "Good news about Christ Jesus."),
        ("q", "What about him?"),
        ("a", "He died according to the Scriptures, He was buried, and He rose again according "
              "to the Scriptures."),
        ("q", "Why is that good news?"),
        ("a", "Because we can be saved."),
        ("land", "The gospel, irreducible", "He died for sins according to the Scriptures. He "
                 "was buried. He rose again according to the Scriptures."),
    ],
    "IV": [
        ("ask", "The questions"),
        ("q", "Saved from what?"),
        ("a", "Sin."),
        ("q", "What's that?"),
        ("a", "Doing something wrong — which two counter-examples then dismantle."),
        ("q", "So like shooting a basket and missing? Is that sin?"),
        ("a", "No. Failure is not sin."),
        ("q", "If I stepped on your foot by accident, did I sin against you?"),
        ("a", "No. Accident is not sin, even though it caused real harm."),
        ("b", "Sin is offense against a standard, and the standard is God's."),
        ("b", "The standard Jesus kept was the moral law of God. (in addition to the "
              "ceremonial law)"),
    ],
    "V": [
        ("ask", "The question that opens it"),
        ("q", "Does it really seem to help anybody to just tell them good news?"),
        ("a", "No. They need the bad news too."),
        ("b", "The bad news is not the gospel. Telling someone bad news is not preaching the "
              "gospel — but it cannot be skipped."),
        ("illus", [
            "A medicine with good ingredients that genuinely works — would you take it?",
            "Not unless you have the disease it was made to cure.",
            "If I handed you ibuprofen and said it fixes headaches, would you take it if you "
            "didn't have a headache?",
            "So: do you have a headache?",
        ]),
        ("p", "What a person must know about himself before the good news can mean anything:"),
        ("b", "That he is dead in his sin."),
        ("b", "That he is worthy of God's judgment."),
        ("b", "That the wages of sin is death."),
        ("b", "That he can do nothing to please God or to atone for his sin."),
        ("land", "The point", "Without knowing the bad news, people have no reason to believe "
                 "the good news."),
    ],
    "VI": [
        ("ask", "The objections"),
        ("q", "Some people don't like the bad news. Should we just not tell them?"),
        ("q", "What if they say they don't want to hear it — it just makes them feel bad?"),
        ("q", "What if they believe in a God who forgives everybody and think they're going to "
              "heaven no matter what? Why interrupt a good feeling like that?"),
        ("a", "It isn't true, and it ends in hell."),
        ("b", "To love your neighbor as yourself is to want them to know."),
        ("b", "So we say the true thing even when it makes them angry."),
        ("b", "Not telling them would itself be sin."),
    ],
    "VII": [
        ("ask", "The question"),
        ("q", "Where do we get a command from God to tell people this? Not just “the Bible” — "
              "where exactly?"),
        ("b", "The Great Commission — go and make disciples of all nations. Which requires "
              "knowing what to say."),
        ("p", "Romans 10, walked backwards:"),
        ("chain", [
            "Everyone who calls on the name of the Lord will be saved.  (v. 13)",
            "But how can they call on One they have not believed?  (v. 14)",
            "And how can they believe One they have not heard?",
            "And how can they hear without someone preaching?",
            "And how can anyone preach unless they are sent?  (v. 15)",
        ], "Faith comes by hearing, and hearing by the word of Christ.  (v. 17)"),
        ("b", "Colossians 1:28 — we proclaim Him, admonishing and teaching everyone with all "
              "wisdom, that we may present everyone complete in Christ."),
        ("land", "The gospel, stated in full", "Jesus descended from David in the flesh. He was "
                 "demonstrated to be the Son of God with power by His resurrection. His "
                 "resurrection followed His death for others. He is truly the Son of God, and He "
                 "can save all who believe."),
    ],
    "VIII": [
        ("b", "No one believes who is not among God's elect, chosen in Him before the foundation "
              "of the world."),
        ("ask", "The objection"),
        ("q", "Wouldn't it be easier to figure out who the elect are and just give the gospel to "
              "them?"),
        ("q", "If I knew somebody wasn't elect, couldn't I save myself the trouble?"),
        ("a", "We cannot know — and neither can they. Not even the elect know before they are "
              "saved."),
        ("b", "So we give the gospel indiscriminately, to everyone, without sorting."),
        ("b", "We proclaim that everyone who calls on the name of the Lord will be saved."),
        ("b", "When people believe, we trust they are His. When they don't, we hope they will "
              "believe later."),
        ("b", "There is no one we withhold it from — not for disliking them, not for judging "
              "them too far gone."),
    ],
    "IX": [
        ("p", "Nobody starts neutral."),
        ("b", "Apart from Christ a person is already dead in trespasses and sins, and by nature "
              "a child of wrath (Eph 2:1–3). Death spread to all (Rom 5:12)."),
        ("b", "The one who does not believe is not awaiting a verdict — he is condemned already "
              "(John 3:18), and the wrath of God remains on him (John 3:36)."),
        ("b", "If people were neutral by default, delay would only postpone an opportunity. "
              "Because they are dead by default, delay leaves them where they already are."),
        ("ask", "The questions"),
        ("q", "We know for sure we have lots of time to reach people before they die, right?"),
        ("q", "If someone's young, we've got seventy years. We can wait."),
        ("a", "No. We don't know how much time we have. The world might end any day."),
        ("b", "I don't know whether the person standing next to me has five minutes. I don't "
              "know if I'll ever see him again."),
        ("b", "Any second could be his last breath, and Christ could return at any time."),
        ("b", "To put it off is the arrogance of James 4 — next year we will go to such-and-such "
              "a city and do such-and-such a thing."),
        ("b", "Luke 12:16–21 — the man whose ground produced so well that he pulled down his "
              "barns to build bigger ones and told his soul to take its ease for many years. "
              "God's answer: Fool — this night your soul is required of you."),
        ("land", "Where it ends", "They are already dead, and there may not be a next year. "
                 "Both are true at once, so the gospel — and the bad news with it — has to be "
                 "given now."),
    ],
    "X": [
        ("p", "The difficulty is not the content of the gospel. It is the first sentence. "
              "Scripture gives several faithful ways to introduce the conversation."),
        ("b", "Proclamation — Acts 8:5. Philip went down to Samaria and proclaimed Christ to a "
              "crowd. No opening question, no permission asked. Peter at Pentecost stood up and "
              "lifted his voice (Acts 2:14). 2 Tim 4:2 — preach the word, in season and out."),
        ("b", "A question — Acts 8:30–35. The same man ran to the chariot and asked whether he "
              "understood what he was reading, then began from that Scripture and told him the "
              "good news about Jesus."),
        ("b", "Same evangelist, same chapter, two entirely different starting methods."),
        ("b", "Overheard worship — Acts 16:25. Paul and Silas prayed and sang hymns to God at "
              "midnight, and the prisoners were listening. A jailer heard the gospel that "
              "night through hymns."),
        ("b", "Col 3:16 — teaching and admonishing one another in psalms, hymns, and spiritual "
              "songs. The verbs are teaching and admonishing. Our singing is doctrine said out "
              "loud, and whoever is in earshot receives it."),
        ("b", "1 Cor 14:24–25 — the outsider who walks in on a church speaking the truth is "
              "convicted, the secrets of his heart disclosed, and he falls down and worships."),
        ("b", "So the jailer's question did not come from nowhere. His household had heard a "
              "slave girl announce for days that these men proclaimed the way of salvation "
              "(Acts 16:17), and his prison had spent the night hearing them sing. He asked what "
              "he must do to be saved, and Paul answered plainly (Acts 16:30–31)."),
        ("p", "Matthew 5:16 — let your light shine so that they may see your good works and "
              "glorify your Father who is in heaven. The weight of it sits on the last clause."),
        ("b", "A watching neighbor can see the kindness, the marriage, the children, and "
              "conclude you are a good person from a nice family. That glorifies you. It does "
              "not glorify the Father."),
        ("b", "For the deed to land where Jesus aims it, they have to know whose you are and who "
              "He is. Nobody glorifies a God they cannot name. Matt 5:16 presupposes "
              "proclamation. 1 Pet 2:12 implies the same if we believe Romans 10."),
        ("p", "Each door has its own failure:"),
        ("b", "A question can become endless dialogue that never arrives at Christ."),
        ("b", "A proclamation can become a monologue at someone who stopped listening."),
        ("b", "An overheard witness fails when it stays overheard — an admirable life, hearty "
              "singing, and nothing ever actually said. Being noticed is not being told."),
        ("b", "1 Pet 3:15 — prepared to give a defense, with gentleness and respect. Col 4:5–6 — "
              "speech gracious and seasoned with salt, so as to know how to answer each person."),
        ("b", "A tract is an opener, and a good way to get the gospel into someone's hands "
              "for later."),
        ("ask", "Ways in"),
        ("q", "Can I ask you something — what do you think happens after we die?"),
        ("q", "Would you say you're a good person?"),
        ("q", "I want to tell you the best news I know, and it will take two minutes."),
        ("q", "Can I tell you why I'm not afraid to die?"),
        ("land", "The point", "You do not need the right personality. You need a first sentence "
                 "— a question or a declaration — and the willingness to say it."),
    ],
    "XI": [
        ("b", "1 Tim 1:8 — the law is good if one uses it lawfully. Paul assumes there is an "
              "unlawful use."),
        ("b", "The lawful use: Gal 3:24, a guardian to lead us to Christ; Rom 3:20, through the "
              "law comes the knowledge of sin."),
        ("b", "The law is a mirror, not a ladder. We hold it up so a person sees himself. We "
              "never hand it over as something to climb."),
        ("illus", [
            "Walk a person through one or two commandments, personally and slowly — as questions "
            "he answers himself:",
            "Have you ever told a lie? What would that make you?",
            "Matt 5:21–28 — Christ explained the standard is higher than ever thought before: anger "
            "equated to murder, lust equated to adultery. It was never merely outward, so nobody "
            "escapes it on a technicality.",
            "In some cases, we do not tell people they are sinners. We ask them questions until "
            "they tell us. (But it's ok to also proclaim sinfulness)",
        ]),
        ("b", "Rom 2:15 — the work of the law is written on their hearts, their conscience also "
              "bearing witness. Aim at the conscience, not the argument. Nothing new is being "
              "installed; a witness already inside them is being called."),
        ("b", "One or two commandments is enough. Running all ten turns a mirror into a lecture."),
        ("b", "Do not stay in the law. It has a destination — a man left under it and nowhere "
              "else has been given the disease and no medicine."),
    ],
    "XII": [
        ("b", "State the good news plainly, in the words from Movement III: He died for sins "
              "according to the Scriptures, He was buried, He rose again."),
        ("b", "Say what God did, not what they must perform. The gospel is an announcement of a "
              "finished work before it is ever a request."),
        ("b", "The call, as Scripture gives it: repent and believe (Mark 1:15). God commands all "
              "people everywhere to repent (Acts 17:30) — a command, not an invitation to "
              "consider at leisure."),
        ("p", "And the call is exclusive. We are not asking anyone to add Christ to what he "
              "already has."),
        ("b", "John 14:6 — He is the way, the truth, and the life; no one comes to the Father "
              "except through Him. Not a way among ways."),
        ("b", "Acts 4:12 — there is no other name under heaven given among men by which we must "
              "be saved. If there were another, this whole errand would be optional."),
        ("b", "1 Thess 1:9 — Paul commends the Thessalonians because they turned to God from "
              "idols, to serve the living and true God. Both directions in one motion. A man "
              "cannot turn to Him without turning from something."),
        ("b", "So a man who adds Jesus to a shelf of other gods has not repented. He has "
              "redecorated."),
        ("b", "Exodus 20:3 — the first commandment was already in the room back in Movement IV: "
              "no other gods before Me. The gospel does not suspend that commandment. It is how "
              "a man comes to keep it."),
        ("b", "This is what repentance means concretely. Not only feeling sorry — but turning, "
              "and leaving something behind."),
        ("b", "Do not lead someone through a prayer and pronounce him saved. Do not manufacture "
              "a decision. A decision that adds Christ without forsaking idols is the very thing "
              "1 Thessalonians 1:9 says did not happen."),
        ("b", "We call for repentance and faith and leave the verdict to God. Assurance is His "
              "to give."),
        ("land", "The point", "Our job is to make the announcement and issue the call. It was "
                 "never to secure the outcome."),
    ],
    "XIII": [
        ("b", "2 Tim 2:24–25 — the Lord's servant must not be quarrelsome but kind to everyone, "
              "correcting opponents with gentleness, God may perhaps grant them repentance. The "
              "reason for gentleness is in that last clause: we are not the ones who grant it, so "
              "there is nothing to be won by force."),
        ("ask", "What comes back, and the answer"),
        ("q", "I'm a good person."),
        ("a", "By whose standard? — which is back in Movement XI."),
        ("q", "God would never send anyone to hell."),
        ("a", "Then we are talking about a God who does not exist."),
        ("q", "What about people who never heard?"),
        ("a", "That is the burden of Romans 10, and the reason for this conversation."),
        ("q", "You're judging me."),
        ("a", "I am telling you what the Judge said. I am under it too."),
        ("b", "A soft answer turns away wrath (Prov 15:1). Do not win the argument and lose the "
              "person."),
        ("b", "But do not buy peace by softening the truth."),
        ("b", "Know when to stop. Leave the door open, leave them something to read, and leave."),
    ],
    "XIV": [
        ("b", "Pray for them by name, and keep praying after the conversation has gone cold."),
        ("b", "Follow up. Give them a Bible or a Gospel of John, and offer to read it with them."),
        ("b", "Bring them under preaching. Romans 10 does not only send us out; it points to the "
              "ordinary means — a preacher, a congregation, a Lord's Day."),
        ("p", "Be clear about what this is and is not. We are not recruiting attendance, and the "
              "goal was never to fill a room. But if a man believes the gospel, he needs the "
              "church. It is not an optional addition to his conversion."),
        ("b", "The commission itself says so. Matt 28:19–20 is not make converts — it is make "
              "disciples, baptizing them and teaching them to observe all that Christ commanded. "
              "Baptism and ongoing teaching are things a church does. The command in Movement VII "
              "does not stop at the moment someone believes."),
        ("b", "Acts 2:41–42 is the pattern: those who received the word were baptized, and they "
              "devoted themselves to the apostles' teaching, to fellowship, to the breaking of "
              "bread, and to prayer. In Acts, being saved and being joined to the church are "
              "two separate events that always accompany one another."),
        ("b", "Eph 4:11–16 — Christ gave pastors and teachers to equip the saints, so that they "
              "grow up and are no longer children tossed about by every wind of doctrine. A "
              "believer left on his own stays an infant. That is not a slight against him; it is "
              "how God designed him to grow."),
        ("b", "Heb 10:24–25 — not neglecting to meet together, as is the habit of some, but "
              "stirring one another up to love and good works."),
        ("b", "And for life, not only doctrine: Gal 6:2, bear one another's burdens; Heb 13:17, "
              "leaders who keep watch over souls. A new believer with no one watching over his "
              "soul has no one watching over his soul."),
        ("b", "We do not measure any of this by attendance. A man who comes and never believes is "
              "not helped by the seat. But a man who believes and stays away is refusing what God "
              "gave him for his own keeping."),
        ("b", "1 Cor 3:6–7 — one plants, another waters, but God gives the growth; so neither "
              "the one who plants nor the one who waters is anything."),
        ("land", "The last word", "We are responsible for the sowing. We were never responsible "
                 "for the harvest — which is exactly why we can afford to go to everyone. Our "
                 "hope is that the ELECT will certainly come to salvation. Go find them!"),
    ],
}

# Delivery notes. Kept here on purpose and NOT printed into the Word document.
CUES = {
    "IV": "Name the callback aloud — “remember the word we couldn't define?” A question answered "
          "forty minutes later is remembered far better than one answered on the spot.",
    "V": "“So: do you have a headache?” is the pivot of the whole teaching. Ask it, then stop — "
         "three or four seconds, longer than is comfortable from the front.",
    "IX": "Pair James and Luke in that order. James rebukes the presumption from outside; Luke "
          "shows it from the inside and ends it mid-sentence.",
    "X": "Say plainly that nobody has to become a different kind of person to evangelize. If they "
         "hear only the Socratic method, half of them will conclude they need to be clever — and "
         "say nothing at all. Land Matt 5:16 on Movement VII: Romans 10 closed the door on silent "
         "faith, Matthew 5:16 closes it on silent works.",
    "XI": "This is the same tool as Movement IV — the missed basket and the stepped-on foot. "
          "Everyone in the room has already watched it work.",
    "XII": "Movement VIII again, at close range: we call, God decides.",
}


# --- emitters ----------------------------------------------------------------

def emit_spine(doc, teacher: bool):
    label(doc, "Fourteen movements across two parts" if teacher
               else "Where we're going", space_before=4)
    for m in MOVEMENTS:
        if m.get("part"):
            p = para(doc, space_before=10, space_after=4, keep=True)
            _border(p, "bottom", "16181C", sz=4, space=3)
            run(p, m["part"], size=8, bold=True, color=INK, caps=True, spacing=24)
            if teacher:
                total = "22 min · as recorded" if m["num"] == "I" else "20 min · new material"
                run(p, "     " + total, size=8, color=INK_FAINT, spacing=8)
        p = para(doc, space_after=3)
        run(p, f"{m['num']:<6}", font=SANS, size=9, color=INK_FAINT)
        run(p, m["title"], font=SERIF, size=11.5,
            italic=bool(m.get("hinge")), color=INK)
        run(p, "   " + " · ".join(m["texts"][:2]), size=8, color=RUBRIC)
        if teacher:
            run(p, "   " + m["mins"], size=8, color=INK_FAINT)


def emit_partbreak(doc, m, teacher: bool):
    if not teacher:
        # Part One flows straight from the masthead on the front of the sheet;
        # Part Two starts the back.
        if m["num"] != "I":
            doc.add_page_break()
        p = para(doc, space_before=2, space_after=2, keep=True)
        _border(p, "bottom", "16181C", sz=6, space=3)
        run(p, m["part"], size=8, bold=True, color=INK, caps=True, spacing=22)
        return

    doc.add_page_break()
    p = para(doc, space_after=5, keep=True)
    run(p, m["part"].split("—")[0].strip(), size=8, bold=True, color=RUBRIC,
        caps=True, spacing=28)


def emit_student_movement(doc, m):
    """Compact: one heading line, then the fill-in lines. No note ruling."""
    p = para(doc, space_before=6, space_after=1, keep=True)
    run(p, f"{m['num']}   ", size=9, bold=True, color=RUBRIC)
    run(p, m["title"], font=SERIF, size=11.5, color=INK)
    run(p, "   " + " · ".join(m["texts"][:3]), size=7.5, color=INK_FAINT)

    for line in STUDENT.get(m["num"], []):
        p = para(doc, space_after=2)
        p.paragraph_format.line_spacing = 1.35
        run(p, line, font=SERIF, size=11)


def emit_movement(doc, m, teacher: bool):
    if not teacher:
        emit_student_movement(doc, m)
        return

    p = para(doc, space_before=18, space_after=0, keep=True)
    _border(p, "top", "DEDEDA", sz=6, space=10)
    run(p, f"Movement {m['num']}", size=7.5, bold=True, color=INK_FAINT,
        caps=True, spacing=24)
    if teacher:
        run(p, "     " + m["mins"], size=7.5, bold=True, color=RUBRIC,
            caps=True, spacing=16)
    if m.get("hinge"):
        run(p, "     the hinge", size=7.5, bold=True, color=RUBRIC,
            caps=True, spacing=16)

    heading(doc, m["title"], space_before=4, space_after=4)

    p = para(doc, space_after=10, keep=True)
    run(p, "  ·  ".join(m["texts"]), size=8.5, color=RUBRIC)

    blocks = TEACHER.get(m["num"], [])
    for blk in blocks:
        kind = blk[0]

        if kind == "p":
            p = para(doc, space_after=7)
            run(p, blk[1])

        elif kind == "b":
            bullet(doc, [(blk[1], {})])

        elif kind == "ask":
            label(doc, blk[1], color=SLATE)

        elif kind == "q":
            sidebar(doc, "45596B", [([("“" + blk[1] + "”",
                                       dict(font=SERIF, size=11.5))], False)])

        elif kind == "a":
            sidebar(doc, "45596B", [([(blk[1], dict(size=9, color=INK_SOFT,
                                                    italic=True))], True)])

        elif kind == "illus":
            label(doc, "The illustration — keep this one")
            for i, line in enumerate(blk[1]):
                p = para(doc, space_after=5, left=0.16)
                _border(p, "left", "DEDEDA", sz=12, space=8)
                if i == 1:
                    run(p, line, font=SERIF, size=11.5, italic=True)
                elif i == len(blk[1]) - 1:
                    run(p, line, size=10.5, bold=True)
                else:
                    run(p, line)

        elif kind == "chain":
            for i, rung in enumerate(blk[1], 1):
                p = para(doc, space_after=4, left=0.28)
                p.paragraph_format.first_line_indent = Inches(-0.28)
                run(p, f"{i}.  ", size=9, color=INK_FAINT)
                run(p, rung)
            p = para(doc, space_before=4, space_after=8, left=0.28)
            p.paragraph_format.first_line_indent = Inches(-0.28)
            _border(p, "top", "9B2226", sz=4, space=6)
            run(p, "→  ", size=10, color=RUBRIC)
            run(p, blk[2], font=SERIF, size=12)

        elif kind == "land":
            p = para(doc, space_before=10, space_after=2, left=0.16, keep=True)
            _border(p, "left", "9B2226", sz=12, space=8)
            run(p, blk[1], size=7.5, bold=True, color=RUBRIC, caps=True, spacing=24)
            p = para(doc, space_after=8, left=0.16)
            _border(p, "left", "9B2226", sz=12, space=8)
            run(p, blk[2], font=SERIF, size=12.5)

        # --- student-only kinds ---
        elif kind == "f":
            p = para(doc, space_before=2, space_after=9)
            p.paragraph_format.line_spacing = 1.6
            run(p, blk[1], font=SERIF, size=12)

        elif kind == "sq":
            p = para(doc, space_before=10, space_after=2)
            run(p, "“" + blk[1] + "”", font=SERIF, size=11.5)

        elif kind == "lab":
            label(doc, blk[1])

        elif kind == "notes":
            writeline(doc, blk[1])


def emit_index(doc, teacher: bool):
    doc.add_page_break()
    label(doc, "Scripture index — every passage cited, in order", space_before=0)

    cols = 3 if teacher else 2
    t = doc.add_table(rows=1, cols=cols)
    t.style = "Table Grid"
    t.autofit = True

    hdr = ["Reference", "Movement"] + (["Use"] if teacher else [])
    for i, h in enumerate(hdr):
        cell = t.rows[0].cells[i]
        cell.text = ""
        run(cell.paragraphs[0], h, size=7.5, bold=True, color=INK_FAINT,
            caps=True, spacing=20)

    for ref, mv, use, quoted in INDEX:
        cells = t.add_row().cells
        if ref is None:                      # section marker across the whole row
            merged = cells[0]
            for c in cells[1:]:
                merged = merged.merge(c)
            merged.text = ""
            run(merged.paragraphs[0], mv, size=7.5, bold=True,
                color=INK_FAINT, caps=True, spacing=20)
            continue
        cells[0].text = ""
        run(cells[0].paragraphs[0], ref, size=8.5, bold=quoted, color=RUBRIC)
        cells[1].text = ""
        run(cells[1].paragraphs[0], mv, size=8.5, color=INK_FAINT)
        if teacher:
            cells[2].text = ""
            run(cells[2].paragraphs[0], use, size=9, color=INK)

    for row in t.rows:
        for cell in row.cells:
            cell.paragraphs[0].paragraph_format.space_after = Pt(2)
            cell.paragraphs[0].paragraph_format.space_before = Pt(2)


def emit_close(doc, teacher: bool):
    p = para(doc, space_before=20, space_after=6, keep=True)
    _border(p, "top", "16181C", sz=8, space=10)
    run(p, "Application", font=SERIF, size=17, color=INK)

    if teacher:
        p = para(doc, space_after=8)
        run(p, "What to actually do:")
        groups = [
            ("Become", ["People who are more likely to give the gospel than we were last week.",
                        "People unafraid of what someone might think of us, or call us."]),
            ("Carry", ["Tracts — actually on your person, not in a drawer.",
                       "The willingness to start the conversation."]),
            ("Remember", ["No one escapes judgment without hearing this message.",
                          "Someone has to say it. That is the whole argument of Romans 10."]),
        ]
        for head, items in groups:
            label(doc, head)
            for it in items:
                bullet(doc, [(it, {})])
    else:
        label(doc, "One person you will tell this week", space_before=12)
        writeline(doc, 1, gap=15)
        label(doc, "The first sentence you will say to them", space_before=12)
        writeline(doc, 2, gap=15)


def build(teacher: bool, out_dir: Path | str | None = None) -> Path:
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = SANS
    st.font.size = Pt(10.5)
    st.paragraph_format.space_after = Pt(6)

    badge = "Teacher's Copy" if teacher else "Student Handout"
    page_setup(doc, "Good News, but Bad News First", badge)
    masthead(doc, badge, student=not teacher)
    if teacher:                       # the handout has no room for a contents list
        emit_spine(doc, teacher)

    for m in MOVEMENTS:
        if m.get("part"):
            emit_partbreak(doc, m, teacher)
        emit_movement(doc, m, teacher)

    emit_close(doc, teacher)
    # The scripture index was removed from the guide: references sit inline.

    out = Path(out_dir or HERE) / (f"theGospel-{'TEACHER' if teacher else 'STUDENT'}.docx")
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Build the handout; teacher guide is opt-in.")
    ap.add_argument("--teacher", action="store_true",
                    help="ALSO rebuild the teacher guide. This OVERWRITES hand edits "
                         "made in Word. The teacher guide is hand-edited — leave this off "
                         "unless you mean to discard those edits.")
    # The script used to live beside its output in .videos/, so it wrote the
    # .docx next to itself. Now that it lives in tools/ that default would drop
    # Word files into the tools directory, so the destination is explicit.
    ap.add_argument("--out", default=None, metavar="DIR",
                    help="where to write the .docx (default: beside this script)")
    args = ap.parse_args()

    if args.teacher:
        path = build(True, args.out)
        print(f"  wrote {path}  ({path.stat().st_size // 1024} KB)")
    else:
        print("  theGospel-TEACHER.docx  left alone (hand-edited in Word)")

    path = build(False, args.out)
    print(f"  wrote {path}  ({path.stat().st_size // 1024} KB)")
