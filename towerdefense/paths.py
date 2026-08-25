"""
Caminho dos inimigos.

Definido como uma sequencia de celulas de grade (col, row) formando um
caminho continuo (cada passo anda 1 celula na horizontal ou vertical).
Essas celulas ficam bloqueadas para construcao de torres.

Este modulo calcula tudo uma unica vez, na importacao, e expoe as
constantes prontas (PATH_CELLS, PATH_CELL_SET, PATH_POINTS,
PATH_TOTAL_LEN) para o resto do jogo usar.
"""

import math

from .config import GRID_COLS, GRID_ROWS, CELL_SIZE, GRID_ORIGIN_X, GRID_ORIGIN_Y


def cell_center_px(col, row):
    x = GRID_ORIGIN_X + col * CELL_SIZE + CELL_SIZE // 2
    y = GRID_ORIGIN_Y + row * CELL_SIZE + CELL_SIZE // 2
    return x, y


def build_path_cells():
    """Gera um caminho em zigue-zague que cobre boa parte da grade."""
    cells = []
    col = 0
    row = 1
    cells.append((col, row))
    # desce/sobe em "S" percorrendo a grade da esquerda pra direita
    direction_down = True
    while col < GRID_COLS - 1:
        # anda um trecho vertical
        target_row = GRID_ROWS - 2 if direction_down else 1
        while row != target_row:
            row += 1 if direction_down else -1
            cells.append((col, row))
        # anda para a direita (se houver espaco), deixando corredores
        # largos o suficiente para construir e dar merge com conforto
        step = min(3, GRID_COLS - 1 - col)
        if step <= 0:
            break
        for _ in range(step):
            col += 1
            cells.append((col, row))
        direction_down = not direction_down
    return cells


def build_path_points(path_cells):
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


def point_at_distance(dist):
    """Retorna (x, y, angle) na posicao 'dist' ao longo do caminho."""
    remaining = dist
    for i in range(len(PATH_POINTS) - 1):
        x1, y1 = PATH_POINTS[i]
        x2, y2 = PATH_POINTS[i + 1]
        seg_len = math.hypot(x2 - x1, y2 - y1)
        if remaining <= seg_len:
            t = remaining / seg_len if seg_len > 0 else 0
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            angle = math.atan2(y2 - y1, x2 - x1)
            return x, y, angle
        remaining -= seg_len
    x1, y1 = PATH_POINTS[-2]
    x2, y2 = PATH_POINTS[-1]
    angle = math.atan2(y2 - y1, x2 - x1)
    return PATH_POINTS[-1][0], PATH_POINTS[-1][1], angle


# Calculado uma unica vez na importacao do modulo.
PATH_CELLS = build_path_cells()
PATH_CELL_SET = set(PATH_CELLS)
PATH_POINTS = build_path_points(PATH_CELLS)
PATH_TOTAL_LEN = _path_length(PATH_POINTS)
