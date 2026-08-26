"""
Caminho dos inimigos.

Definido como uma sequencia de celulas de grade (col, row) formando um
caminho continuo (cada passo anda 1 celula na horizontal ou vertical).
Essas celulas ficam bloqueadas para construcao de torres.

O layout do caminho depende do MAPA escolhido (ver maps.py). Por isso
toda a geometria vive na classe MapPath, que e instanciada uma vez por
partida (Game.__init__ / Game.reset) a partir do path_builder do mapa
selecionado no menu. Nada aqui e mais global/fixo no import do modulo.
"""

import math

from .config import GRID_COLS, GRID_ROWS, CELL_SIZE, GRID_ORIGIN_X, GRID_ORIGIN_Y
from .maps import MAP_DEFS, DEFAULT_MAP_ID


def cell_center_px(col, row):
    x = GRID_ORIGIN_X + col * CELL_SIZE + CELL_SIZE // 2
    y = GRID_ORIGIN_Y + row * CELL_SIZE + CELL_SIZE // 2
    return x, y


def _build_path_points(path_cells):
    """Converte as celulas do caminho em pontos de pixel (centro de cada
    celula), adicionando uma extensao para fora da tela no inicio e no fim
    para os inimigos entrarem/saírem suavemente."""
    pts = [cell_center_px(c, r) for c, r in path_cells]
    if len(pts) >= 2:
        x0, y0 = pts[0]
        x1, y1 = pts[1]
        dx, dy = x0 - x1, y0 - y1
        norm = math.hypot(dx, dy) or 1
        entry = (x0 + dx / norm * 100, y0 + dy / norm * 100)
        pts.insert(0, entry)
        xe0, ye0 = pts[-2]
        xe1, ye1 = pts[-1]
        dxe, dye = xe1 - xe0, ye1 - ye0
        norme = math.hypot(dxe, dye) or 1
        exitp = (xe1 + dxe / norme * 100, ye1 + dye / norme * 100)
        pts.append(exitp)
    return pts


def _path_length(points):
    total = 0.0
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        total += math.hypot(x2 - x1, y2 - y1)
    return total


class MapPath:
    """Geometria completa do caminho de um mapa especifico: celulas
    bloqueadas para torres, pontos de pixel e utilitario para andar ao
    longo do caminho por distancia percorrida (usado pelos inimigos)."""

    def __init__(self, map_id=None):
        self.map_id = map_id or DEFAULT_MAP_ID
        map_def = MAP_DEFS[self.map_id]
        self.map_def = map_def
        self.cells = map_def["path_builder"](GRID_COLS, GRID_ROWS)
        self.cell_set = set(self.cells)
        self.points = _build_path_points(self.cells)
        self.total_len = _path_length(self.points)
        self.hp_mult = map_def.get("hp_mult", 1.0)
        self.gold_mult = map_def.get("gold_mult", 1.0)

    def point_at_distance(self, dist):
        """Retorna (x, y, angle) na posicao 'dist' ao longo do caminho."""
        remaining = dist
        pts = self.points
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            seg_len = math.hypot(x2 - x1, y2 - y1)
            if remaining <= seg_len:
                t = remaining / seg_len if seg_len > 0 else 0
                x = x1 + (x2 - x1) * t
                y = y1 + (y2 - y1) * t
                angle = math.atan2(y2 - y1, x2 - x1)
                return x, y, angle
            remaining -= seg_len
        x1, y1 = pts[-2]
        x2, y2 = pts[-1]
        angle = math.atan2(y2 - y1, x2 - x1)
        return pts[-1][0], pts[-1][1], angle
