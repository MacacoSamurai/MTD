"""Desenho do HUD (topo/rodape), legenda de niveis e tela de game over.

Todas as funcoes recebem a instancia do Game (para ler estado como ouro,
vidas, onda atual...) e a Surface onde desenhar. Algumas tambem guardam
de volta no Game os rects dos botoes (gem_button_rect, skip_button_rect)
para que o tratamento de clique em game.py possa reutiliza-los.
"""

import pygame

from ..config import (
    WIDTH, HEIGHT, TOP_HUD_HEIGHT, BOTTOM_HUD_HEIGHT,
    COL_PANEL, COL_GRID_BORDER, COL_GOLD, COL_GEM, COL_TEXT, COL_TEXT_DIM,
    COL_WHITE, COL_RED, COL_GREEN,
    SKIP_WAVE_BASE_BONUS, SKIP_WAVE_BONUS_PER_WAVE,
)
from ..fonts import get_font
from ..entities.tower import tower_color
from ..maps import MAP_DEFS


def draw_gem_icon(surf, cx, cy, size):
    """Desenha um pequeno icone de gema (losango facetado)."""
    pts = [
        (cx, cy - size), (cx + size * 0.8, cy - size * 0.2),
        (cx + size * 0.55, cy + size), (cx - size * 0.55, cy + size),
        (cx - size * 0.8, cy - size * 0.2),
    ]
    pygame.draw.polygon(surf, COL_GEM, pts)
    pygame.draw.polygon(surf, (20, 30, 40), pts, 1)


def draw_hud(game, surf):
    font_big = get_font(24, bold=True)
    font_med = get_font(17)
    font_small = get_font(14)

    pygame.draw.rect(surf, COL_PANEL, (0, 0, WIDTH, TOP_HUD_HEIGHT))
    pygame.draw.line(surf, COL_GRID_BORDER, (0, TOP_HUD_HEIGHT), (WIDTH, TOP_HUD_HEIGHT), 2)
    pygame.draw.rect(surf, COL_PANEL, (0, HEIGHT - BOTTOM_HUD_HEIGHT, WIDTH, BOTTOM_HUD_HEIGHT))
    pygame.draw.line(surf, COL_GRID_BORDER, (0, HEIGHT - BOTTOM_HUD_HEIGHT), (WIDTH, HEIGHT - BOTTOM_HUD_HEIGHT), 2)

    # topo: ouro, vidas, onda
    gold_txt = font_big.render(f"Ouro: {int(game.gold)}", True, COL_GOLD)
    surf.blit(gold_txt, (20, 16))

    lives_color = COL_GREEN if game.lives > 5 else COL_RED
    lives_txt = font_big.render(f"Vidas: {game.lives}", True, lives_color)
    surf.blit(lives_txt, (240, 16))

    wave_txt = font_big.render(f"Onda: {game.wave_mgr.wave_num}", True, COL_TEXT)
    surf.blit(wave_txt, (440, 16))

    kills_txt = font_small.render(f"Abates: {game.total_kills}", True, COL_TEXT_DIM)
    surf.blit(kills_txt, (620, 22))

    map_name = MAP_DEFS[game.selected_map_id]["name"]
    map_txt = font_small.render(f"Mapa: {map_name} (M)", True, COL_TEXT_DIM)
    surf.blit(map_txt, (440, 44))

    # gemas: recurso mais valioso do jogo, ganho matando bosses.
    # tambem funciona como botao para abrir o shop de melhorias (G).
    gem_rect = pygame.Rect(0, 0, 130, 30)
    gem_rect.topright = (WIDTH - 20, 12)
    game.gem_button_rect = gem_rect
    gem_hovered = gem_rect.collidepoint(game.mouse_pos)
    gem_bg = (40, 55, 70) if gem_hovered else (28, 40, 52)
    pygame.draw.rect(surf, gem_bg, gem_rect, border_radius=8)
    pygame.draw.rect(surf, COL_GEM, gem_rect, 2, border_radius=8)
    draw_gem_icon(surf, gem_rect.x + 18, gem_rect.centery, 8)
    gem_txt = font_med.render(f"{game.gems}  (G)", True, COL_GEM)
    surf.blit(gem_txt, (gem_rect.x + 32, gem_rect.y + 5))

    cost_txt = font_small.render(f"Custo torre nova: {game.tower_cost}g", True, COL_TEXT_DIM)
    crect = cost_txt.get_rect()
    crect.topright = (gem_rect.x - 14, 22)
    surf.blit(cost_txt, crect)

    # status da onda
    if game.wave_mgr.wave_active:
        status = f"Onda {game.wave_mgr.wave_num} em andamento ({len(game.enemies)} vivos)"
        scol = COL_TEXT
    else:
        remaining = max(0, game.wave_mgr.auto_start_delay - game.wave_mgr.time_since_wave_end)
        status = f"Proxima onda em {remaining:0.1f}s (ESPACO)"
        scol = COL_TEXT_DIM
    status_txt = font_small.render(status, True, scol)
    rect = status_txt.get_rect(center=(WIDTH // 2 - 130, 50))
    surf.blit(status_txt, rect)

    # botao de pular onda (da ouro extra, mas antecipa a proxima onda)
    bonus = SKIP_WAVE_BASE_BONUS + game.wave_mgr.wave_num * SKIP_WAVE_BONUS_PER_WAVE
    btn_w, btn_h = 190, 34
    btn_rect = pygame.Rect(0, 0, btn_w, btn_h)
    btn_rect.center = (WIDTH // 2 + 150, 50)
    game.skip_button_rect = btn_rect
    hovered = btn_rect.collidepoint(game.mouse_pos)
    btn_bg = (70, 60, 30) if hovered else (48, 42, 26)
    pygame.draw.rect(surf, btn_bg, btn_rect, border_radius=8)
    pygame.draw.rect(surf, COL_GOLD, btn_rect, 2, border_radius=8)
    btn_txt = font_small.render(f"Pular onda (N)  +{bonus}g", True, COL_GOLD)
    t_rect = btn_txt.get_rect(center=btn_rect.center)
    surf.blit(btn_txt, t_rect)

    if game.paused:
        p_txt = font_big.render("PAUSADO (P para continuar)", True, COL_WHITE)
        rect = p_txt.get_rect(center=(WIDTH // 2, TOP_HUD_HEIGHT + 30))
        surf.blit(p_txt, rect)


def draw_legend(surf):
    font = get_font(14)
    y = HEIGHT - BOTTOM_HUD_HEIGHT + 10
    x = 20
    txt1 = font.render(
        "Slot vazio: torre.  |  Arraste sobre MESMO TIPO: MERGE (maior nivel persiste).  |  "
        "Clique: MELHORIAS.  |  G: gemas.  |  M: trocar de mapa.", True, COL_TEXT_DIM)
    surf.blit(txt1, (x, y))
    # legenda de cores de nivel
    ly = y + 26
    lx = x
    for i in range(6):
        pygame.draw.circle(surf, tower_color(i + 1), (lx + 8, ly + 8), 8)
        t = font.render(str(i + 1), True, COL_TEXT_DIM)
        surf.blit(t, (lx + 20, ly))
        lx += 40
    more_txt = font.render("...infinito", True, COL_TEXT_DIM)
    surf.blit(more_txt, (lx, ly))


def draw_game_over(game, surf):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 190))
    surf.blit(overlay, (0, 0))
    font_big = get_font(56, bold=True)
    font_med = get_font(26)
    t1 = font_big.render("GAME OVER", True, COL_RED)
    r1 = t1.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 60))
    surf.blit(t1, r1)
    t2 = font_med.render(f"Voce sobreviveu ate a onda {game.wave_mgr.wave_num}", True, COL_TEXT)
    r2 = t2.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    surf.blit(t2, r2)
    t3 = font_med.render(f"Total de abates: {game.total_kills}", True, COL_TEXT_DIM)
    r3 = t3.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40))
    surf.blit(t3, r3)
    t4 = font_med.render("Pressione R para escolher outro mapa", True, COL_GOLD)
    r4 = t4.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 90))
    surf.blit(t4, r4)
