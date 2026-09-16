"""Menus flutuantes: loja de gemas (meta-upgrades) e o tooltip de
alcance ao passar o mouse.

(O menu de compra de torre nova e o menu de melhorias por torre agora
vivem no painel lateral fixo, ver ui/tower_panel.py.)

As funcoes *_rects() calculam apenas geometria (pygame.Rect) e sao usadas
tanto para desenhar quanto para testar cliques em game.py. As funcoes
draw_*() fazem o desenho propriamente dito.
"""

import math
import pygame

from ..config import (
    WIDTH, HEIGHT, TOP_HUD_HEIGHT,
    TOWER_TYPES, META_UPGRADE_DEFS, META_UPGRADE_KEYS,
    COL_GEM, COL_WHITE, COL_RED, COL_GOLD, COL_GREEN,
    COL_TEXT_DIM,
)
from ..fonts import get_font
from ..entities.tower import tower_color
from .hud import draw_gem_icon
from . import theme


# ----------------------------------------------------------------------
# GEOMETRIA (usada tanto para desenhar quanto para testar cliques)
# ----------------------------------------------------------------------
def meta_shop_rects():
    """Retorna (rects, close_rect, panel_rect) para os botoes do shop de
    gemas, organizados em um painel central."""
    cols = 2
    card_w, card_h = 320, 118
    gap_x, gap_y = 18, 18
    n = len(META_UPGRADE_KEYS)
    rows = math.ceil(n / cols)
    total_w = cols * card_w + (cols - 1) * gap_x
    total_h = rows * card_h + (rows - 1) * gap_y
    start_x = (WIDTH - total_w) // 2
    start_y = TOP_HUD_HEIGHT + 88
    rects = []
    for i, key in enumerate(META_UPGRADE_KEYS):
        col = i % cols
        row = i // cols
        x = start_x + col * (card_w + gap_x)
        y = start_y + row * (card_h + gap_y)
        rects.append((pygame.Rect(x, y, card_w, card_h), key))
    panel_rect = pygame.Rect(start_x - 24, start_y - 78, total_w + 48, total_h + 102)
    close_rect = pygame.Rect(panel_rect.right - 40, panel_rect.y + 14, 26, 26)
    return rects, close_rect, panel_rect


# ----------------------------------------------------------------------
# DESENHO
# ----------------------------------------------------------------------
def draw_tower_range_hover(game, surf, offset):
    """Mostra alcance da torre sob o mouse (quando nao arrastando)."""
    if game.dragging_tower is not None:
        return
    cell = game.hovered_cell
    if cell is None or cell not in game.towers:
        return
    t = game.towers[cell]
    gx, gy = t.grid_pos()
    color = t.color()
    range_surf = pygame.Surface((t.range * 2, t.range * 2), pygame.SRCALPHA)
    pygame.draw.circle(range_surf, (*color, 35), (t.range, t.range), t.range)
    pygame.draw.circle(range_surf, (*color, 110), (t.range, t.range), t.range, 2)
    if t.aura_radius > 0:
        # a aura tem raio proprio (mod `aura_radius_mult`), quase sempre
        # diferente do alcance de tiro -- mostrar so o alcance enganaria
        r = int(t.aura_radius)
        pygame.draw.circle(range_surf, (*color, 60), (t.range, t.range), r, 3)
    surf.blit(range_surf, (gx - t.range, gy - t.range))

    # tooltip com stats
    font = get_font(15, bold=True)
    font2 = get_font(13)
    conf = "-".join(str(x) for x in t.tiers)
    lines = [
        f"{t.display_name()} [{conf}]",
        f"Nv.{t.level} - Dano {t.damage:0.0f} | Alcance {t.range:0.0f}",
        f"Cadencia: {1/t.fire_rate:0.1f}/s" + (f" x{t.shots}" if t.shots > 1 else ""),
    ]
    if t.splash > 0:
        lines.append(f"Splash: {t.splash:0.0f}px")
    if t.effects.get("pierce"):
        lines.append(f"Perfura {t.effects['pierce']} inimigos")
    if t.slow:
        lines.append(f"Lentidao: {int((1-t.slow[0])*100)}%")
    if t.effects.get("freeze_chance"):
        lines.append(f"Congela: {int(t.effects['freeze_chance']*100)}%")
    if t.effects.get("heavy_mult", 1.0) > 1.0:
        lines.append(f"Vs pesados: x{t.effects['heavy_mult']:0.1f}")
    if t.effects.get("crit_chance"):
        lines.append(f"Critico: {int(t.effects['crit_chance']*100)}% (x{t.effects['crit_mult']:0.1f})")
    if t.effects.get("mark_on_hit"):
        lines.append(f"Marca alvos: +{int(t.effects['mark_amp']*100)}% dano")
    if t.aura_radius > 0:
        lines.append("Aura ativa ao redor da torre")
    if t.armor_pierce:
        lines.append("Ignora armadura")
    if t.has_ability:
        lines.append(f"HABILIDADE: {t.ability()['name']}")
    pad = 8
    icon_w = 26
    w = max(font.size(l)[0] for l in lines) + pad * 2 + icon_w
    h = 20 * len(lines) + pad
    tx = min(WIDTH - w - 10, gx + 20)
    # nunca deixar o tooltip nascer por baixo do HUD superior (torres da
    # primeira fileira do grid ficam bem perto do topo da tela)
    ty = max(TOP_HUD_HEIGHT + 6, gy - h - 20)
    box_rect = pygame.Rect(tx, ty, w, h)
    theme.draw_panel(surf, box_rect, (20, 24, 32), border=color, radius=6, border_w=2)
    tower_shape = TOWER_TYPES[t.ttype]["tower_shape"]
    theme.draw_shape_icon(surf, tx + pad + 10, ty + h // 2, 12, tower_shape, color)
    for i, line in enumerate(lines):
        fnt = font if i == 0 else font2
        t_surf = fnt.render(line, True, COL_WHITE if i == 0 else COL_TEXT_DIM)
        surf.blit(t_surf, (tx + pad + icon_w, ty + pad // 2 + i * 20))


def draw_meta_shop(game, surf):
    if not game.meta_shop_open:
        return
    rects, close_rect, panel_rect = meta_shop_rects()

    # fundo escurecido cobrindo o jogo, para focar no shop
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 165))
    surf.blit(overlay, (0, 0))

    theme.draw_panel(surf, panel_rect, (20, 24, 34), border=COL_GEM, radius=14, border_w=3)

    # cabecalho
    font_title = get_font(24, bold=True)
    title_txt = font_title.render("Loja de Gemas - Melhorias Permanentes", True, COL_GEM)
    trect = title_txt.get_rect(center=(panel_rect.centerx, panel_rect.y + 22))
    surf.blit(title_txt, trect)

    font_sub = get_font(13)
    gem_amount = font_sub.render(f"Voce tem {game.gems} gemas", True, COL_GEM)
    arect = gem_amount.get_rect(center=(panel_rect.centerx, panel_rect.y + 44))
    draw_gem_icon(surf, arect.x - 12, arect.centery, 7)
    surf.blit(gem_amount, arect)

    sub_txt = font_sub.render(
        "Gemas sao ganhas derrotando BOSSES (a cada 10 ondas) e persistem entre partidas.",
        True, COL_TEXT_DIM)
    srect = sub_txt.get_rect(center=(panel_rect.centerx, panel_rect.y + 62))
    surf.blit(sub_txt, srect)

    # botao fechar
    close_hovered = close_rect.collidepoint(game.mouse_pos)
    theme.draw_panel(surf, close_rect, (60, 40, 40) if not close_hovered else (90, 50, 50),
                      border=COL_RED, radius=6, border_w=1, shadow=False)
    font_x = get_font(16, bold=True)
    x_txt = font_x.render("X", True, COL_WHITE)
    surf.blit(x_txt, x_txt.get_rect(center=close_rect.center))

    # cards de cada melhoria
    font_lbl = get_font(15, bold=True)
    font_desc = get_font(11)
    font_val = get_font(12, bold=True)
    for rect, key in rects:
        spec = META_UPGRADE_DEFS[key]
        lvl = game.meta.level(key)
        max_lvl = spec["max_level"]  # None == sem teto (upgrade infinito)
        cost = game.meta.cost_for_next(key)
        maxed = cost is None
        affordable = (not maxed) and game.gems >= cost
        hovered = rect.collidepoint(game.mouse_pos)

        base_fill = (30, 40, 34) if affordable else (26, 28, 34)
        if hovered and affordable:
            base_fill = theme.shade(base_fill, 0.12)
        border_col = COL_GEM if affordable else ((90, 90, 60) if maxed else (70, 70, 78))
        theme.draw_panel(surf, rect, base_fill, border=border_col, radius=10,
                          border_w=2 if not (hovered and affordable) else 3, shadow=False)

        draw_gem_icon(surf, rect.x + 20, rect.y + 22, 9)

        lbl = font_lbl.render(spec["label"], True, COL_WHITE)
        surf.blit(lbl, (rect.x + 36, rect.y + 10))

        lvl_label = f"Nv {lvl}/{max_lvl}" if max_lvl is not None else f"Nv {lvl}"
        lvl_txt = font_val.render(lvl_label, True, COL_TEXT_DIM)
        lrect = lvl_txt.get_rect()
        lrect.topright = (rect.right - 12, rect.y + 12)
        surf.blit(lvl_txt, lrect)

        desc_txt = font_desc.render(spec["desc"], True, COL_TEXT_DIM)
        surf.blit(desc_txt, (rect.x + 14, rect.y + 40))

        # barra de progresso do nivel (upgrades sem teto mostram a chance
        # atual em vez de "nivel/maximo", que nao existe pra eles)
        bar_x, bar_y = rect.x + 14, rect.y + 62
        bar_w, bar_h = rect.w - 28, 8
        pygame.draw.rect(surf, (15, 18, 24), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        if key == "extra_lives":
            pct = game.meta.second_chance_prob() / 1.0  # ja e 0..1
        else:
            pct = lvl / max_lvl if max_lvl else 0
        if pct > 0:
            fill_w = max(bar_h, bar_w * pct) if pct > 0 else 0
            pygame.draw.rect(surf, COL_GEM, (bar_x, bar_y, fill_w, bar_h), border_radius=4)

        # custo / status
        if key == "extra_lives":
            pct_txt = font_val.render(f"Chance atual: {game.meta.second_chance_prob() * 100:0.1f}%",
                                       True, COL_GEM)
            prect = pct_txt.get_rect()
            prect.topleft = (bar_x, bar_y + bar_h + 3)
            surf.blit(pct_txt, prect)
        if maxed:
            cost_txt = font_val.render("NIVEL MAXIMO", True, (255, 220, 90))
        else:
            cost_col = COL_GEM if affordable else COL_TEXT_DIM
            cost_txt = font_val.render(f"Custo: {cost} gemas", True, cost_col)
        crect = cost_txt.get_rect()
        crect.bottomleft = (rect.x + 14, rect.bottom - 8)
        surf.blit(cost_txt, crect)

    # dica no rodape
    font_hint = get_font(12)
    hint_txt = font_hint.render("Clique numa melhoria para compra-la. Pressione G ou X para fechar.", True, COL_TEXT_DIM)
    hrect = hint_txt.get_rect(center=(panel_rect.centerx, panel_rect.bottom - 14))
    surf.blit(hint_txt, hrect)
