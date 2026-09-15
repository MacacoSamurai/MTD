"""Menu principal (tela de titulo), exibido antes do menu de selecao de
mapa. E o primeiro estado do jogo (game.state == "main_menu").

Segue o mesmo padrao dos outros menus deste pacote: as funcoes *_rects()
so calculam geometria (usada tanto para desenhar quanto para testar
cliques em game.py) e draw_*() cuida do desenho.
"""

import math
import pygame

from ..config import (
    WIDTH, HEIGHT, COL_BG, COL_PANEL, COL_GRID_BORDER, COL_WHITE,
    COL_TEXT, COL_TEXT_DIM, COL_GOLD, COL_GEM, COL_RED, COL_GREEN,
)
from ..fonts import get_font
from .hud import draw_gem_icon
from . import theme

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
    w, h = 360, 62
    gap = 20
    n = len(MENU_BUTTONS)
    total_h = n * h + (n - 1) * gap
    start_y = HEIGHT // 2 - total_h // 2 + 50
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


# ----------------------------------------------------------------------
# CONTEUDO DO "COMO JOGAR"
# Fica no nivel do modulo (e nao dentro de draw_help_overlay) porque a
# ALTURA do painel e calculada a partir dele: o texto cresceu quando a
# arvore de caminhos entrou no jogo e passou a vazar por baixo da borda
# de um painel de altura fixa. Agora geometria e desenho leem a mesma
# fonte de verdade.
# ----------------------------------------------------------------------
HELP_SECTIONS = [
    ("Objetivo", [
        "Impeca que os inimigos cheguem ao fim do caminho, construindo e "
        "melhorando torres. As ondas sao infinitas e ficam mais dificeis "
        "com o tempo - sobreviva o maximo que conseguir.",
    ]),
    ("Construir e fundir torres", [
        "Clique num slot vazio da grade para escolher e comprar um tipo de torre.",
        "Arraste uma torre sobre OUTRA do mesmo tipo para fazer merge: se tiverem "
        "o mesmo nivel, o resultado sobe um nivel (nao ha nivel maximo).",
    ]),
    ("Caminhos de evolucao (3 x 6)", [
        "Clique rapido numa torre para abrir a arvore dela: cada torre tem 3 "
        "caminhos de 6 tiers, com identidades bem diferentes.",
        "Regra de crosspath: so da pra abrir DOIS caminhos, e apenas UM deles "
        "pode passar do tier 2 - o outro trava ali. Escolha bem a especializacao.",
        "O tier 6 e a super torre: ganha uma habilidade poderosa que a IA dispara "
        "sozinha na melhor hora. So pode existir UMA torre tier 6 de cada TIPO "
        "na partida (no maximo 5 no total, uma de cada tipo).",
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


def _help_wrap(text, font, width):
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


def _help_content_height(max_w):
    font_h = get_font(15, bold=True)
    font_p = get_font(13)
    h = 0
    for heading, paragraphs in HELP_SECTIONS:
        h += 22
        for para in paragraphs:
            h += 18 * len(_help_wrap(para, font_p, max_w))
            h += 6
    return h


def help_panel_rect():
    """Painel do 'Como Jogar'. A altura acompanha o texto (com um teto
    pra nunca passar da janela) -- ver comentario em HELP_SECTIONS."""
    w = 820
    h = min(HEIGHT - 40, 86 + _help_content_height(w - 56))
    return pygame.Rect((WIDTH - w) // 2, (HEIGHT - h) // 2, w, h)


# ----------------------------------------------------------------------
# DESENHO
# ----------------------------------------------------------------------
def _draw_background(surf):
    """Fundo com vinheta radial suave (mais claro no centro-topo, mais
    escuro nas bordas) em vez de uma cor solida chapada, mais um
    quadriculado bem discreto lembrando a grade do jogo."""
    theme.vertical_gradient(surf, (0, 0, WIDTH, HEIGHT),
                             theme.shade(COL_BG, 0.10), theme.shade(COL_BG, -0.35))

    # quadriculado discreto (mesma escala da grade de jogo) so pra dar
    # textura, bem apagado para nao competir com o texto
    grid_col = (*theme.shade(COL_BG, 0.22), 60)
    grid_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    step = 72
    for x in range(0, WIDTH, step):
        pygame.draw.line(grid_surf, grid_col, (x, 0), (x, HEIGHT), 1)
    for y in range(0, HEIGHT, step):
        pygame.draw.line(grid_surf, grid_col, (0, y), (WIDTH, y), 1)
    surf.blit(grid_surf, (0, 0))


def _draw_decorative_towers(surf):
    """Pequena decoracao abstrata no fundo: circulos remetendo a torres e
    alcance, so para a tela de titulo nao ficar totalmente vazia."""
    decos = [
        (140, 620, (110, 190, 255), 46),
        (WIDTH - 160, 660, (255, 140, 70), 58),
        (WIDTH - 260, 150, (230, 90, 220), 40),
        (200, 140, (140, 230, 120), 34),
    ]
    for cx, cy, color, r in decos:
        ring = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(ring, (*color, 26), (r, r), r)
        pygame.draw.circle(ring, (*color, 130), (r, r), r, 2)
        surf.blit(ring, (cx - r, cy - r))
        pygame.draw.circle(surf, theme.shade(color, -0.3), (cx, cy + 2), 9)
        pygame.draw.circle(surf, color, (cx, cy), 8)


def draw_main_menu(game, surf):
    _draw_background(surf)
    _draw_decorative_towers(surf)

    font_title = get_font(52, bold=True)
    font_subtitle = get_font(18, bold=True)

    title_center = (WIDTH // 2, HEIGHT // 2 - 210)
    # sombra/glow do titulo: varias copias deslocadas em tom escuro atras
    # do texto branco, pra dar profundidade sem precisar de fonte custom
    shadow_txt = font_title.render("TOWER DEFENSE INFINITO", True, (0, 0, 0))
    for dx, dy in ((3, 3), (0, 4)):
        srect = shadow_txt.get_rect(center=(title_center[0] + dx, title_center[1] + dy))
        surf.blit(shadow_txt, srect)
    title_txt = font_title.render("TOWER DEFENSE INFINITO", True, COL_WHITE)
    trect = title_txt.get_rect(center=title_center)
    surf.blit(title_txt, trect)
    underline_y = trect.bottom + 4
    pygame.draw.line(surf, COL_GOLD, (trect.centerx - 140, underline_y),
                      (trect.centerx + 140, underline_y), 3)

    sub_txt = font_subtitle.render("MERGE DAS TORRES", True, COL_GOLD)
    srect = sub_txt.get_rect(center=(WIDTH // 2, underline_y + 22))
    surf.blit(sub_txt, srect)

    mouse_pos = game.mouse_pos
    font_btn = get_font(23, bold=True)
    for rect, action in button_rects():
        hovered = rect.collidepoint(mouse_pos)
        label = next(lbl for lbl, act in MENU_BUTTONS if act == action)
        col = COL_RED if action == "quit" else COL_GOLD
        base_fill = COL_PANEL if not hovered else theme.shade(COL_PANEL, 0.12)
        theme.draw_panel(surf, rect, base_fill, border=col if hovered else COL_GRID_BORDER,
                          radius=12, border_w=2 if not hovered else 3)
        txt = font_btn.render(label, True, COL_WHITE if hovered else COL_TEXT)
        surf.blit(txt, txt.get_rect(center=rect.center))
        if hovered:
            # pequena seta indicando o item ativo, reforca o hover alem da borda
            tip = [(rect.x + 18, rect.centery - 7), (rect.x + 18, rect.centery + 7), (rect.x + 30, rect.centery)]
            pygame.draw.polygon(surf, col, tip)

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
    theme.draw_panel(surf, panel_rect, (20, 24, 34), border=COL_GOLD, radius=16, border_w=3)

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
    for heading, paragraphs in HELP_SECTIONS:
        h_txt = font_h.render(heading, True, COL_WHITE)
        surf.blit(h_txt, (x, y))
        y += 22
        for para in paragraphs:
            for line in _help_wrap(para, font_p, max_w):
                l_txt = font_p.render(line, True, COL_TEXT_DIM)
                surf.blit(l_txt, (x, y))
                y += 18
            y += 6
