#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree, tostring
from xml.dom import minidom
from datetime import datetime, timezone

OUT = Path('docs/confluence')
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1800, 1100

# Palette
C = {
    'ink': '#111827',
    'muted': '#667085',
    'board': '#d0d5dd',
    'line': '#eaecf0',
    'purple_bg': '#ead7ff',
    'purple': '#7c3aed',
    'cyan_bg': '#dcf7fb',
    'cyan': '#0891b2',
    'robot_bg': '#dff4ff',
    'robot': '#0284c7',
    'green_bg': '#ecfdf3',
    'green': '#16a34a',
    'blue_bg': '#e8f4ff',
    'blue': '#2563eb',
    'amber_bg': '#fff7ed',
    'amber': '#d97706',
    'gray_bg': '#f8fafc',
    'gray': '#98a2b3',
    'red': '#ef4444',
}

BASE_FONT = 'Noto Sans CJK KR'


def style(**kw: str | int) -> str:
    return ';'.join(f'{k}={v}' for k, v in kw.items()) + ';'


def pretty(root: Element) -> bytes:
    rough = tostring(root, encoding='utf-8')
    return minidom.parseString(rough).toprettyxml(indent='  ', encoding='utf-8')


class DrawIO:
    def __init__(self, name: str, page_w: int = W, page_h: int = H):
        self.mxfile = Element('mxfile', {
            'host': 'app.diagrams.net',
            'modified': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'agent': 'Codex SmartFactory draw.io generator',
            'version': '26.0.0',
            'type': 'device',
        })
        diagram = SubElement(self.mxfile, 'diagram', {'id': name.lower().replace(' ', '-'), 'name': name})
        self.model = SubElement(diagram, 'mxGraphModel', {
            'dx': str(page_w), 'dy': str(page_h), 'grid': '1', 'gridSize': '10',
            'guides': '1', 'tooltips': '1', 'connect': '1', 'arrows': '1',
            'fold': '1', 'page': '1', 'pageScale': '1', 'pageWidth': str(page_w),
            'pageHeight': str(page_h), 'background': '#ffffff', 'math': '0', 'shadow': '0',
        })
        self.root = SubElement(self.model, 'root')
        SubElement(self.root, 'mxCell', {'id': '0'})
        SubElement(self.root, 'mxCell', {'id': '1', 'parent': '0'})
        self.rect('bg', '', 0, 0, page_w, page_h, fill='#ffffff', stroke='#ffffff', rounded=False, lw=0, z_bg=True)

    def rect(self, id_: str, value: str, x: int, y: int, w: int, h: int, *,
             fill: str, stroke: str, rounded: bool = True, lw: float = 2.0,
             fs: int = 18, bold: bool = False, color: str | None = None,
             align: str = 'center', valign: str = 'middle', spacing: int = 8,
             font: str = BASE_FONT, z_bg: bool = False) -> Element:
        st = style(
            rounded=1 if rounded else 0, whiteSpace='wrap', html=1,
            fillColor=fill, strokeColor=stroke, strokeWidth=lw,
            fontFamily=font, fontSize=fs, fontColor=color or C['ink'],
            fontStyle=1 if bold else 0, align=align, verticalAlign=valign,
            spacing=spacing, arcSize=10,
        )
        if z_bg:
            st += 'movable=0;resizable=0;rotatable=0;deletable=0;locked=1;'
        cell = SubElement(self.root, 'mxCell', {
            'id': id_, 'value': value, 'style': st, 'vertex': '1', 'parent': '1'
        })
        SubElement(cell, 'mxGeometry', {'x': str(x), 'y': str(y), 'width': str(w), 'height': str(h), 'as': 'geometry'})
        return cell

    def text(self, id_: str, value: str, x: int, y: int, w: int, h: int, *,
             fs: int = 18, bold: bool = False, color: str | None = None,
             align: str = 'center', valign: str = 'middle', fill: str = 'none') -> Element:
        st = style(
            text='', html=1, strokeColor='none', fillColor=fill,
            align=align, verticalAlign=valign, whiteSpace='wrap', rounded=0,
            fontFamily=BASE_FONT, fontSize=fs, fontStyle=1 if bold else 0,
            fontColor=color or C['ink'], spacing=4,
        )
        cell = SubElement(self.root, 'mxCell', {
            'id': id_, 'value': value, 'style': st, 'vertex': '1', 'parent': '1'
        })
        SubElement(cell, 'mxGeometry', {'x': str(x), 'y': str(y), 'width': str(w), 'height': str(h), 'as': 'geometry'})
        return cell

    def edge(self, id_: str, source: str, target: str, *, color: str, lw: float = 3.0,
             dashed: bool = False, both: bool = False, exitX: float | None = None,
             exitY: float | None = None, entryX: float | None = None,
             entryY: float | None = None,
             points: list[tuple[int, int]] | None = None) -> Element:
        parts = dict(
            edgeStyle='orthogonalEdgeStyle', rounded=1, orthogonalLoop=1,
            jettySize='auto', html=1, strokeColor=color, strokeWidth=lw,
            endArrow='block', endFill=1, fontFamily=BASE_FONT,
        )
        if dashed:
            parts['dashed'] = 1
        if both:
            parts['startArrow'] = 'block'
            parts['startFill'] = 1
        if exitX is not None:
            parts['exitX'] = exitX
        if exitY is not None:
            parts['exitY'] = exitY
        if entryX is not None:
            parts['entryX'] = entryX
        if entryY is not None:
            parts['entryY'] = entryY
        cell = SubElement(self.root, 'mxCell', {
            'id': id_, 'value': '', 'style': style(**parts), 'edge': '1',
            'parent': '1', 'source': source, 'target': target,
        })
        geo = SubElement(cell, 'mxGeometry', {'relative': '1', 'as': 'geometry'})
        if points:
            arr = SubElement(geo, 'Array', {'as': 'points'})
            for x, y in points:
                SubElement(arr, 'mxPoint', {'x': str(x), 'y': str(y)})
        return cell

    def label(self, id_: str, value: str, x: int, y: int, w: int, h: int, *, color: str) -> Element:
        return self.text(id_, value, x, y, w, h, fs=15, bold=True, color=color, fill='#ffffff')

    def write(self, path: Path) -> None:
        path.write_bytes(pretty(self.mxfile))


def hardware() -> None:
    d = DrawIO('HW Architecture')
    d.text('title', 'HW Architecture', 560, 36, 680, 54, fs=34, bold=True)
    d.rect('board', '', 250, 145, 1300, 880, fill='#ffffff', stroke=C['board'], rounded=False, lw=2.2)

    # Top-level hardware. Source-style: compact blocks, clear relations, no descriptions.
    d.rect('user_pc', 'User PC', 430, 230, 240, 70,
           fill='#f2f4f7', stroke=C['gray'], fs=20, bold=True)
    d.rect('main_server_pc', 'Main Server PC', 430, 350, 280, 72,
           fill='#f2f4f7', stroke=C['gray'], fs=20, bold=True)
    d.rect('wifi_ap', 'Wi-Fi AP / Router', 430, 485, 280, 72,
           fill='#f2f4f7', stroke=C['gray'], fs=20, bold=True)
    d.rect('ai_server_pc', 'AI Server PC', 1160, 350, 280, 72,
           fill='#f2f4f7', stroke=C['gray'], fs=20, bold=True)

    # BOT hardware block.
    d.rect('bot_hw', '', 350, 650, 760, 275,
           fill='#e5e7eb', stroke=C['gray'], fs=22, bold=True, valign='top', spacing=18)
    d.text('bot_hw_title', 'TurtleBot3 Burger x2', 570, 675, 340, 32, fs=24, bold=True)
    d.rect('raspberry_pi', 'Raspberry Pi', 430, 750, 255, 48,
           fill=C['green_bg'], stroke=C['green'], fs=16, bold=True)
    d.rect('opencr', 'OpenCR Board', 760, 750, 255, 48,
           fill=C['green_bg'], stroke=C['green'], fs=16, bold=True)
    d.rect('battery', 'Battery', 865, 675, 110, 46,
           fill='#ffffff', stroke=C['green'], fs=13, bold=True)

    d.rect('pi_camera', 'Pi Camera', 420, 835, 105, 58,
           fill='#ffffff', stroke=C['blue'], fs=13, bold=True)
    d.rect('lidar', 'LDS-03<br>LiDAR', 550, 835, 105, 58,
           fill='#ffffff', stroke=C['blue'], fs=13, bold=True)
    d.rect('imu', 'IMU', 680, 835, 105, 58,
           fill='#ffffff', stroke=C['blue'], fs=13, bold=True)
    d.rect('wheel_motor', 'Wheel<br>Motor', 820, 835, 105, 58,
           fill='#ffffff', stroke=C['amber'], fs=13, bold=True)
    d.rect('lift_motor', 'Lift<br>Motor', 950, 835, 105, 58,
           fill='#ffffff', stroke=C['amber'], fs=13, bold=True)

    # Global camera hardware.
    d.rect('global_camera_hw', '', 1160, 650, 280, 250,
           fill='#e5e7eb', stroke=C['gray'], fs=22, bold=True, valign='top', spacing=18)
    d.text('global_hw_title', 'Global Camera', 1195, 685, 210, 32, fs=22, bold=True)
    d.rect('global_camera_unit', 'Camera Unit', 1242, 775, 115, 58,
           fill=C['green_bg'], stroke=C['green'], fs=14, bold=True)

    # Clean external hardware relations.
    d.edge('user_to_server', 'user_pc', 'main_server_pc', color=C['ink'], both=True,
           exitX=0.5, exitY=1, entryX=0.5, entryY=0, lw=3.0)
    d.edge('server_to_wifi', 'main_server_pc', 'wifi_ap', color=C['ink'], both=True,
           exitX=0.5, exitY=1, entryX=0.5, entryY=0, lw=3.0)
    d.edge('wifi_to_rpi', 'wifi_ap', 'raspberry_pi', color=C['ink'], both=True,
           exitX=0.5, exitY=1, entryX=0.50, entryY=0,
           points=[(570, 620), (558, 620)], lw=3.0)
    d.edge('server_to_ai', 'main_server_pc', 'ai_server_pc', color=C['ink'], both=True,
           exitX=1, exitY=0.5, entryX=0, entryY=0.5, lw=3.0)
    d.edge('global_to_ai', 'global_camera_unit', 'ai_server_pc', color=C['ink'],
           exitX=1, exitY=0.5, entryX=1, entryY=0.5,
           points=[(1480, 804), (1480, 386)], lw=3.0)

    # BOT internal input/output/power relations.
    d.edge('pi_camera_input', 'pi_camera', 'raspberry_pi', color=C['blue'],
           exitX=0.5, exitY=0, entryX=0.16, entryY=1, lw=2.8)
    d.edge('lidar_input', 'lidar', 'raspberry_pi', color=C['blue'],
           exitX=0.5, exitY=0, entryX=0.55, entryY=1, lw=2.8)
    d.edge('imu_input', 'imu', 'opencr', color=C['blue'],
           exitX=0.5, exitY=0, entryX=0.15, entryY=1, lw=2.8)
    d.edge('opencr_to_wheel', 'opencr', 'wheel_motor', color=C['amber'],
           exitX=0.36, exitY=1, entryX=0.5, entryY=0, lw=2.8)
    d.edge('opencr_to_lift', 'opencr', 'lift_motor', color=C['amber'],
           exitX=0.78, exitY=1, entryX=0.5, entryY=0, lw=2.8)
    d.edge('battery_to_opencr', 'battery', 'opencr', color=C['green'],
           exitX=0.5, exitY=1, entryX=0.62, entryY=0, lw=2.8)
    d.edge('rpi_to_opencr', 'raspberry_pi', 'opencr', color=C['ink'], both=True,
           exitX=1, exitY=0.5, entryX=0, entryY=0.5, lw=2.5)

    d.text('input_tag', 'INPUT', 512, 900, 170, 24, fs=13, bold=True, color=C['blue'])
    d.text('output_tag', 'OUTPUT', 830, 900, 190, 24, fs=13, bold=True, color=C['amber'])

    d.write(OUT / 'hardware-architecture.drawio')


def software() -> None:
    d = DrawIO('SW Architecture')
    d.text('title', 'SW Architecture', 560, 36, 680, 54, fs=34, bold=True)
    d.rect('board', '', 250, 145, 1300, 880, fill='#ffffff', stroke=C['board'], rounded=False, lw=2.2)

    # Source-style object blocks; no functional descriptions.
    d.rect('user_gui', 'USER GUI', 695, 225, 250, 82,
           fill='#f2f4f7', stroke=C['gray'], fs=21, bold=True)

    d.rect('legend', '', 1120, 205, 350, 140,
           fill='#f8fafc', stroke=C['gray'], fs=18, bold=True, valign='top', spacing=12)

    def legend_arrow(id_: str, color: str, y: int) -> None:
        d.rect(f'{id_}_from', '', 1175, y, 1, 1,
               fill='none', stroke='none', rounded=False, lw=0)
        d.rect(f'{id_}_to', '', 1252, y, 1, 1,
               fill='none', stroke='none', rounded=False, lw=0)
        d.edge(id_, f'{id_}_from', f'{id_}_to', color=color,
               exitX=0.5, exitY=0.5, entryX=0.5, entryY=0.5, lw=3.2)

    legend_arrow('legend_tcp_arrow', C['red'], 241)
    d.text('tcp_lbl', 'TCP', 1290, 225, 120, 28, fs=18, bold=True, align='left')
    legend_arrow('legend_ros2_arrow', C['amber'], 285)
    d.text('ros2_lbl', 'ROS2', 1290, 269, 120, 28, fs=18, bold=True, align='left')
    legend_arrow('legend_udp_arrow', C['blue'], 329)
    d.text('udp_lbl', 'UDP', 1290, 313, 120, 28, fs=18, bold=True, align='left')

    d.rect('main_server', '', 330, 405, 630, 245,
           fill='#e5e7eb', stroke=C['gray'], fs=23, bold=True, valign='top', spacing=18)
    d.text('main_title', 'Main<br>Server', 365, 498, 110, 66, fs=22, bold=True)
    d.rect('network_manager', 'Network Manager', 730, 520, 180, 58,
           fill=C['green_bg'], stroke=C['green'], fs=15, bold=True)
    d.rect('task_manager', 'Task Manager', 500, 520, 140, 58,
           fill=C['green_bg'], stroke=C['green'], fs=15, bold=True)

    d.rect('ai_server', '', 1110, 405, 420, 335,
           fill='#e5e7eb', stroke=C['gray'], fs=23, bold=True, valign='top', spacing=18)
    d.text('ai_title', 'AI Server', 1265, 430, 170, 32, fs=23, bold=True)
    d.rect('aruco_detection', 'ArUco Marker<br>Detection', 1230, 505, 210, 56,
           fill=C['green_bg'], stroke=C['green'], fs=14, bold=True)
    d.rect('obstacle_detection', 'Obstacle<br>Detection', 1230, 590, 210, 56,
           fill=C['green_bg'], stroke=C['green'], fs=14, bold=True)
    d.rect('human_detection', 'Human<br>Detection', 1230, 675, 210, 56,
           fill=C['green_bg'], stroke=C['green'], fs=14, bold=True)

    d.rect('bot_sw', '', 330, 760, 720, 200,
           fill='#e5e7eb', stroke=C['gray'], fs=23, bold=True, valign='top', spacing=16)
    d.text('bot_sw_title', 'BOT', 625, 785, 120, 30, fs=23, bold=True)
    d.rect('driving_controller', 'Driving<br>Controller', 390, 865, 105, 54,
           fill=C['green_bg'], stroke=C['green'], fs=12, bold=True)
    d.rect('path_planner', 'Path Planner<br>(NAV2)', 540, 865, 120, 54,
           fill=C['green_bg'], stroke=C['green'], fs=12, bold=True)
    d.rect('lift_controller', 'LiftController', 695, 865, 110, 54,
           fill=C['green_bg'], stroke=C['green'], fs=12, bold=True)
    d.rect('camera_opencv', 'Camera<br>(OpenCV)', 835, 865, 105, 54,
           fill=C['green_bg'], stroke=C['green'], fs=12, bold=True)
    d.rect('bot_video_stream', 'Video<br>Stream', 965, 865, 74, 54,
           fill=C['green_bg'], stroke=C['green'], fs=12, bold=True)

    d.rect('global_camera_sw', '', 1120, 760, 390, 200,
           fill='#e5e7eb', stroke=C['gray'], fs=23, bold=True, valign='top', spacing=16)
    d.text('global_sw_title', 'Global Camera', 1190, 790, 220, 30, fs=23, bold=True)
    d.rect('global_video_stream', 'Video Stream', 1240, 865, 185, 54,
           fill=C['green_bg'], stroke=C['green'], fs=15, bold=True)

    # Internal arrows: every inner object connects to a clear source/target.
    d.edge('task_network', 'task_manager', 'network_manager', color=C['ink'], both=True,
           exitX=1, exitY=0.5, entryX=0, entryY=0.5, lw=2.5)
    d.edge('planner_to_driving', 'path_planner', 'driving_controller', color=C['ink'],
           exitX=0, exitY=0.5, entryX=1, entryY=0.5, lw=2.5)
    d.edge('planner_to_lift', 'path_planner', 'lift_controller', color=C['ink'],
           exitX=1, exitY=0.5, entryX=0, entryY=0.5, lw=2.5)
    d.edge('camera_to_video', 'camera_opencv', 'bot_video_stream', color=C['ink'],
           exitX=1, exitY=0.5, entryX=0, entryY=0.5, lw=2.5)
    d.edge('aruco_to_obstacle', 'aruco_detection', 'obstacle_detection', color=C['ink'],
           exitX=0.5, exitY=1, entryX=0.5, entryY=0, lw=2.5)
    d.edge('obstacle_to_human', 'obstacle_detection', 'human_detection', color=C['ink'],
           exitX=0.5, exitY=1, entryX=0.5, entryY=0, lw=2.5)

    # External flows. Dedicated lanes avoid object text and keep ports natural.
    d.edge('gui_main_tcp', 'user_gui', 'network_manager', color=C['red'], both=True,
           exitX=0.5, exitY=1, entryX=0.5, entryY=0, lw=3.0)
    d.label('gui_main_tcp_lbl', 'TCP', 840, 352, 55, 26, color=C['red'])

    d.edge('main_bot_ros2', 'network_manager', 'path_planner', color=C['amber'], both=True,
           exitX=0.5, exitY=1, entryX=0.5, entryY=0,
           points=[(820, 720), (600, 720)], lw=3.0)
    d.label('main_bot_ros2_lbl', 'ROS2', 710, 696, 62, 26, color=C['amber'])

    d.edge('ai_main_tcp', 'network_manager', 'ai_server', color=C['red'], both=True,
           exitX=1, exitY=0.5, entryX=0, entryY=0.32, lw=3.0)
    d.label('ai_main_tcp_lbl', 'TCP', 988, 500, 55, 26, color=C['red'])

    d.edge('bot_ai_udp', 'bot_video_stream', 'aruco_detection', color=C['blue'],
           exitX=1, exitY=0.5, entryX=0, entryY=0.5,
           points=[(1080, 892), (1080, 533)], lw=3.0)
    d.label('bot_ai_udp_lbl', 'UDP', 1045, 735, 55, 26, color=C['blue'])

    d.edge('global_ai_udp', 'global_video_stream', 'human_detection', color=C['blue'],
           exitX=1, exitY=0.5, entryX=1, entryY=0.5,
           points=[(1540, 892), (1540, 703)], lw=3.0)
    d.label('global_ai_udp_lbl', 'UDP', 1488, 745, 55, 26, color=C['blue'])

    d.write(OUT / 'software-architecture.drawio')
if __name__ == '__main__':
    hardware()
    software()
    print(OUT / 'hardware-architecture.drawio')
    print(OUT / 'software-architecture.drawio')
