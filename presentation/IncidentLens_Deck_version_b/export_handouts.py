"""Export existing generated slides and an English presenter handout to PDF.

This never creates or edits slide images. Images are embedded unchanged as inputs.
"""
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Spacer, PageBreak

ROOT = Path(__file__).resolve().parent
RED = colors.HexColor('#9A0907')
GRAY = colors.HexColor('#666666')
pdfmetrics.registerFont(TTFont('Arial', r'C:\Windows\Fonts\arial.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Bold', r'C:\Windows\Fonts\arialbd.ttf'))

speech=(ROOT/'speech.md').read_text(encoding='utf-8')
matches=list(re.finditer(r'^## Slide (\d+): (.+)$', speech, re.M))
sections=[]
for i,m in enumerate(matches):
    stop=matches[i+1].start() if i+1<len(matches) else len(speech)
    sections.append((int(m.group(1)),m.group(2),speech[m.end():stop].strip()))
assert [n for n,_,_ in sections] == list(range(1,22))

# Slides-only PDF, preserving the deck's full-slide images and 16:9 canvas.
slides_pdf=ROOT/'IncidentLens_Deck_version_b.pdf'
c=canvas.Canvas(str(slides_pdf),pagesize=(960,540),pageCompression=1)
c.setTitle('IncidentLens - version_b')
c.setAuthor('COMP5584 Group 5')
for n,_,_ in sections:
    c.drawImage(str(ROOT/f'origin_image/slide_{n:02}.png'),0,0,width=960,height=540)
    c.showPage()
c.save()

def speaker(n):
    for last,who in [(3,'S1'),(6,'S2'),(9,'S3'),(12,'S4'),(14,'S5'),(15,'S6')]:
        if n<=last:
            return who
    return 'Q&A backup'

title=ParagraphStyle('SlideTitle',fontName='Arial-Bold',fontSize=15,leading=19,textColor=RED,spaceAfter=5)
meta=ParagraphStyle('Meta',fontName='Arial',fontSize=9,leading=12,textColor=GRAY,spaceAfter=10)
label=ParagraphStyle('ScriptLabel',fontName='Arial-Bold',fontSize=11,leading=15,spaceAfter=7)
body=ParagraphStyle('Script',fontName='Arial',fontSize=12,leading=17,spaceAfter=8,textColor=colors.HexColor('#1D1D1F'))

handout=ROOT/'Presentation_Script_version_b.pdf'
width,height=A4
margin=36
image_width=width-2*margin
image_height=image_width*9/16
doc=SimpleDocTemplate(str(handout),pagesize=A4,leftMargin=margin,rightMargin=margin,
                      topMargin=28,bottomMargin=30,title='IncidentLens - Slide-by-slide Presenter Script',
                      author='COMP5584 Group 5')
story=[]
for n,t,words in sections:
    story.append(Paragraph(f'Slide {n}: {escape(t)}',title))
    block='Main presentation' if n<=15 else 'Backup: use during questions'
    story.append(Paragraph(escape(f'{block} - Speaker block: {speaker(n)}'),meta))
    story.append(Image(str(ROOT/f'origin_image/slide_{n:02}.png'),width=image_width,height=image_height))
    story.append(Spacer(1,14))
    story.append(Paragraph('Presenter script',label))
    for paragraph in words.split('\n\n'):
        story.append(Paragraph(escape(paragraph).replace('\n',' '),body))
    if n<21:
        story.append(PageBreak())

def footer(c,doc):
    c.setFont('Arial',8)
    c.setFillColor(GRAY)
    c.drawString(margin,16,'IncidentLens - COMP5584 Group 5 - version_b')
    c.drawRightString(width-margin,16,f'{doc.page}/21')

doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(slides_pdf)
print(handout)
