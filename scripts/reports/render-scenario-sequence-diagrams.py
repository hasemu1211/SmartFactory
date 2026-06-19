#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math
import textwrap

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "confluence" / "sequence-diagrams"
QA = ROOT / "docs" / "confluence" / "qa" / "sequence-diagrams"
OUT.mkdir(parents=True, exist_ok=True)
QA.mkdir(parents=True, exist_ok=True)

FONT_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

def font(size: int, bold: bool = False):
    # Keep every text element visually consistent: sequence labels, actor
    # labels, participant headers, and titles all use the same bold family.
    return ImageFont.truetype(FONT_BOLD, size=size)

W, H = 2000, 1250
TOP_Y = 148
BOX_W, BOX_H = 235, 74
LIFE_TOP, LIFE_BOTTOM = 230, 1195
ARROW_COLOR = (34, 39, 50)
TEXT = (17, 24, 39)
BG = (255, 255, 255)
ACTOR_HALF_W = 40
ACTOR_GAP = 18
BAR_HALF_W = 10

PALETTE = {
    "blue": ((230, 243, 255), (24, 121, 210), (190, 222, 250)),
    "green": ((231, 250, 240), (0, 145, 107), (194, 238, 218)),
    "purple": ((241, 236, 255), (112, 70, 230), (218, 206, 250)),
    "red": ((255, 235, 235), (224, 55, 50), (247, 202, 202)),
    "yellow": ((255, 246, 210), (224, 145, 0), (248, 227, 157)),
    "gray": ((246, 247, 249), (104, 112, 128), (220, 224, 230)),
}

@dataclass
class Participant:
    name: str
    x: int
    color: str
    actor: bool = False
    actor_ys: list[int] | None = None

@dataclass
class Msg:
    frm: str
    to: str
    y: int
    label: str
    kind: str = "normal"  # normal | self | note
    height: int = 50
    label_bias: str = "center"  # center | start | end
    label_pos: str = "above"  # above | below

@dataclass
class Diagram:
    slug: str
    title: str
    subtitle: str
    participants: list[Participant]
    messages: list[Msg]
    notes: list[str]
    accent: str


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt) -> tuple[int, int]:
    if not text:
        return 0, 0
    b = draw.multiline_textbbox((0, 0), text, font=fnt, spacing=4)
    return b[2] - b[0], b[3] - b[1]


def fit_lines(text: str, max_chars: int = 12) -> str:
    if len(text) <= max_chars:
        return text
    # Korean textwrap is imperfect; prefer breaking by spaces, then by char length.
    parts = text.split()
    if len(parts) > 1:
        lines, cur = [], ""
        for p in parts:
            cand = p if not cur else cur + " " + p
            if len(cand) <= max_chars:
                cur = cand
            else:
                if cur:
                    lines.append(cur)
                cur = p
        if cur:
            lines.append(cur)
        return "\n".join(lines)
    return "\n".join(text[i:i+max_chars] for i in range(0, len(text), max_chars))


def draw_center_text(draw, xy, text, fnt, fill=TEXT, spacing=4):
    x, y, w, h = xy
    tw, th = text_size(draw, text, fnt)
    draw.multiline_text((x + (w - tw) / 2, y + (h - th) / 2 - 1), text, font=fnt, fill=fill, align="center", spacing=spacing)


def draw_actor(draw, p: Participant):
    """Draw external human actors like the reference images.

    Important reference rule:
    - no participant header box
    - no lifeline / activation bar below the person
    - label is under the stick figure, not above it
    - if the same human participates at separated times, draw another external
      actor near that event instead of implying a lifeline.
    """
    fill, stroke, pale = PALETTE[p.color]
    x = p.x
    ys = p.actor_ys or [TOP_Y + 86]
    for cy in ys:
        draw.ellipse([x-20, cy-40, x+20, cy], outline=stroke, width=5)
        draw.line([x, cy, x, cy+54], fill=stroke, width=5)
        draw.line([x-40, cy+22, x+40, cy+22], fill=stroke, width=5)
        draw.line([x, cy+54, x-36, cy+102], fill=stroke, width=5)
        draw.line([x, cy+54, x+36, cy+102], fill=stroke, width=5)
        label = fit_lines(p.name.strip(), 10)
        fnt = font(22, True)
        tw, th = text_size(draw, label, fnt)
        draw.multiline_text((x - tw/2, cy + 112), label, font=fnt, fill=TEXT, align="center", spacing=3)


def draw_participant(draw, p: Participant):
    fill, stroke, pale = PALETTE[p.color]
    x = p.x
    rect = [x - BOX_W//2, TOP_Y, x + BOX_W//2, TOP_Y + BOX_H]
    draw.rounded_rectangle(rect, radius=14, fill=fill, outline=stroke, width=4)
    draw_center_text(draw, (rect[0], rect[1], BOX_W, BOX_H), fit_lines(p.name, 10), font(27, True))
    draw_dashed_line(draw, x, TOP_Y + BOX_H, x, LIFE_BOTTOM, fill=(165,170,180), width=3, dash=12)
    # Activation bar fully covers the vertical lifeline down to the diagram bottom,
    # so no stray dashed line appears below the bar.
    draw.rounded_rectangle([x-BAR_HALF_W, LIFE_TOP, x+BAR_HALF_W, LIFE_BOTTOM], radius=7, fill=pale, outline=stroke, width=2)


def draw_dashed_line(draw, x1, y1, x2, y2, fill, width=2, dash=10):
    if x1 == x2:
        y = y1
        while y < y2:
            draw.line([x1, y, x2, min(y+dash, y2)], fill=fill, width=width)
            y += dash * 2
    else:
        x = x1
        step = dash if x2 >= x1 else -dash
        while (x < x2 if step > 0 else x > x2):
            x_end = x + step
            if step > 0: x_end = min(x_end, x2)
            else: x_end = max(x_end, x2)
            draw.line([x, y1, x_end, y2], fill=fill, width=width)
            x += step * 2


def arrowhead(draw, x1, y1, x2, y2, fill=ARROW_COLOR, size=13):
    ang = math.atan2(y2-y1, x2-x1)
    pts=[]
    for a in (ang + math.pi * 0.84, ang - math.pi * 0.84):
        pts.append((x2 + size*math.cos(a), y2 + size*math.sin(a)))
    draw.polygon([(x2,y2), pts[0], pts[1]], fill=fill)


def draw_arrow(draw, x1, y, x2, label, dashed=False, start_pad=18, end_pad=18, gap_xs: list[int] | None = None, label_bias="center", label_pos="above"):
    if abs(x2-x1) < 8:
        return
    direction = 1 if x2 > x1 else -1
    sx = x1 + direction * start_pad
    ex = x2 - direction * end_pad
    # line
    # Draw sequence arrows over intermediate activation bars.
    # Earlier versions cut gaps around bars, which made long arrows look like
    # they passed underneath the lifeline bars. The desired visual contract is
    # that message arrows remain continuous and visually sit on top.
    gap_xs = []
    start, end = sorted((sx, ex))
    gaps: list[tuple[float, float]] = []
    cur = start
    for g0, g1 in gaps:
        if cur < g0:
            if dashed:
                draw_dashed_line(draw, cur, y, g0, y, fill=ARROW_COLOR, width=4, dash=14)
            else:
                draw.line([cur, y, g0, y], fill=ARROW_COLOR, width=4)
        cur = max(cur, g1)
    if cur < end:
        if dashed:
            draw_dashed_line(draw, cur, y, end, y, fill=ARROW_COLOR, width=4, dash=14)
        else:
            draw.line([cur, y, end, y], fill=ARROW_COLOR, width=4)
    arrowhead(draw, sx, y, ex, y)
    # label with white background; avoid placing labels directly over intermediate bars.
    fnt = font(22, True if len(label) < 9 else False)
    tw, th = text_size(draw, label, fnt)
    base_cx = (sx + ex) / 2
    if label_bias == "end":
        base_cx = ex - direction * 120
    elif label_bias == "start":
        base_cx = sx + direction * 120
    label_margin = 18
    segments: list[tuple[float, float]] = []
    cur = start
    for g0, g1 in gaps:
        if cur < g0:
            segments.append((cur, g0))
        cur = max(cur, g1)
    if cur < end:
        segments.append((cur, end))
    best_cx = base_cx
    best_cost = float("inf")
    for s0, s1 in segments:
        if s1 - s0 < tw + label_margin * 2:
            continue
        cx = min(max(base_cx, s0 + tw / 2 + label_margin), s1 - tw / 2 - label_margin)
        cost = abs(cx - base_cx)
        if cost < best_cost:
            best_cx, best_cost = cx, cost
    lx = best_cx - tw / 2
    if label_pos == "below":
        ly = y + 11
    else:
        ly = y - th - 11
    draw.rounded_rectangle([lx-9, ly-5, lx+tw+9, ly+th+5], radius=7, fill=(255,255,255), outline=(235,238,242), width=1)
    draw.text((lx, ly), label, font=fnt, fill=TEXT)


def draw_self_arrow(draw, x, y, label, side="right", height=50):
    sign = 1 if side == "right" else -1
    w = 116
    h = height
    x0 = x + sign*BAR_HALF_W
    x1 = x + sign*w
    # polyline: out, down, back
    draw.line([x0, y, x1, y, x1, y+h, x0, y+h], fill=ARROW_COLOR, width=4, joint="curve")
    arrowhead(draw, x1, y+h, x0, y+h)
    fnt = font(22, True if len(label) < 10 else False)
    label_wrapped = fit_lines(label, 12)
    tw, th = text_size(draw, label_wrapped, fnt)
    lx = x1 + 10 if sign > 0 else x1 - tw - 10
    ly = y + h/2 - th/2
    draw.rounded_rectangle([lx-7, ly-4, lx+tw+7, ly+th+4], radius=6, fill=(255,255,255), outline=(235,238,242), width=1)
    draw.multiline_text((lx, ly), label_wrapped, font=fnt, fill=TEXT, spacing=3)


def draw_note_box(draw, d: Diagram):
    if not d.notes:
        return
    fill, stroke, _ = PALETTE[d.accent]
    x0, y0, x1, y1 = 1330, 970, 1905, 1142
    draw.rounded_rectangle([x0, y0, x1, y1], radius=18, fill=(255,253,248), outline=stroke, width=3)
    draw.text((x0+28, y0+22), "예외/확인", font=font(28, True), fill=TEXT)
    y = y0 + 64
    for note in d.notes[:4]:
        draw.text((x0+32, y), f"• {note}", font=font(23), fill=TEXT)
        y += 34


def render(d: Diagram):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    fill, stroke, _ = PALETTE[d.accent]
    # title: keep the reference-like style simple; no large subtitle block in the image.
    draw.text((72, 42), d.title, font=font(43, True), fill=TEXT)
    # subtle accent line below title, away from text.
    draw.rounded_rectangle([74, 100, 390, 107], radius=4, fill=stroke)

    pmap = {p.name: p for p in d.participants}
    for p in d.participants:
        if p.actor:
            draw_actor(draw, p)
        else:
            draw_participant(draw, p)

    # draw messages
    def anchor_x(p: Participant, other_x: int) -> int:
        # Human actors are external: use the actor's CENTER HEIGHT via message y,
        # but keep a small horizontal clearance so lines do not touch or cut through the body.
        if p.actor:
            direction = 1 if other_x > p.x else -1
            return p.x + direction * (ACTOR_HALF_W + ACTOR_GAP)
        return p.x

    for m in d.messages:
        if m.kind.startswith("self") or m.frm == m.to:
            p = pmap[m.frm]
            side = "left" if m.kind == "self_left" else "right"
            if p.x > W - 360:
                side = "left"
            draw_self_arrow(draw, p.x, m.y, m.label, side=side, height=m.height)
        else:
            p1, p2 = pmap[m.frm], pmap[m.to]
            x1 = anchor_x(p1, p2.x)
            x2 = anchor_x(p2, p1.x)
            # Message endpoints should attach to the side edge of the sender/receiver
            # activation bar. Intermediate activation bars are still crossed in the
            # foreground because draw_arrow does not cut gaps around gap_xs.
            start_pad = 0 if p1.actor else BAR_HALF_W
            end_pad = 0 if p2.actor else BAR_HALF_W
            gap_xs = [
                p.x for p in d.participants
                if not p.actor and p.name not in {p1.name, p2.name}
            ]
            draw_arrow(draw, x1, m.y, x2, m.label, start_pad=start_pad, end_pad=end_pad, gap_xs=gap_xs, label_bias=m.label_bias, label_pos=m.label_pos)
    # Keep exceptions out of the main canvas to preserve the simple reference style.
    # Footer source note
    out = OUT / f"{d.slug}.png"
    img.save(out)
    # Save a tiny text source for traceability
    src = OUT / f"{d.slug}.seq.txt"
    with src.open("w", encoding="utf-8") as f:
        f.write(d.title + "\n" + d.subtitle + "\n\n")
        f.write("Participants: " + ", ".join(p.name for p in d.participants) + "\n\n")
        for i, m in enumerate(d.messages, 1):
            f.write(f"{i}. {m.frm} -> {m.to}: {m.label}\n")
        if d.notes:
            f.write("\nNotes:\n" + "\n".join("- " + n for n in d.notes) + "\n")
    return out


def diagrams():
    six = [135, 435, 735, 1035, 1335, 1635]
    return [
        Diagram(
            slug="scenario-01-inbound-storage-sequence",
            title="#1 입고 및 보관",
            subtitle="부품 입고 요청부터 창고 보관, 데이터베이스 갱신과 작업 로그 기록까지",
            accent="blue",
            participants=[
                Participant("관리자", six[0], "blue", actor=True, actor_ys=[225, 1000]),
                Participant("관제 화면", six[1], "green"),
                Participant("중앙 관리 서버", six[2], "purple"),
                Participant("운반 로봇", six[3], "blue"),
                Participant("AI 서버", six[4], "green"),
                Participant("데이터베이스", six[5], "gray"),
            ],
            messages=[
                Msg("관리자", "관제 화면", 270, "입고 요청"),
                Msg("관제 화면", "중앙 관리 서버", 335, "작업 등록"),
                Msg("중앙 관리 서버", "중앙 관리 서버", 400, "로봇 선택", "self_left"),
                Msg("중앙 관리 서버", "운반 로봇", 470, "입고 구역 이동"),
                Msg("운반 로봇", "AI 서버", 540, "수령 확인"),
                Msg("AI 서버", "운반 로봇", 610, "리프트 확인"),
                Msg("운반 로봇", "운반 로봇", 690, "창고 구역 이동", "self"),
                Msg("운반 로봇", "운반 로봇", 770, "지정 위치 하역", "self"),
                Msg("운반 로봇", "중앙 관리 서버", 830, "작업 완료"),
                Msg("중앙 관리 서버", "데이터베이스", 885, "재고/이력 갱신"),
                Msg("중앙 관리 서버", "데이터베이스", 940, "작업 로그 기록"),
                Msg("중앙 관리 서버", "관제 화면", 995, "완료 상태 전달"),
                Msg("관제 화면", "관리자", 1040, "완료 표시"),
                Msg("중앙 관리 서버", "운반 로봇", 1115, "대기/충전 장소 이동"),
            ],
            notes=["장애물 발생 시 #3", "적재 실패 시 관리자 확인", "위치 불가 시 대체 위치 확인"],
        ),
        Diagram(
            slug="scenario-02-outbound-sequence",
            title="#2 출고",
            subtitle="창고 부품을 찾아 출고 구역으로 운반하고 작업 로그를 기록",
            accent="green",
            participants=[
                Participant("관리자", six[0], "blue", actor=True, actor_ys=[220, 1095]),
                Participant("관제 화면", six[1], "green"),
                Participant("중앙 관리 서버", six[2], "purple"),
                Participant("데이터베이스", six[3], "gray"),
                Participant("운반 로봇", six[4], "green"),
                Participant("AI 서버", six[5], "green"),
            ],
            messages=[
                Msg("관리자", "관제 화면", 270, "출고 요청"),
                Msg("관제 화면", "중앙 관리 서버", 335, "작업 등록"),
                Msg("중앙 관리 서버", "데이터베이스", 400, "재고/위치 확인"),
                Msg("데이터베이스", "중앙 관리 서버", 465, "확인 결과"),
                Msg("중앙 관리 서버", "중앙 관리 서버", 535, "로봇 선택", "self_left"),
                Msg("중앙 관리 서버", "운반 로봇", 605, "창고 구역 이동"),
                Msg("운반 로봇", "AI 서버", 675, "수령 확인"),
                Msg("AI 서버", "운반 로봇", 745, "확인 완료"),
                Msg("운반 로봇", "운반 로봇", 815, "출고 구역 이동", "self"),
                Msg("운반 로봇", "운반 로봇", 885, "출고 구역 하역", "self"),
                Msg("운반 로봇", "중앙 관리 서버", 945, "작업 완료"),
                Msg("중앙 관리 서버", "데이터베이스", 1000, "재고/이력 갱신"),
                Msg("중앙 관리 서버", "데이터베이스", 1050, "작업 로그 기록"),
                Msg("중앙 관리 서버", "관제 화면", 1095, "완료 상태 전달"),
                Msg("관제 화면", "관리자", 1140, "출고 완료 표시"),
                Msg("중앙 관리 서버", "운반 로봇", 1180, "대기/충전 장소 이동", label_pos="below"),
            ],
            notes=["재고 부족 시 작업 불가 알림", "같은 구역 사용 중이면 대기"],
        ),
        Diagram(
            slug="scenario-03-obstacle-risk-sequence",
            title="#3 장애물 및 위험 상황 대응",
            subtitle="장애물 감지 후 즉시 정지, 정적 장애물 우회, 동적 장애물 확인, 로그 기록",
            accent="red",
            participants=[
                Participant("운반 로봇", 120, "red"),
                Participant("AI 서버", 395, "green"),
                Participant("장애물", 645, "red", actor=True, actor_ys=[330]),
                Participant("중앙 관리 서버", 880, "purple"),
                Participant("데이터베이스", 1160, "gray"),
                Participant("관제 화면", 1440, "green"),
                Participant("관리자", 1765, "blue", actor=True, actor_ys=[800]),
                Participant("장애물 해소", 625, "red", actor=True, actor_ys=[750]),
            ],
            messages=[
                Msg("운반 로봇", "운반 로봇", 285, "이동 중", "self"),
                Msg("장애물", "AI 서버", 360, "나타남"),
                Msg("AI 서버", "운반 로봇", 425, "장애물 감지"),
                Msg("운반 로봇", "운반 로봇", 505, "즉시 정지", "self"),
                Msg("운반 로봇", "운반 로봇", 575, "정적 장애물\n우회 기동", "self", 70),
                Msg("AI 서버", "중앙 관리 서버", 675, "동적 장애물 확인"),
                Msg("중앙 관리 서버", "관제 화면", 760, "위험 알림"),
                Msg("관제 화면", "관리자", 840, "확인 요청"),
                Msg("장애물 해소", "AI 서버", 800, "해소"),
                Msg("중앙 관리 서버", "중앙 관리 서버", 910, "상황 처리/판단", "self", 130),
                Msg("AI 서버", "중앙 관리 서버", 970, "해소 인지"),
                Msg("중앙 관리 서버", "운반 로봇", 1060, "재개/대기 지시"),
                Msg("중앙 관리 서버", "데이터베이스", 1125, "위험 처리 로그 기록", label_pos="below"),
            ],
            notes=["미등록 사람은 경고", "로봇끼리는 순서 지정", "낙하/통신 끊김/긴급 정지는 중지"],
        ),
        Diagram(
            slug="scenario-04-auto-charge-sequence",
            title="#4 충전 대기",
            subtitle="배터리 부족 시 충전 구역으로 이동해 충전 대기 상태를 표시",
            accent="yellow",
            participants=[
                Participant("중앙 관리 서버", 180, "purple"),
                Participant("운반 로봇", 510, "yellow"),
                Participant("충전 구역", 840, "yellow"),
                Participant("데이터베이스", 1170, "gray"),
                Participant("관제 화면", 1500, "green"),
                Participant("관리자", 1830, "blue", actor=True, actor_ys=[1070]),
            ],
            messages=[
                Msg("중앙 관리 서버", "운반 로봇", 285, "배터리 확인"),
                Msg("운반 로봇", "중앙 관리 서버", 365, "상태 전달"),
                Msg("중앙 관리 서버", "중앙 관리 서버", 435, "20% 미만 제외", "self"),
                Msg("중앙 관리 서버", "운반 로봇", 535, "충전 이동 지시"),
                Msg("운반 로봇", "충전 구역", 625, "충전 구역 이동"),
                Msg("충전 구역", "운반 로봇", 710, "충전 시작"),
                Msg("운반 로봇", "관제 화면", 790, "충전 중 표시"),
                Msg("운반 로봇", "중앙 관리 서버", 875, "50% 이상 알림"),
                Msg("중앙 관리 서버", "운반 로봇", 935, "작업 가능 복귀"),
                Msg("중앙 관리 서버", "데이터베이스", 995, "충전/복귀 로그 기록"),
                Msg("중앙 관리 서버", "관제 화면", 1050, "작업 가능 상태 전달"),
                Msg("관제 화면", "관리자", 1115, "상태 표시"),
            ],
            notes=["이동 불가 시 관리자 확인", "진행 중 작업이 없을 때 충전"],
        ),
    ]

def make_contact(paths: list[Path]):
    thumbs=[]
    for p in paths:
        im=Image.open(p).resize((1000,625))
        thumbs.append(im)
    sheet=Image.new("RGB", (2000, 1250), (250,251,253))
    coords=[(0,0),(1000,0),(0,625),(1000,625)]
    for im, xy in zip(thumbs, coords):
        sheet.paste(im, xy)
    sheet.save(QA / "scenario-sequence-contact-sheet.png")


def main():
    paths=[render(d) for d in diagrams()]
    make_contact(paths)
    print("Rendered:")
    for p in paths:
        print(p.relative_to(ROOT))
    print((QA / "scenario-sequence-contact-sheet.png").relative_to(ROOT))

if __name__ == "__main__":
    main()
