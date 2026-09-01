"""Menu principal (tela de titulo), exibido antes do menu de selecao de
mapa. E o primeiro estado do jogo (game.state == "main_menu").

Segue o mesmo padrao dos outros menus deste pacote: as funcoes *_rects()
so calculam geometria (usada tanto para desenhar quanto para testar
cliques em game.py) e draw_*() cuida do desenho.
"""

import pygame

from ..config import (
    WIDTH, HEIGHT, COL_BG, COL_PANEL, COL_GRID_BORDER, COL_WHITE,
    COL_TEXT, COL_TEXT_DIM, COL_GOLD, COL_GEM, COL_RED, COL_GREEN,
)
from ..fonts import get_font
from .hud import draw_gem_icon

# cada item: (label, action). "action" e o que game.py usa para decidir
# o que fazer no clique (ver handle_main_menu_click).
MENU_BUTTONS = [
    ("Jogar", "play"),
    ("Como Jogar", "help"),
    ("Sair", "quit"),
]


def button_rects():
    """Retorna lista de (rect, action) para os botoes do menu, empilhados
    verticalmente e centralizados na tela."""
    w, h = 340, 60
    gap = 22
    n = len(MENU_BUTTONS)
    total_h = n * h + (n - 1) * gap
    start_y = HEIGHT // 2 - total_h // 2 + 40
    x = WIDTH // 2 - w // 2
    rects = []
    for i, (label, action) in enumerate(MENU_BUTTONS):
        y = start_y + i * (h + gap)
        rects.append((pygame.Rect(x, y, w, h), action))
    return rects


def help_close_rect():
    """Rect do botao de fechar (X) do painel 'Como Jogar'."""
    panel = help_panel_rect()
    return pygame.Rect(panel.right - 44, panel.y + 14, 30, 30)


def help_panel_rect():
    w, h = 760, 560
    return pygame.Rect((WIDTH - w) // 2, (HEIGHT - h) // 2, w, h)


# ----------------------------------------------------------------------
# DESENHO
# ----------------------------------------------------------------------
def _draw_decorative_towers(surf):
    """Pequena decoracao abstrata no fundo: circulos remetendo a torres e
    alcance, so para a tela de titulo nao ficar totalmente vazia."""
    import math
    decos = [
        (140, 620, (110, 190, 255), 46),
        (WIDTH - 160, 660, (255, 140, 70), 58),
        (WIDTH - 260, 150, (230, 90, 220), 40),
        (200, 140, (140, 230, 120), 34),
    ]
    for cx, cy, color, r in decos:
        ring = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(ring, (*color, 30), (r, r), r)
        pygame.draw.circle(ring, (*color, 130), (r, r), r, 2)
        surf.blit(ring, (cx - r, cy - r))
        pygame.draw.circle(surf, color, (cx, cy), 8)


def draw_main_menu(game, surf):
    surf.fill(COL_BG)
    _draw_decorative_towers(surf)

    font_title = get_font(50, bold=True)
    font_subtitle = get_font(18)

    title_txt = font_title.render("TOWER DEFENSE INFINITO", True, COL_WHITE)
    trect = title_txt.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 210))
    surf.blit(title_txt, trect)

    sub_txt = font_subtitle.render("Merge das Torres", True, COL_GOLD)
    srect = sub_txt.get_rect(center=(WIDTH // 2, trect.bottom + 12))
    surf.blit(sub_txt, srect)

    mouse_pos = game.mouse_pos
    font_btn = get_font(22, bold=True)
    for rect, action in button_rects():
        hovered = rect.collidepoint(mouse_pos)
        bg = (40, 48, 62) if hovered else COL_PANEL
        pygame.draw.rect(surf, bg, rect, border_radius=12)
        border_col = COL_GOLD if hovered else COL_GRID_BORDER
        pygame.draw.rect(surf, border_col, rect, 2, border_radius=12)
        label = next(lbl for lbl, act in MENU_BUTTONS if act == action)
        txt = font_btn.render(label, True, COL_WHITE if hovered else COL_TEXT)
        surf.blit(txt, txt.get_rect(center=rect.center))

    # progresso permanente (gemas), visivel desde o menu principal porque
    # persiste entre partidas (ver Game.__init__: self.gems nao e resetado)
    font_small = get_font(14)
    gem_y = button_rects()[-1][0].bottom + 34
    gem_txt = font_small.render(f"{game.gems} gemas guardadas", True, COL_GEM)
    grect = gem_txt.get_rect(center=(WIDTH // 2 + 10, gem_y))
    draw_gem_icon(surf, grect.x - 14, grect.centery, 8)
    surf.blit(gem_txt, grect)

    if game.total_bosses_killed > 0:
        boss_txt = font_small.render(
            f"{game.total_bosses_killed} bosses derrotados nesta sessao", True, COL_TEXT_DIM)
        brect = boss_txt.get_rect(center=(WIDTH // 2, gem_y + 22))
        surf.blit(boss_txt, brect)

    hint_txt = font_small.render("ESC a qualquer momento para sair", True, COL_TEXT_DIM)
    hrect = hint_txt.get_rect(center=(WIDTH // 2, HEIGHT - 30))
    surf.blit(hint_txt, hrect)

    if game.show_help:
        draw_help_overlay(surf, mouse_pos)


def draw_help_overlay(surf, mouse_pos):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 175))
    surf.blit(overlay, (0, 0))

    panel_rect = help_panel_rect()
    panel = pygame.Surface((panel_rect.w, panel_rect.h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (20, 24, 34, 250), (0, 0, panel_rect.w, panel_rect.h), border_radius=16)
    pygame.draw.rect(panel, (*COL_GOLD, 255), (0, 0, panel_rect.w, panel_rect.h), 3, border_radius=16)
    surf.blit(panel, panel_rect.topleft)

    font_title = get_font(24, bold=True)
    title_txt = font_title.render("Como Jogar", True, COL_GOLD)
    surf.blit(title_txt, (panel_rect.x + 28, panel_rect.y + 20))

    close_rect = help_close_rect()
    hovered = close_rect.collidepoint(mouse_pos)
    pygame.draw.rect(surf, (60, 40, 40) if not hovered else (90, 50, 50), close_rect, border_radius=8)
    pygame.draw.rect(surf, COL_RED, close_rect, 1, border_radius=8)
    font_x = get_font(16, bold=True)
    x_txt = font_x.render("X", True, COL_WHITE)
    surf.blit(x_txt, x_txt.get_rect(center=close_rect.center))

    font_h = get_font(15, bold=True)
    font_p = get_font(13)
    y = panel_rect.y + 62
    x = panel_rect.x + 28
    max_w = panel_rect.w - 56

    def wrap(text, font, width):
        words = text.split(" ")
        lines, cur = [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if font.size(test)[0] > width:
                lines.append(cur)
                cur = w
            else:
                cur = test
        if cur:
            lines.append(cur)
        return lines

    sections = [
        ("Objetivo", [
            "Impeca que os inimigos cheguem ao fim do caminho, construindo e "
            "melhorando torres. As ondas sao infinitas e ficam mais dificeis "
            "com o tempo - sobreviva o maximo que conseguir.",
        ]),
        ("Construir e fundir torres", [
            "Clique num slot vazio da grade para escolher e comprar um tipo de torre.",
            "Arraste uma torre sobre OUTRA do mesmo tipo para fazer merge: se tiverem "
            "o mesmo nivel, o resultado sobe um nivel (nao ha nivel maximo).",
            "Clique rapido (sem arrastar) numa torre para abrir o menu de melhorias "
            "e gastar ouro em Dano, Alcance ou Cadencia daquela torre.",
        ]),
        ("Ondas e bosses", [
            "Pressione ESPACO para iniciar a proxima onda manualmente, ou espere o "
            "inicio automatico. Pressione N para pular a onda atual e ganhar ouro extra.",
            "A cada 10 ondas aparece um boss, que solta gemas ao morrer.",
        ]),
        ("Progressao permanente", [
            "Pressione G durante a partida para abrir a loja de gemas: melhorias "
            "permanentes que persistem entre partidas (ouro inicial, vidas, "
            "descontos e mais).",
        ]),
        ("Controles", [
            "Mouse: comprar/arrastar/soltar torres, pular onda, abrir loja.  "
            "ESPACO: proxima onda.  N: pular onda.  G: loja de gemas.  "
            "P: pausar.  M: trocar de mapa.  R: reiniciar apos game over.",
        ]),
    ]

    for heading, paragraphs in sections:
        h_txt = font_h.render(heading, True, COL_WHITE)
        surf.blit(h_txt, (x, y))
        y += 22
        for para in paragraphs:
            for line in wrap(para, font_p, max_w):
                l_txt = font_p.render(line, True, COL_TEXT_DIM)
                surf.blit(l_txt, (x, y))
                y += 18
            y += 6
        y += 6
