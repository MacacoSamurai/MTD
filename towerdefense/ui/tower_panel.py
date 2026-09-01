"""Painel lateral fixo de torres (estilo Bloons TD).

Fica sobreposto na frente do grid, do lado direito da tela, e pode
abrir/fechar deslizando (sem redimensionar o grid). Tem dois "modos"
de conteudo:

- Modo LOJA (game.selected_tower_for_upgrade is None): mostra um card
  por tipo de torre, arrastavel ate a grade para comprar. Dois
  cliques rapidos no mesmo card tambem compram, colocando a torre
  automaticamente na primeira celula vazia disponivel.
- Modo UPGRADE (ha uma torre selecionada no grid): mostra os
  botoes de melhoria (dano/alcance/cadencia) daquela torre, no lugar
  da lista de compra.

As funcoes *_rects() calculam apenas geometria e sao reaproveitadas
tanto para desenhar quanto para testar cliques em game.py.
"""

import pygame

from ..config import (
    WIDTH, HEIGHT, TOP_HUD_HEIGHT, BOTTOM_HUD_HEIGHT,
    TOWER_PANEL_WIDTH, TOWER_PANEL_CARD_H, TOWER_PANEL_CARD_GAP,
    TOWER_TYPES, TOWER_TYPE_KEYS, UPGRADE_LABELS,
    COL_WHITE, COL_RED, COL_GOLD, COL_GREEN, COL_TEXT_DIM, COL_PANEL,
    COL_GRID_BORDER,
)
from ..fonts import get_font
from ..entities.tower import tower_color, tower_name


# ----------------------------------------------------------------------
# GEOMETRIA
# ----------------------------------------------------------------------
def panel_area_rect():
    """Area total do painel quando totalmente aberto (x=WIDTH-largura)."""
    y = TOP_HUD_HEIGHT
    h = HEIGHT - TOP_HUD_HEIGHT - BOTTOM_HUD_HEIGHT
    return pygame.Rect(WIDTH - TOWER_PANEL_WIDTH, y, TOWER_PANEL_WIDTH, h)


def toggle_tab_rect(panel_x):
    """Pequena aba/botao para abrir e fechar o painel, sempre visivel
    na borda esquerda do painel (acompanha o slide)."""
    w, h = 26, 64
    x = panel_x - w
    y = TOP_HUD_HEIGHT + (HEIGHT - TOP_HUD_HEIGHT - BOTTOM_HUD_HEIGHT) // 2 - h // 2
    return pygame.Rect(x, y, w, h)


def shop_card_rects(panel_x):
    """Retorna lista de (rect, type_key) para os cards de compra,
    posicionados dentro do painel na posicao horizontal atual
    (panel_x = borda esquerda do painel, muda durante a animacao)."""
    area = panel_area_rect()
    area.x = panel_x
    rects = []
    y = area.y + 16
    for key in TOWER_TYPE_KEYS:
        r = pygame.Rect(area.x + 12, y, area.w - 24, TOWER_PANEL_CARD_H)
        rects.append((r, key))
        y += TOWER_PANEL_CARD_H + TOWER_PANEL_CARD_GAP
    return rects


def upgrade_button_rects(panel_x):
    """Retorna (rects, back_rect) para o modo de upgrade dentro do
    painel. rects e uma lista de (rect, aspect)."""
    area = panel_area_rect()
    area.x = panel_x
    back_rect = pygame.Rect(area.x + 12, area.y + 12, area.w - 24, 30)
    w = area.w - 24
    h = 56
    gap = 10
    start_y = area.y + 12 + 30 + 44  # abaixo do botao voltar + cabecalho
    aspects = ["damage", "range", "rate"]
    rects = []
    for i, aspect in enumerate(aspects):
        r = pygame.Rect(area.x + 12, start_y + i * (h + gap), w, h)
        rects.append((r, aspect))
    return rects, back_rect


# ----------------------------------------------------------------------
# DESENHO
# ----------------------------------------------------------------------
def draw_tower_panel(game, surf):
    panel_x = game.tower_panel_x
    area = panel_area_rect()
    area.x = panel_x

    if area.right <= 0:
        # totalmente fora da tela: nem desenha
        pass
    else:
        # fundo do painel
        bg = pygame.Surface((area.w, area.h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (*COL_PANEL, 240), (0, 0, area.w, area.h), border_radius=10)
        pygame.draw.rect(bg, COL_GRID_BORDER, (0, 0, area.w, area.h), 2, border_radius=10)
        surf.blit(bg, area.topleft)

        if game.selected_tower_cell is not None and game.selected_tower_cell in game.towers:
            _draw_upgrade_mode(game, surf, panel_x)
        else:
            _draw_shop_mode(game, surf, panel_x)

    # aba de abrir/fechar (sempre desenhada, mesmo com painel fora da tela)
    tab = toggle_tab_rect(panel_x)
    pygame.draw.rect(surf, COL_PANEL, tab, border_radius=6)
    pygame.draw.rect(surf, COL_GRID_BORDER, tab, 2, border_radius=6)
    font_arrow = get_font(16, bold=True)
    arrow = "\u25b6" if game.tower_panel_open else "\u25c0"
    txt = font_arrow.render(arrow, True, COL_WHITE)
    surf.blit(txt, txt.get_rect(center=tab.center))


def _draw_shop_mode(game, surf, panel_x):
    font_lbl = get_font(15, bold=True)
    font_desc = get_font(11)
    font_cost = get_font(13, bold=True)

    for rect, ttype in shop_card_rects(panel_x):
        if game.dragging_from_panel == ttype:
            continue  # esta sendo desenhada seguindo o mouse, nao aqui
        spec = TOWER_TYPES[ttype]
        color = spec["base_color"]
        affordable = game.gold >= game.tower_cost

        bg = (34, 40, 52) if affordable else (28, 28, 32)
        pygame.draw.rect(surf, bg, rect, border_radius=8)
        pygame.draw.rect(surf, color, rect, 2, border_radius=8)

        pygame.draw.circle(surf, color, (rect.x + 22, rect.y + 24), 13)
        pygame.draw.circle(surf, (0, 0, 0), (rect.x + 22, rect.y + 24), 13, 2)

        lbl = font_lbl.render(spec["label"], True, COL_WHITE if affordable else COL_TEXT_DIM)
        surf.blit(lbl, (rect.x + 44, rect.y + 12))

        cost_col = COL_GOLD if affordable else COL_TEXT_DIM
        cost_txt = font_cost.render(f"{game.tower_cost}g", True, cost_col)
        crect = cost_txt.get_rect()
        crect.topright = (rect.right - 10, rect.y + 12)
        surf.blit(cost_txt, crect)

        # descricao, quebrada em ate 2 linhas simples
        desc = spec["desc"]
        words = desc.split(" ")
        lines, cur = [], ""
        max_w = rect.w - 16
        for w in words:
            test = (cur + " " + w).strip()
            if font_desc.size(test)[0] > max_w and cur:
                lines.append(cur)
                cur = w
            else:
                cur = test
        if cur:
            lines.append(cur)
        for i, line in enumerate(lines[:2]):
            dtxt = font_desc.render(line, True, COL_TEXT_DIM)
            surf.blit(dtxt, (rect.x + 10, rect.y + 46 + i * 15))

        hint = "arraste ou clique 2x" if affordable else "sem ouro"
        htxt = font_desc.render(hint, True, COL_TEXT_DIM)
        surf.blit(htxt, (rect.x + 10, rect.bottom - 18))


def _draw_upgrade_mode(game, surf, panel_x):
    cell = game.selected_tower_cell
    tower = game.towers[cell]
    rects, back_rect = upgrade_button_rects(panel_x)
    area = panel_area_rect()
    area.x = panel_x

    # botao "voltar" (fecha o modo upgrade, volta pra loja)
    pygame.draw.rect(surf, (44, 40, 40), back_rect, border_radius=6)
    pygame.draw.rect(surf, COL_RED, back_rect, 1, border_radius=6)
    font_back = get_font(13, bold=True)
    back_txt = font_back.render("< Voltar", True, COL_WHITE)
    surf.blit(back_txt, back_txt.get_rect(center=back_rect.center))

    # cabecalho: tipo + nivel
    color = tower_color(tower.level)
    font_h = get_font(15, bold=True)
    label = TOWER_TYPES[tower.ttype]["label"]
    header = font_h.render(f"{label}", True, COL_WHITE)
    surf.blit(header, (area.x + 12, back_rect.bottom + 10))
    font_sub = get_font(12)
    sub = font_sub.render(f"{tower_name(tower.level)} (Nv.{tower.level})", True, color)
    surf.blit(sub, (area.x + 12, back_rect.bottom + 30))

    font_lbl = get_font(13, bold=True)
    font_val = get_font(11)
    for rect, aspect in rects:
        pts = tower.upgrades[aspect]
        cost = int(round(tower.upgrade_cost(aspect) * game.meta.upgrade_cost_mult()))
        cost = max(1, cost)
        affordable = game.gold >= cost
        bg = (34, 44, 40) if affordable else (30, 30, 34)
        pygame.draw.rect(surf, bg, rect, border_radius=8)
        border_col = COL_GREEN if affordable else (80, 80, 86)
        pygame.draw.rect(surf, border_col, rect, 2, border_radius=8)

        lbl = font_lbl.render(UPGRADE_LABELS[aspect], True, COL_WHITE)
        surf.blit(lbl, (rect.x + 10, rect.y + 6))
        lvl_txt = font_val.render(f"nivel {pts}", True, COL_TEXT_DIM)
        surf.blit(lvl_txt, (rect.x + 10, rect.y + 26))

        cost_col = COL_GOLD if affordable else COL_TEXT_DIM
        cost_txt = font_val.render(f"{cost}g" if affordable else f"{cost}g (sem ouro)", True, cost_col)
        crect = cost_txt.get_rect()
        crect.topright = (rect.right - 10, rect.y + 26)
        surf.blit(cost_txt, crect)

        if aspect == "damage":
            stat_txt = f"{tower.damage:0.0f} dmg"
        elif aspect == "range":
            stat_txt = f"{tower.range:0.0f} alcance"
        else:
            stat_txt = f"{1/tower.fire_rate:0.2f} tiros/s"
        stxt = font_val.render(stat_txt, True, COL_TEXT_DIM)
        srect = stxt.get_rect()
        srect.topright = (rect.right - 10, rect.y + 6)
        surf.blit(stxt, srect)


def draw_dragged_card_ghost(game, surf):
    """Enquanto uma torre esta sendo arrastada do painel, desenha um
    circulo fantasma seguindo o mouse (o alcance/preview real da
    torre ja e desenhado por menus.draw_tower_range_hover-like logic
    em game.py, aqui e so o icone)."""
    ttype = game.dragging_from_panel
    if ttype is None:
        return
    spec = TOWER_TYPES[ttype]
    color = spec["base_color"]
    mx, my = game.mouse_pos
    pygame.draw.circle(surf, (30, 30, 36), (mx, my), 24)
    pygame.draw.circle(surf, color, (mx, my), 20)
    pygame.draw.circle(surf, (0, 0, 0), (mx, my), 20, 2)
