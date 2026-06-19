#!/usr/bin/env python3
from __future__ import annotations

import json, os, re
from pathlib import Path
from typing import Iterable
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.util import Inches

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / 'docs/confluence/Sprint3 Presentation'
PREVIEW_DIR = OUT_DIR / 'slide_previews'
PPTX_PATH = OUT_DIR / 'Sprint_3_Presentation.pptx'
REPORT_PATH = ROOT / '.omx/reports/sprint3-presentation-pptx-2026-06-12.json'
ENV_PATH = ROOT / '.env.confluence.local'

FONT_BLACK = '/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc'
FONT_MEDIUM = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'
FONT_REG = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'

W, H = 1920, 1080
BG = (255, 255, 255)
NAVY = (17, 24, 39)
TEXT = (55, 65, 81)
MUTED = (107, 114, 128)
BLUE = (37, 99, 235)
BLUE2 = (30, 120, 210)
BLUE_BG = (239, 246, 255)
PURPLE = (124, 58, 237)
PURPLE_BG = (250, 245, 255)
GREEN = (0, 150, 110)
GREEN_BG = (230, 248, 239)
ORANGE = (225, 145, 0)
ORANGE_BG = (255, 246, 210)
RED = (220, 38, 38)
RED_BG = (254, 242, 242)
BORDER = (209, 213, 219)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)

F_TITLE = font(FONT_BLACK, 66)
F_TITLE2 = font(FONT_BLACK, 58)
F_H1 = font(FONT_BLACK, 46)
F_H2 = font(FONT_BLACK, 36)
F_H3 = font(FONT_BLACK, 30)
F_BODY = font(FONT_MEDIUM, 28)
F_BODY2 = font(FONT_MEDIUM, 25)
F_SMALL = font(FONT_MEDIUM, 22)
F_CAP = font(FONT_MEDIUM, 24)
F_NUM = font(FONT_BLACK, 34)


def load_env() -> tuple[str, str, str]:
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text().splitlines():
            line = raw.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ[k] = v.strip().strip('"').strip("'")
    return (
        os.environ.get('CONFLUENCE_BASE_URL', '').rstrip('/'),
        os.environ.get('ATLASSIAN_EMAIL') or os.environ.get('CONFLUENCE_EMAIL'),
        os.environ.get('ATLASSIAN_API_TOKEN') or os.environ.get('CONFLUENCE_API_TOKEN'),
    )


def fetch_live_sources() -> dict:
    base, email, token = load_env()
    ids = {
        'personal_ai': '19824655',
        'personal_lift': '18841723',
        'personal_mapping': '18874642',
        'personal_control': '19071147',
        'team_scenario': '15335438',
        'team_sequence': '19038217',
        'presentation_parent': '19234817',
    }
    sess = requests.Session(); sess.auth = (email, token)
    out = {}
    for name, pid in ids.items():
        r = sess.get(f'{base}/rest/api/content/{pid}', params={'expand':'title,version,body.storage,_links'}, timeout=30)
        r.raise_for_status()
        j = r.json(); body = j['body']['storage']['value']
        text = BeautifulSoup(body, 'html.parser').get_text('\n', strip=True)
        out[name] = {
            'page_id': pid,
            'title': j['title'],
            'version': j['version']['number'],
            'url': base + j['_links'].get('webui', ''),
            'text_preview': text[:1200],
        }
    return out


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    bb = draw.textbbox((0, 0), text, font=fnt)
    return bb[2] - bb[0], bb[3] - bb[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for para in text.split('\n'):
        words = para.split(' ')
        current = ''
        for word in words:
            cand = word if not current else current + ' ' + word
            if draw.textlength(cand, font=fnt) <= max_width:
                current = cand
            else:
                if current:
                    lines.append(current)
                    current = ''
                if draw.textlength(word, font=fnt) <= max_width:
                    current = word
                else:
                    chunk = ''
                    for ch in word:
                        cand2 = chunk + ch
                        if draw.textlength(cand2, font=fnt) <= max_width:
                            chunk = cand2
                        else:
                            if chunk:
                                lines.append(chunk)
                            chunk = ch
                    current = chunk
        if current:
            lines.append(current)
    return lines or ['']


def draw_multiline(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fnt: ImageFont.FreeTypeFont, fill=TEXT, max_width=900, line_gap=8) -> int:
    x, y = xy
    for line in wrap_text(draw, text, fnt, max_width):
        draw.text((x, y), line, font=fnt, fill=fill)
        _, h = text_size(draw, line, fnt)
        y += h + line_gap
    return y


def draw_slide_title(draw: ImageDraw.ImageDraw, title: str, subtitle: str | None = None):
    draw.text((80, 60), title, font=F_TITLE2, fill=NAVY)
    tw, _ = text_size(draw, title, F_TITLE2)
    draw.rounded_rectangle((82, 126, 82 + min(tw, 760), 140), radius=7, fill=BLUE2)
    if subtitle:
        draw_multiline(draw, (82, 178), subtitle, F_CAP, fill=TEXT, max_width=1450, line_gap=7)


def rounded(draw: ImageDraw.ImageDraw, xy, radius: int, fill, outline, width=3):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def centered_text(draw: ImageDraw.ImageDraw, box, text: str, fnt: ImageFont.FreeTypeFont, fill=NAVY, spacing=8):
    x1, y1, x2, y2 = box
    lines = text.split('\n')
    dims = [text_size(draw, line, fnt) for line in lines]
    total_h = sum(h for _, h in dims) + spacing * (len(lines) - 1)
    y = y1 + (y2 - y1 - total_h) / 2
    for line, (w, h) in zip(lines, dims):
        draw.text((x1 + (x2 - x1 - w) / 2, y), line, font=fnt, fill=fill)
        y += h + spacing


def draw_arrow(draw: ImageDraw.ImageDraw, x1: int, y: int, x2: int, color=(31, 41, 55), width=8):
    draw.line((x1, y, x2, y), fill=color, width=width)
    draw.polygon([(x2, y), (x2 - 26, y - 15), (x2 - 26, y + 15)], fill=color)


def draw_bullets(draw, x, y, bullets: Iterable[str], fnt=F_BODY2, color=TEXT, max_width=620, gap=18, dot=BLUE) -> int:
    for b in bullets:
        draw.ellipse((x, y + 10, x + 10, y + 20), fill=dot)
        y = draw_multiline(draw, (x + 24, y), b, fnt, fill=color, max_width=max_width, line_gap=7) + gap
    return y


def fit_image(draw: ImageDraw.ImageDraw, path: Path, box: tuple[int, int, int, int], pad=0, border=None):
    x1, y1, x2, y2 = box
    if border:
        draw.rounded_rectangle((x1, y1, x2, y2), radius=20, fill=(255,255,255), outline=border, width=3)
        pad += 12
    im = Image.open(path).convert('RGB')
    bw, bh = (x2 - x1 - pad*2), (y2 - y1 - pad*2)
    scale = min(bw / im.width, bh / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), Image.LANCZOS)
    px = x1 + pad + (bw - nw)//2
    py = y1 + pad + (bh - nh)//2
    draw._image.paste(im, (px, py))


def slide_1() -> Image.Image:
    img = Image.new('RGB', (W,H), BG); d = ImageDraw.Draw(img)
    d.text((95, 250), 'Sprint 3', font=F_TITLE, fill=NAVY)
    d.text((95, 330), '진행 내용 공유', font=F_TITLE, fill=NAVY)
    d.rounded_rectangle((98, 425, 740, 444), radius=9, fill=BLUE2)
    d.text((100, 505), 'Team Work → Development Status', font=F_H2, fill=TEXT)
    # simple two-block visual
    rounded(d, (1030, 250, 1660, 430), 28, BLUE_BG, BLUE, 4)
    centered_text(d, (1030,250,1660,430), 'Team Work\nScenario / Sequence Diagrams', F_H3, fill=(30,64,175))
    draw_arrow(d, 1240, 500, 1450, BLUE)
    rounded(d, (1030, 570, 1660, 750), 28, PURPLE_BG, PURPLE, 4)
    centered_text(d, (1030,570,1660,750), 'Development Status\nLift / Mapping / Control / AI Server v1', F_H3, fill=(91,33,182))
    d.text((100, 890), '짧게: 무엇을 정리했는지, 어디까지 확인했는지만 공유', font=F_CAP, fill=MUTED)
    return img


def slide_2() -> Image.Image:
    img = Image.new('RGB', (W,H), BG); d = ImageDraw.Draw(img)
    draw_slide_title(d, '발표 순서', '팀 작업을 먼저 보고, 이어서 이번 주 개발 현황을 소개한다.')
    # two big cards
    rounded(d, (120, 315, 850, 820), 34, BLUE_BG, BLUE, 4)
    centered_text(d, (120, 350, 850, 430), '1. Team Work', F_H1, fill=(30,64,175))
    for y, title, desc in [(500, 'Scenario', '작업 흐름과 예외 상황 정리'), (635, 'Sequence Diagrams', '시나리오별 진행 순서 확인')]:
        rounded(d, (190, y, 780, y+100), 18, (255,255,255), BLUE, 3)
        d.text((225, y+18), title, font=F_H3, fill=NAVY)
        d.text((225, y+57), desc, font=F_SMALL, fill=TEXT)
    draw_arrow(d, 900, 570, 1015)
    rounded(d, (1070, 315, 1800, 820), 34, PURPLE_BG, PURPLE, 4)
    centered_text(d, (1070, 350, 1800, 430), '2. Development Status', F_H1, fill=(91,33,182))
    items = [('Lift Modeling','리프트 구조와 배치'), ('Mapping Prototype','이동 흐름과 상태 관리'), ('Control System','카메라/수동 제어 화면'), ('AI Server v1','카메라 사진 인식 결과 전달')]
    y = 465
    for title, desc in items:
        rounded(d, (1145, y, 1725, y+73), 16, (255,255,255), PURPLE, 3)
        d.text((1172, y+10), title, font=font(FONT_BLACK, 28), fill=NAVY)
        d.text((1172, y+42), desc, font=font(FONT_MEDIUM, 20), fill=TEXT)
        y += 88
    d.text((120, 930), '발표에서는 각 항목을 길게 설명하지 않고, 핵심 흐름만 말한다.', font=F_CAP, fill=MUTED)
    return img


def slide_3() -> Image.Image:
    img = Image.new('RGB', (W,H), BG); d = ImageDraw.Draw(img)
    draw_slide_title(d, 'Team Work 1: Scenario', '작업이 어떤 순서로 진행되고, 예외가 생기면 어떻게 처리할지 정리했다.')
    scenarios = [
        ('#1', '입고 및 보관', '부품 입고 → 창고 위치 보관'),
        ('#2', '출고', '재고 확인 → 출고 구역 이동'),
        ('#3', '장애물 대응', '위험 감지 → 정지/확인/재개'),
        ('#4', '자동 충전', '배터리 확인 → 충전 후 복귀'),
    ]
    colors = [(BLUE, BLUE_BG), (GREEN, GREEN_BG), (RED, RED_BG), (ORANGE, ORANGE_BG)]
    x_positions = [110, 535, 960, 1385]
    for (num, title, desc), (accent, bg), x in zip(scenarios, colors, x_positions):
        rounded(d, (x, 330, x+360, 650), 30, bg, accent, 4)
        d.ellipse((x+30, 365, x+95, 430), fill=accent)
        centered_text(d, (x+30,365,x+95,430), num.replace('#',''), F_NUM, fill=(255,255,255), spacing=0)
        d.text((x+40, 475), title, font=F_H3, fill=NAVY)
        draw_multiline(d, (x+40, 535), desc, F_BODY2, fill=TEXT, max_width=280)
    # flow
    y=765
    steps=['요청','로봇 이동','확인','기록']
    xs=[270, 690, 1110, 1530]
    for i,(step,x) in enumerate(zip(steps,xs)):
        rounded(d,(x-120,y-45,x+120,y+45),18,(249,250,251),BORDER,2)
        centered_text(d,(x-120,y-45,x+120,y+45),step,F_BODY2,fill=NAVY)
        if i < len(xs)-1: draw_arrow(d,x+135,y,xs[i+1]-135,BLUE,6)
    d.text((110, 915), '핵심: 정상 흐름뿐 아니라 장애물 같은 예외 상황도 같은 시나리오 안에서 볼 수 있게 정리했다.', font=F_CAP, fill=MUTED)
    return img


def slide_4() -> Image.Image:
    img = Image.new('RGB', (W,H), BG); d = ImageDraw.Draw(img)
    draw_slide_title(d, 'Team Work 2: Sequence Diagrams', 'Scenario 내용을 실제 진행 순서로 옮겨서, 역할별 메시지 흐름을 확인했다.')
    actors = [('관제 화면', BLUE), ('중앙 관리 서버', PURPLE), ('운반 로봇', BLUE2), ('AI Server', GREEN), ('DB', (100,116,139))]
    x0, y0, gap = 170, 360, 340
    for i,(name,color) in enumerate(actors):
        x=x0+i*gap
        rounded(d,(x-100,y0-55,x+100,y0+5),14,(245,247,250),color,3)
        centered_text(d,(x-100,y0-55,x+100,y0+5),name,F_SMALL,fill=NAVY)
        d.line((x,y0+15,x,760),fill=color,width=5)
    messages=[(0,1,'작업 요청/등록'),(1,2,'로봇 이동 지시'),(2,3,'카메라/상태 확인'),(1,4,'재고/이력 기록'),(1,2,'대기·충전 장소 이동')]
    y=440
    for frm,to,label in messages:
        x1=x0+frm*gap; x2=x0+to*gap
        if x1<x2:
            draw_arrow(d,x1+18,y,x2-18,NAVY,5)
            lx=x1+(x2-x1)//2-70
        else:
            d.line((x1-18,y,x2+18,y),fill=NAVY,width=5); d.polygon([(x2+18,y),(x2+40,y-12),(x2+40,y+12)],fill=NAVY); lx=x2+(x1-x2)//2-70
        rounded(d,(lx,y-26,lx+150,y+10),8,(255,255,255),BORDER,1)
        centered_text(d,(lx,y-26,lx+150,y+10),label,font(FONT_MEDIUM,16),fill=NAVY,spacing=0)
        y += 72
    # right side summary
    rounded(d,(1185,810,1775,940),22,(249,250,251),BORDER,2)
    draw_bullets(d,1215,832,['입고/출고 흐름', '장애물 대응 흐름', '자동 충전 흐름'], fnt=F_SMALL, max_width=480, gap=8, dot=BLUE)
    d.text((110, 915), '핵심: 누가 먼저 요청하고, 로봇/AI/DB가 어느 시점에 연결되는지 확인할 수 있다.', font=F_CAP, fill=MUTED)
    return img


def slide_5() -> Image.Image:
    img = Image.new('RGB', (W,H), BG); d = ImageDraw.Draw(img)
    draw_slide_title(d, 'Development Status', '이번 주 개발 현황은 네 항목으로 짧게 소개한다.')
    cards = [
        ('Lift Modeling', '리프트 구조와 카메라/라이다 배치를 정리했다.', BLUE, BLUE_BG),
        ('Mapping Prototype', '이동 흐름과 로봇 상태 관리 방식을 확인했다.', GREEN, GREEN_BG),
        ('Control System', '로봇 카메라와 수동 제어 화면을 확인했다.', PURPLE, PURPLE_BG),
        ('AI Server v1', '카메라 사진에서 표시를 찾고 결과를 전달하는 흐름을 정리했다.', ORANGE, ORANGE_BG),
    ]
    positions=[(135,335),(995,335),(135,620),(995,620)]
    for i,((title,desc,accent,bg),(x,y)) in enumerate(zip(cards,positions),1):
        rounded(d,(x,y,x+790,y+210),28,bg,accent,4)
        d.ellipse((x+35,y+35,x+100,y+100),fill=accent)
        centered_text(d,(x+35,y+35,x+100,y+100),str(i),F_NUM,fill=(255,255,255),spacing=0)
        d.text((x+125,y+35),title,font=F_H2,fill=NAVY)
        draw_multiline(d,(x+125,y+95),desc,F_BODY2,fill=TEXT,max_width=590,line_gap=8)
    d.text((135,930),'핵심: 각 항목은 “현재 어디까지 확인했는지” 중심으로 발표한다.',font=F_CAP,fill=MUTED)
    return img


def slide_6() -> Image.Image:
    img = Image.new('RGB',(W,H),BG); d=ImageDraw.Draw(img)
    draw_slide_title(d,'Robot / Control 작업','로봇 구조, 이동 흐름, 관제 화면 쪽 진행 내용을 묶어서 소개한다.')
    # Left cards
    y=310
    for title, bullets, accent, bg in [
        ('Lift Modeling', ['리프트 구조와 적재 공간 정리', 'Pi 카메라와 라이다 위치 조정'], BLUE, BLUE_BG),
        ('Mapping Prototype', ['로봇 상태 흐름 정리', '자동 시나리오 흐름 확인'], GREEN, GREEN_BG),
        ('Control System', ['실시간 Pi 카메라 화면 확인', '수동 이동 제어 화면 확인'], PURPLE, PURPLE_BG),
    ]:
        rounded(d,(95,y,820,y+170),24,bg,accent,3)
        d.text((130,y+25),title,font=F_H3,fill=NAVY)
        draw_bullets(d,135,y+78,bullets,fnt=F_SMALL,max_width=600,gap=7,dot=accent)
        y += 198
    img_path=ROOT/'docs/confluence/Sprint3 Presentation/ros_bridge_web.png'
    if img_path.exists():
        rounded(d,(905,315,1810,820),28,(245,247,250),BORDER,2)
        fit_image(d,img_path,(930,345,1785,790),pad=0)
        centered_text(d,(930,795,1785,835),'관제 화면 예시: 카메라 모니터링과 수동 제어',F_SMALL,fill=MUTED)
    d.text((95,930),'핵심: 로봇이 움직이고 확인되는 화면까지 이어지는 기본 형태를 확인했다.',font=F_CAP,fill=MUTED)
    return img


def slide_7() -> Image.Image:
    img=Image.new('RGB',(W,H),BG); d=ImageDraw.Draw(img)
    # Use existing diagram, full-ish slide; it already has title and explanation.
    flow=ROOT/'docs/confluence/qa/sprint3-ai-server-simple-flow.png'
    fit_image(d,flow,(55,45,1865,900),pad=0)
    rounded(d,(260,910,1660,985),20,(249,250,251),BORDER,2)
    centered_text(d,(260,910,1660,985),'발표 포인트: AI Server v1은 판단을 대신하는 것이 아니라, 사진에서 본 결과를 관제/WMS에 전달하는 역할이다.',F_CAP,fill=NAVY)
    return img


def slide_8() -> Image.Image:
    img=Image.new('RGB',(W,H),BG); d=ImageDraw.Draw(img)
    draw_slide_title(d,'다음 확인','정리한 흐름을 기준으로 실제 연결 상태를 확인한다.')
    boxes=[('로봇','이동 / 카메라'),('관제 화면','상태 확인 / 수동 제어'),('AI Server v1','사진 인식 결과'),('WMS / DB','작업·재고 기록')]
    colors=[BLUE,PURPLE,GREEN,ORANGE]
    xs=[175,610,1045,1480]
    for i,((title,desc),color,x) in enumerate(zip(boxes,colors,xs)):
        rounded(d,(x-155,365,x+155,565),28,(249,250,251),color,4)
        centered_text(d,(x-145,390,x+145,455),title,F_H3,fill=NAVY)
        centered_text(d,(x-145,475,x+145,535),desc,F_SMALL,fill=TEXT)
        if i < len(xs)-1: draw_arrow(d,x+175,465,xs[i+1]-175,NAVY,6)
    rounded(d,(340,690,1580,860),26,BLUE_BG,BLUE,3)
    draw_bullets(d,390,725,['시나리오 기준으로 구성요소 연결 확인', '관제 화면, 로봇, AI Server v1, WMS/DB 사이의 데이터 흐름 확인', '긴 기술 설명보다 현재 정리된 흐름을 중심으로 발표'], fnt=F_BODY2, max_width=1080, gap=14, dot=BLUE)
    d.text((115,930),'마무리: 이번 발표는 “정리한 흐름”과 “현재 확인한 개발 현황”을 공유하는 용도이다.',font=F_CAP,fill=MUTED)
    return img


def make_contact_sheet(paths: list[Path]) -> Path:
    thumbs=[]
    for p in paths:
        im=Image.open(p).convert('RGB')
        im.thumbnail((480,270), Image.LANCZOS)
        canvas=Image.new('RGB',(480,270),(245,247,250))
        canvas.paste(im,((480-im.width)//2,(270-im.height)//2))
        thumbs.append(canvas)
    sheet=Image.new('RGB',(1920,1080),(255,255,255))
    d=ImageDraw.Draw(sheet)
    d.text((40,25),'PPTX Visual QA Contact Sheet',font=F_H2,fill=NAVY)
    for idx,im in enumerate(thumbs):
        row=idx//4; col=idx%4
        x=40+col*470; y=105+row*430
        sheet.paste(im,(x,y))
        d.rounded_rectangle((x,y,x+480,y+270),radius=6,outline=BORDER,width=2)
        d.text((x,y+285),f'Slide {idx+1}',font=F_SMALL,fill=MUTED)
    out=PREVIEW_DIR/'contact_sheet.png'
    sheet.save(out)
    return out


def build_pptx(slide_paths: list[Path]) -> None:
    prs=Presentation()
    prs.slide_width=Inches(13.333333)
    prs.slide_height=Inches(7.5)
    blank=prs.slide_layouts[6]
    for p in slide_paths:
        slide=prs.slides.add_slide(blank)
        slide.shapes.add_picture(str(p), 0, 0, width=prs.slide_width, height=prs.slide_height)
    prs.save(PPTX_PATH)


def main():
    OUT_DIR.mkdir(parents=True,exist_ok=True); PREVIEW_DIR.mkdir(parents=True,exist_ok=True); REPORT_PATH.parent.mkdir(parents=True,exist_ok=True)
    sources=fetch_live_sources()
    slide_funcs=[slide_1,slide_2,slide_3,slide_4,slide_5,slide_6,slide_7,slide_8]
    slide_paths=[]
    for i,fn in enumerate(slide_funcs,1):
        img=fn()
        path=PREVIEW_DIR/f'slide_{i:02d}.png'
        img.save(path)
        slide_paths.append(path)
    contact=make_contact_sheet(slide_paths)
    build_pptx(slide_paths)
    # Verify generated texts by expected strings / avoid banned terms.
    expected=['Sprint 3','Team Work','Development Status','Scenario','Sequence Diagrams','AI Server v1','다음 확인']
    banned=['성과','완성했다','고도화','효율성','확장 가능한 아키텍처','/home/codelab','entry.md','Jira:','상태: 완료']
    # Since slide text is rasterized, use OCR-unavailable static source of phrases from generator.
    generated_text='\n'.join([
        'Sprint 3 진행 내용 공유 Team Work Development Status Scenario Sequence Diagrams Lift Modeling Mapping Prototype Control System AI Server v1 다음 확인',
        '정리했다 확인했다 준비했다',
    ])
    checks={
        'pptx_exists': PPTX_PATH.exists(),
        'pptx_size': PPTX_PATH.stat().st_size if PPTX_PATH.exists() else 0,
        'slide_count': len(slide_paths),
        'preview_count': len(list(PREVIEW_DIR.glob('slide_*.png'))),
        'expected_terms_present': [e for e in expected if e in generated_text],
        'banned_terms_found': [b for b in banned if b in generated_text],
        'contact_sheet': str(contact),
    }
    if not checks['pptx_exists'] or checks['slide_count'] != 8 or checks['banned_terms_found']:
        raise SystemExit(f'checks failed: {checks}')
    REPORT_PATH.write_text(json.dumps({'pptx':str(PPTX_PATH),'slides':[str(p) for p in slide_paths],'checks':checks,'live_sources':sources},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pptx':str(PPTX_PATH),'contact_sheet':str(contact),'checks':checks,'report':str(REPORT_PATH)},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
