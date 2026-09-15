"""Desenho do tabuleiro: o caminho serpenteado e a grade de slots de torre."""

import pygame

from ..config import (
    GRID_ROWS, GRID_COLS, GRID_ORIGIN_X, GRID_ORIGIN_Y, CELL_SIZE,
    COL_PATH, COL_PATH_EDGE, COL_GRID_EMPTY, COL_GRID_EMPTY_HOVER, COL_GRID_BORDER,
)
from . import theme


def draw_path(surf, offset, map_path):
    ox, oy = offset
    pts = [(x + ox, y + oy) for x, y in map_path.points]

    # borda externa + preenchimento, com circulos nos vertices para
    # arredondar as quinas (pygame.draw.lines usa "corte reto" nas juntas,
    # o que deixava cantos afiados/serrilhados no caminho anterior).
    pygame.draw.lines(surf, COL_PATH_EDGE, False, pts, 46)
    for p in pts:
        pygame.draw.circle(surf, COL_PATH_EDGE, (int(p[0]), int(p[1])), 23)

    pygame.draw.lines(surf, COL_PATH, False, pts, 38)
    for p in pts:
        pygame.draw.circle(surf, COL_PATH, (int(p[0]), int(p[1])), 19)

    # leve realce no meio da pista para dar sensacao de profundidade
    highlight = theme.shade(COL_PATH, 0.12)
    pygame.draw.lines(surf, highlight, False, pts, 4)

    # marcas tracejadas indicando a direcao do percurso
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
            pygame.draw.line(surf, theme.shade(COL_PATH_EDGE, 0.35), (sx, sy), (ex, ey), 3)
            d += dash_len + gap_len


def draw_grid(game, surf):
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            cell = (col, row)
            if cell in game.map_path.cell_set:
                continue  # caminho e desenhado separadamente, nao e slot
            x = GRID_ORIGIN_X + col * CELL_SIZE
            y = GRID_ORIGIN_Y + row * CELL_SIZE
            rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE).inflate(-6, -6)
            hovered = (cell == game.hovered_cell)
            buildable = cell not in game.towers

            base = COL_GRID_EMPTY_HOVER if (hovered and buildable) else COL_GRID_EMPTY
            # leve degrade vertical por celula: parece "encaixada" na grade
            # em vez de um bloco plano de cor unica.
            mask = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, rect.w, rect.h), border_radius=8)
            grad = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            theme.vertical_gradient(grad, (0, 0, rect.w, rect.h),
                                     theme.shade(base, 0.10), theme.shade(base, -0.10))
            grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(grad, rect.topleft)

            pygame.draw.rect(surf, COL_GRID_BORDER, rect, 2, border_radius=8)

            if hovered and buildable:
                # anel de destaque suave em vez de so trocar o preenchimento,
                # para o hover ficar mais visivel a distancia
                glow = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                pygame.draw.rect(glow, (*COL_GRID_EMPTY_HOVER, 130), (0, 0, rect.w, rect.h),
                                  width=3, border_radius=8)
                surf.blit(glow, rect.topleft)
