"""Painel lateral fixo de torres (estilo Bloons TD).

Fica sobreposto na frente do grid, do lado direito da tela, e pode
abrir/fechar deslizando (sem redimensionar o grid). Tem dois "modos"
de conteudo:

- Modo LOJA (game.selected_tower() is None): mostra um card
  por tipo de torre, arrastavel ate a grade para comprar. Dois
  cliques rapidos no mesmo card tambem compram, colocando a torre
  automaticamente na primeira celula vazia disponivel.
- Modo UPGRADE (game.selected_tower() retorna uma torre): mostra os
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
    TOWER_TYPES, TOWER_TYPE_KEYS,
    COL_WHITE, COL_RED, COL_GOLD, COL_GEM, COL_GREEN, COL_TEXT_DIM, COL_PANEL,
    COL_GRID_BORDER, TOWER_SELL_REFUND_RATIO,
)
from ..fonts import get_font
from ..entities.tower import tower_color, tower_name, draw_tower_shape
from .. import upgrades as up
from . import theme


# altura de cada card de caminho no modo upgrade
PATH_CARD_H = 122
PATH_CARD_GAP = 9


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


def upgrade_header_h():
    """Altura reservada para o botao voltar + cabecalho da torre."""
    return 12 + 30 + 74


def upgrade_button_rects(panel_x):
    """Retorna (rects, back_rect, sell_rect) para o modo de upgrade dentro
    do painel.

    `rects` e uma lista de (rect, path_index) -- um card por CAMINHO da
    arvore de upgrades (ver towerdefense/upgrades.py). Substituiu os tres
    botoes fixos de dano/alcance/cadencia da versao antiga.

    `back_rect` e `sell_rect` dividem a mesma linha do topo (voltar pra
    loja / vender a torre), lado a lado, pra nao precisar abrir espaco
    novo no painel nem empurrar os cards de caminho pra baixo --
    `upgrade_header_h()` continua valendo sem alteracao.
    """
    area = panel_area_rect()
    area.x = panel_x
    w = area.w - 24
    gap = 8
    back_w = int(w * 0.58)
    back_rect = pygame.Rect(area.x + 12, area.y + 12, back_w, 30)
    sell_rect = pygame.Rect(back_rect.right + gap, area.y + 12,
                             w - back_w - gap, 30)
    start_y = area.y + upgrade_header_h()
    rects = []
    for i in range(3):
        r = pygame.Rect(area.x + 12, start_y + i * (PATH_CARD_H + PATH_CARD_GAP),
                        w, PATH_CARD_H)
        rects.append((r, i))
    return rects, back_rect, sell_rect


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

        # game.selected_tower() (e nao selected_tower_cell cru) e o que
        # decide o modo -- o tratamento de clique em game.py chama a MESMA
        # funcao, entao desenho e clique nunca discordam sobre qual modo o
        # painel esta mostrando.
        if game.selected_tower() is not None:
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


def _wrap(font, text, max_w, max_lines=2):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if font.size(test)[0] > max_w and cur:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
        else:
            cur = test
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines


def _draw_tier_pips(surf, x, y, tier, color, size=9, gap=3):
    """Seis quadradinhos mostrando o progresso do caminho (tier 0..6)."""
    for i in range(up.MAX_TIER):
        rect = pygame.Rect(x + i * (size + gap), y, size, size)
        if i < tier:
            fill = color if i < up.MAX_TIER - 1 else (255, 225, 120)
            pygame.draw.rect(surf, fill, rect, border_radius=2)
        else:
            pygame.draw.rect(surf, (52, 58, 70), rect, border_radius=2)
            pygame.draw.rect(surf, (72, 78, 92), rect, 1, border_radius=2)


def _draw_upgrade_mode(game, surf, panel_x):
    tower = game.selected_tower()
    if tower is None:
        return
    rects, back_rect, sell_rect = upgrade_button_rects(panel_x)
    area = panel_area_rect()
    area.x = panel_x

    # botao "voltar" (fecha o modo upgrade, volta pra loja)
    back_hovered = back_rect.collidepoint(game.mouse_pos)
    theme.draw_panel(surf, back_rect, (44, 32, 32) if not back_hovered else (60, 38, 38),
                      border=COL_RED, radius=6, shadow=False)
    font_back = get_font(13, bold=True)
    back_txt = font_back.render("< Voltar", True, COL_WHITE)
    surf.blit(back_txt, back_txt.get_rect(center=back_rect.center))

    # botao "vender": devolve TOWER_SELL_REFUND_RATIO do ouro investido
    # (compra + upgrades de caminho + o que veio de merges, ver
    # Tower.invested / Game.sell_tower) -- mostra o valor de venda direto
    # no botao pra nao precisar abrir outro menu pra saber quanto volta.
    refund = int(round(tower.invested * TOWER_SELL_REFUND_RATIO))
    sell_hovered = sell_rect.collidepoint(game.mouse_pos)
    theme.draw_panel(surf, sell_rect, (28, 40, 30) if not sell_hovered else (36, 52, 38),
                      border=COL_GREEN, radius=6, shadow=False)
    font_sell = get_font(12, bold=True)
    sell_txt = font_sell.render(f"Vender {refund}g", True, COL_WHITE)
    surf.blit(sell_txt, sell_txt.get_rect(center=sell_rect.center))

    # cabecalho: torre de verdade (com cano apontando pra baixo, que e a
    # direcao com mais espaco livre aqui), nome da especializacao e a
    # configuracao em notacao BTD (ex.: "4-2-0")
    color = tower.color()
    spec = TOWER_TYPES[tower.ttype]
    icon_cy = back_rect.bottom + 28
    draw_tower_shape(surf, area.x + 28, icon_cy, tower.ttype, tower.level,
                      angle=math.pi / 2, radius=14, show_level=False, tiers=tower.tiers)
    font_h = get_font(15, bold=True)
    header = font_h.render(tower.display_name(), True, COL_WHITE)
    surf.blit(header, (area.x + 58, back_rect.bottom + 8))
    font_sub = get_font(12)
    conf = "-".join(str(t) for t in tower.tiers)
    sub = font_sub.render(f"{spec['label']} - Nv.{tower.level}  [{conf}]", True, color)
    surf.blit(sub, (area.x + 58, back_rect.bottom + 28))
    stats = font_sub.render(
        f"{tower.damage:0.0f} dmg | {tower.range:0.0f} alc | {1/tower.fire_rate:0.1f}/s",
        True, COL_TEXT_DIM)
    surf.blit(stats, (area.x + 58, back_rect.bottom + 46))

    font_path = get_font(13, bold=True)
    font_name = get_font(13, bold=True)
    font_desc = get_font(11)
    font_cost = get_font(12, bold=True)

    for rect, path_index in rects:
        pdef = up.path_def(tower.ttype, path_index)
        pcolor = up.PATH_COLORS[tower.ttype][path_index]
        tier = tower.tiers[path_index]
        ok, cost, reason = game.path_purchase_state(tower, path_index)
        hovered = rect.collidepoint(game.mouse_pos)
        maxed = tier >= up.MAX_TIER

        if maxed:
            fill, border = (46, 40, 24), (255, 225, 120)
        elif ok:
            fill = theme.shade(pcolor, -0.80 if not hovered else -0.70)
            border = pcolor
        else:
            fill, border = (28, 30, 36), (72, 76, 86)
        theme.draw_panel(surf, rect, fill, border=border, radius=8,
                          border_w=3 if (hovered and ok) else 2, shadow=False)

        # linha 1: nome do caminho + tier atual
        name_col = COL_WHITE if (ok or maxed) else COL_TEXT_DIM
        surf.blit(font_path.render(pdef["name"], True, name_col), (rect.x + 10, rect.y + 7))
        tier_txt = font_cost.render(f"{tier}/{up.MAX_TIER}", True, pcolor)
        trect = tier_txt.get_rect()
        trect.topright = (rect.right - 10, rect.y + 7)
        surf.blit(tier_txt, trect)

        _draw_tier_pips(surf, rect.x + 10, rect.y + 27, tier, pcolor)
        surf.blit(font_desc.render(pdef["short"], True, COL_TEXT_DIM),
                  (rect.x + 10 + 6 * 12 + 8, rect.y + 27))

        # linha 2: proximo upgrade (nome + descricao) ou "concluido"
        if maxed:
            ab = up.ability_def(tower.ttype, path_index)
            surf.blit(font_name.render(f"TIER 6 - {ab['name']}", True, (255, 225, 120)),
                      (rect.x + 10, rect.y + 46))
            for i, line in enumerate(_wrap(font_desc, ab["desc"], rect.w - 20, 3)):
                surf.blit(font_desc.render(line, True, COL_TEXT_DIM),
                          (rect.x + 10, rect.y + 64 + i * 14))
            # estado da habilidade automatica
            if tower.ability_active > 0:
                st, stc = "HABILIDADE ATIVA", (255, 255, 160)
            elif tower.ability_cd <= 0:
                st, stc = "Pronta - a IA escolhe a hora", (140, 255, 170)
            else:
                st, stc = f"Recarregando: {tower.ability_cd:0.1f}s", COL_TEXT_DIM
            surf.blit(font_cost.render(st, True, stc), (rect.x + 10, rect.bottom - 20))
            continue

        nxt = up.tier_def(tower.ttype, path_index, tier + 1)
        surf.blit(font_name.render(f"{tier + 1}. {nxt['name']}", True, name_col),
                  (rect.x + 10, rect.y + 46))
        for i, line in enumerate(_wrap(font_desc, nxt["desc"], rect.w - 20, 2)):
            surf.blit(font_desc.render(line, True, COL_TEXT_DIM),
                      (rect.x + 10, rect.y + 64 + i * 14))

        # linha 3: custo (ou o motivo do bloqueio). Tier 6 tambem cobra
        # gemas -- mostra os dois precos juntos quando for o caso.
        gem_cost = game.path_upgrade_gem_cost(tower, path_index)
        gem_part = f" + {gem_cost} gemas" if gem_cost else ""
        if cost is None:
            info, icol = reason, COL_TEXT_DIM
        elif ok:
            info, icol = f"{cost}g{gem_part}", COL_GOLD if not gem_part else COL_GEM
        else:
            info, icol = f"{cost}g{gem_part} - {reason}", COL_TEXT_DIM
        surf.blit(font_cost.render(info, True, icol), (rect.x + 10, rect.bottom - 20))


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
