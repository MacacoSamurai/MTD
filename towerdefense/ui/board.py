"""Desenho do tabuleiro: o caminho serpenteado e a grade de slots de torre."""

import pygame

from ..config import (
    GRID_ROWS, GRID_COLS, GRID_ORIGIN_X, GRID_ORIGIN_Y, CELL_SIZE,
    COL_PATH, COL_PATH_EDGE, COL_GRID_EMPTY, COL_GRID_EMPTY_HOVER, COL_GRID_BORDER,
)
from ..paths import PATH_POINTS, PATH_CELL_SET


def draw_path(surf, offset):
    ox, oy = offset
    pts = [(x + ox, y + oy) for x, y in PATH_POINTS]
    pygame.draw.lines(surf, COL_PATH_EDGE, False, pts, 46)
    pygame.draw.lines(surf, COL_PATH, False, pts, 38)
    # marcas tracejadas
    dash_len = 14
    gap_len = 10
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        seg = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if seg == 0:
            continue
        ux, uy = (x2 - x1) / seg, (y2 - y1) / seg
        d = 0
        while d < seg:
            sx = x1 + ux * d
            sy = y1 + uy * d
            ed = min(d + dash_len, seg)
            ex = x1 + ux * ed
            ey = y1 + uy * ed
            pygame.draw.line(surf, (110, 95, 70), (sx, sy), (ex, ey), 3)
            d += dash_len + gap_len


def draw_grid(game, surf):
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            cell = (col, row)
            if cell in PATH_CELL_SET:
                continue  # caminho e desenhado separadamente, nao e slot
            x = GRID_ORIGIN_X + col * CELL_SIZE
            y = GRID_ORIGIN_Y + row * CELL_SIZE
            rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)
            hovered = (cell == game.hovered_cell)
            buildable = cell not in game.towers
            if hovered and buildable:
                color = COL_GRID_EMPTY_HOVER
            else:
                color = COL_GRID_EMPTY
            pygame.draw.rect(surf, color, rect.inflate(-6, -6), border_radius=8)
            pygame.draw.rect(surf, COL_GRID_BORDER, rect.inflate(-6, -6), 2, border_radius=8)
