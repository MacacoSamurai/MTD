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

import math

import pygame

from ..config import (
    WIDTH, HEIGHT, TOP_HUD_HEIGHT, BOTTOM_HUD_HEIGHT,
    TOWER_PANEL_WIDTH, TOWER_PANEL_CARD_H, TOWER_PANEL_CARD_GAP,
    TOWER_TYPES, TOWER_TYPE_KEYS, UPGRADE_LABELS,
    COL_WHITE, COL_RED, COL_GOLD, COL_GREEN, COL_TEXT_DIM, COL_PANEL,
    COL_GRID_BORDER,
)
from ..fonts import get_font
from ..entities.tower import tower_color, tower_name, draw_tower_shape
from . import theme


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
    # 70 (nao 44): o cabecalho agora desenha a torre de verdade (com cano),
    # que e mais alta que o icone de forma generico antigo -- ver
    # _draw_upgrade_mode. Se nao abrir esse espaco, o cano da sniper (o
    # mais longo) entra por baixo do primeiro botao de melhoria.
    start_y = area.y + 12 + 30 + 70  # abaixo do botao voltar + cabecalho
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
        # fundo do painel: leve degrade + sombra pra "flutuar" sobre o grid
        theme.draw_shadow(surf, area, radius=10, offset=(-4, 0), alpha=110)
        bg = pygame.Surface((area.w, area.h), pygame.SRCALPHA)
        mask = pygame.Surface((area.w, area.h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, area.w, area.h), border_radius=10)
        grad = pygame.Surface((area.w, area.h), pygame.SRCALPHA)
        theme.vertical_gradient(grad, (0, 0, area.w, area.h),
                                 theme.shade(COL_PANEL, 0.08), theme.shade(COL_PANEL, -0.12))
        grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        bg.blit(grad, (0, 0))
        bg.set_alpha(245)
        surf.blit(bg, area.topleft)
        pygame.draw.rect(surf, COL_GRID_BORDER, area, 2, border_radius=10)

        if game.selected_tower_cell is not None and game.selected_tower_cell in game.towers:
            _draw_upgrade_mode(game, surf, panel_x)
        else:
            _draw_shop_mode(game, surf, panel_x)

    # aba de abrir/fechar (sempre desenhada, mesmo com painel fora da tela)
    tab = toggle_tab_rect(panel_x)
    hovered_tab = tab.collidepoint(game.mouse_pos)
    tab_fill = theme.shade(COL_PANEL, 0.1) if hovered_tab else COL_PANEL
    theme.draw_panel(surf, tab, tab_fill, border=COL_GOLD if hovered_tab else COL_GRID_BORDER,
                      radius=6, shadow=True)
    # seta desenhada como triangulo (poligono), NAO como glifo de fonte
    # ("\u25b6"/"\u25c0"): SysFont("arial") nem sempre tem esse glifo em
    # todo sistema/instalacao (no Linux costuma cair pra uma fonte de
    # fallback sem ele), e ai o botao ficava com um quadradinho vazio ou
    # nada desenhado -- um triangulo manual sempre aparece, em qualquer
    # maquina.
    cx, cy = tab.center
    s = 6
    if game.tower_panel_open:  # aponta pra direita (fecha o painel)
        points = [(cx - s, cy - s), (cx - s, cy + s), (cx + s, cy)]
    else:  # aponta pra esquerda (abre o painel)
        points = [(cx + s, cy - s), (cx + s, cy + s), (cx - s, cy)]
    pygame.draw.polygon(surf, COL_WHITE, points)


def _draw_shop_mode(game, surf, panel_x):
    font_lbl = get_font(15, bold=True)
    font_desc = get_font(11)
    font_cost = get_font(13, bold=True)

    # nivel com que a torre nasce ao ser comprada agora (pode ser > 1 com
    # a melhoria permanente de gemas "start_tower_level_bonus") -- o card
    # mostra a torre de verdade nesse nivel, entao acompanha essa melhoria
    # tambem, nao so a aparencia por tipo.
    start_level = 1 + int(game.meta.start_tower_level_bonus())

    for rect, ttype in shop_card_rects(panel_x):
        if game.dragging_from_panel == ttype:
            continue  # esta sendo desenhada seguindo o mouse, nao aqui
        spec = TOWER_TYPES[ttype]
        color = spec["base_color"]
        affordable = game.gold >= game.tower_cost
        hovered = rect.collidepoint(game.mouse_pos)

        base_fill = theme.shade(color, -0.82) if affordable else (28, 28, 32)
        if hovered and affordable:
            base_fill = theme.shade(color, -0.72)
        theme.draw_panel(surf, rect, base_fill, border=color if affordable else (70, 70, 76),
                          radius=8, border_w=2 if not hovered else 3, shadow=False)

        # torre de verdade em miniatura (nao um icone generico da forma):
        # usa o mesmo desenho de Tower.draw, entao qualquer mudanca futura
        # na aparencia da torre aparece aqui automaticamente. Radius menor
        # so pra caber no card; sem alvo -> pose neutra (cano pra cima).
        draw_tower_shape(surf, rect.x + 28, rect.y + 30, ttype, start_level,
                          radius=15, show_level=False)

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
    back_hovered = back_rect.collidepoint(game.mouse_pos)
    theme.draw_panel(surf, back_rect, (44, 32, 32) if not back_hovered else (60, 38, 38),
                      border=COL_RED, radius=6, shadow=False)
    font_back = get_font(13, bold=True)
    back_txt = font_back.render("< Voltar", True, COL_WHITE)
    surf.blit(back_txt, back_txt.get_rect(center=back_rect.center))

    # cabecalho: torre de verdade (nao icone generico da forma) + tipo + nivel.
    # O cano aponta pra BAIXO (angle=pi/2) de proposito: e a direcao com
    # mais espaco livre aqui (entre o cabecalho e os botoes de melhoria),
    # sem disputar espaco com o botao "Voltar" acima nem com o texto ao
    # lado -- ver o "70" em upgrade_button_rects, calculado pra caber ate
    # o cano mais longo (sniper).
    color = tower_color(tower.level)
    spec = TOWER_TYPES[tower.ttype]
    icon_cy = back_rect.bottom + 26
    draw_tower_shape(surf, area.x + 26, icon_cy, tower.ttype, tower.level,
                      angle=math.pi / 2, radius=14, show_level=False)
    font_h = get_font(15, bold=True)
    header = font_h.render(spec["label"], True, COL_WHITE)
    surf.blit(header, (area.x + 54, back_rect.bottom + 10))
    font_sub = get_font(12)
    sub = font_sub.render(f"{tower_name(tower.level)} (Nv.{tower.level})", True, color)
    surf.blit(sub, (area.x + 54, back_rect.bottom + 30))

    font_lbl = get_font(13, bold=True)
    font_val = get_font(11)
    for rect, aspect in rects:
        pts = tower.upgrades[aspect]
        cost = int(round(tower.upgrade_cost(aspect) * game.meta.upgrade_cost_mult()))
        cost = max(1, cost)
        affordable = game.gold >= cost
        hovered = rect.collidepoint(game.mouse_pos)

        base_fill = (30, 40, 34) if affordable else (30, 30, 34)
        if hovered and affordable:
            base_fill = theme.shade(base_fill, 0.15)
        border_col = COL_GREEN if affordable else (80, 80, 86)
        theme.draw_panel(surf, rect, base_fill, border=border_col, radius=8,
                          border_w=2 if not hovered else 3, shadow=False)

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
    """Enquanto uma torre esta sendo arrastada do painel, desenha a torre
    de verdade (nao um icone generico da forma) seguindo o mouse -- o
    alcance/preview real da torre ja e desenhado por
    menus.draw_tower_range_hover-like logic em game.py, aqui e so o
    corpo da torre, no mesmo nivel com que ela vai nascer ao ser solta."""
    ttype = game.dragging_from_panel
    if ttype is None:
        return
    start_level = 1 + int(game.meta.start_tower_level_bonus())
    mx, my = game.mouse_pos
    draw_tower_shape(surf, mx, my, ttype, start_level, show_level=False)
