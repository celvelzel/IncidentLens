"""Read-only verification of the shipped deck, notes, images and PDF page counts.

Run with the project's installed environment. Does not invoke an image/model backend.
"""
from pathlib import Path
import hashlib
import json
import re

from pptx import Presentation
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent

def verify():
    speech = (ROOT / 'speech.md').read_text(encoding='utf-8')
    headings = list(re.finditer(r'^## Slide (\d+): (.+)$', speech, re.M))
    assert [int(h.group(1)) for h in headings] == list(range(1, 22))
    assert not re.search(r'[\u3400-\u9fff]', speech)
    tracks = [speech[h.end():headings[i+1].start() if i+1 < len(headings) else len(speech)].strip()
              for i, h in enumerate(headings)]
    ppt = Presentation(ROOT / 'IncidentLens_Deck_version_b.pptx')
    assert len(ppt.slides) == 21
    assert ppt.slide_width * 9 == ppt.slide_height * 16
    jobs = json.loads((ROOT / 'slide_jobs.json').read_text(encoding='utf-8'))
    assert len(jobs['slides']) == 21
    assert sum(j['status'] == 'recorded' for j in jobs['slides']) == 20
    assert sum(j['status'] == 'accepted' for j in jobs['slides']) == 1
    for n, slide in enumerate(ppt.slides, 1):
        assert len(slide.shapes) == 1, n
        assert slide.shapes[0].image.blob == (ROOT / f'origin_image/slide_{n:02}.png').read_bytes(), n
        assert slide.notes_slide.notes_text_frame.text.strip() == tracks[n-1], n
        job = jobs['slides'][n-1]
        if job['status'] == 'recorded':
            assert job['result']['backend_used'] == 'built-in image tool'
    for name in ['IncidentLens_Deck_version_b.pdf', 'Presentation_Script_version_b.pdf']:
        assert len(PdfReader(ROOT / name).pages) == 21, name
    for item in json.loads((ROOT / 'qa_report.json').read_text(encoding='utf-8'))['deliverables']:
        assert hashlib.sha256((ROOT / item['file']).read_bytes()).hexdigest() == item['sha256'], item['file']
    print('PASS: 21 slides, exact source images and English notes, recorded backend provenance, two 21-page PDFs and deliverable hashes.')

if __name__ == '__main__':
    verify()
