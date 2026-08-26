"""Inimigos: dados de tipo (ENEMY_TYPES) e a classe Enemy."""

import math
import pygame

from ..config import (
    ENEMY_TYPES, COL_HP_BG, COL_HP_FG, COL_RED,
    BOSS_WAVE_INTERVAL, BOSS_HP_SCALE_PER_CYCLE, BOSS_GEMS_PER_CYCLE,
)
from ..fonts import get_font


class Enemy:
    def __init__(self, kind, wave, hp_mult, speed_mult, map_path):
        base = ENEMY_TYPES[kind]
        self.map_path = map_path
        self.kind = kind
        self.dist = 0.0
        self.is_boss = base.get("is_boss", False)
        boss_extra_mult = 1.0
        if self.is_boss:
            # bosses ficam mais fortes a cada ciclo de 10 ondas (boss da
            # onda 20 e mais forte que o da onda 10, etc.)
            cycle = max(0, (wave // BOSS_WAVE_INTERVAL) - 1)
            boss_extra_mult = 1.0 + cycle * BOSS_HP_SCALE_PER_CYCLE
        self.max_hp = base["hp"] * hp_mult * boss_extra_mult
        self.hp = self.max_hp
        self.speed = base["speed"] * speed_mult
        self.gold = base["gold"]
        self.gems = base.get("gems", 0)
        if self.is_boss:
            cycle = max(0, (wave // BOSS_WAVE_INTERVAL) - 1)
            self.gems += cycle * BOSS_GEMS_PER_CYCLE
        self.radius = base["radius"]
        self.color = base["color"]
        self.armor = base["armor"]
        self.shape = base["shape"]
        self.x, self.y, self.angle = map_path.point_at_distance(0)
        self.alive = True
        self.slow_timer = 0.0
        self.slow_factor = 1.0
        self.reached_end = False
        self._processed_death = False

    def update(self, dt):
        if self.slow_timer > 0:
            self.slow_timer -= dt
            if self.slow_timer <= 0:
                self.slow_factor = 1.0
        eff_speed = self.speed * self.slow_factor
        self.dist += eff_speed * dt
        if self.dist >= self.map_path.total_len:
            self.reached_end = True
            self.alive = False
            return
        self.x, self.y, self.angle = self.map_path.point_at_distance(self.dist)

    def apply_slow(self, factor, duration):
        # sempre pega o slow mais forte ativo
        if factor < self.slow_factor or self.slow_timer <= 0:
            self.slow_factor = factor
            self.slow_timer = duration

    def take_damage(self, dmg, ignore_armor=False):
        real_dmg = dmg if ignore_armor else max(1, dmg - self.armor)
        self.hp -= real_dmg
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    def draw(self, surf, offset):
        ox, oy = offset
        px, py = self.x + ox, self.y + oy
        r = self.radius
        if self.shape == "circle":
            pygame.draw.circle(surf, self.color, (int(px), int(py)), r)
            pygame.draw.circle(surf, (0, 0, 0), (int(px), int(py)), r, 1)
        elif self.shape == "square":
            rect = pygame.Rect(0, 0, r * 1.8, r * 1.8)
            rect.center = (px, py)
            pygame.draw.rect(surf, self.color, rect, border_radius=4)
            pygame.draw.rect(surf, (0, 0, 0), rect, 1, border_radius=4)
        elif self.shape == "diamond":
            pts = [(px, py - r), (px + r, py), (px, py + r), (px - r, py)]
            pygame.draw.polygon(surf, self.color, pts)
            pygame.draw.polygon(surf, (0, 0, 0), pts, 1)
        elif self.shape == "star":
            pts = []
            for i in range(10):
                ang = -math.pi / 2 + i * math.pi / 5
                rr = r if i % 2 == 0 else r * 0.5
                pts.append((px + rr * math.cos(ang), py + rr * math.sin(ang)))
            pygame.draw.polygon(surf, self.color, pts)
            pygame.draw.polygon(surf, (0, 0, 0), pts, 1)

        if self.slow_timer > 0:
            pygame.draw.circle(surf, (140, 210, 255), (int(px), int(py)), r + 4, 2)

        if self.is_boss:
            # anel pulsante dourado + rotulo "BOSS" para destacar
            pygame.draw.circle(surf, (255, 230, 120), (int(px), int(py)), r + 7, 3)
            font_b = get_font(12, bold=True)
            btxt = font_b.render("BOSS", True, (255, 220, 90))
            brect = btxt.get_rect(center=(px, py - r - 22))
            surf.blit(btxt, brect)

        # barra de vida
        bar_w = r * 2.2
        bar_h = 5
        bx = px - bar_w / 2
        by = py - r - 12
        pygame.draw.rect(surf, COL_HP_BG, (bx, by, bar_w, bar_h))
        pct = max(0, self.hp / self.max_hp)
        pygame.draw.rect(surf, COL_HP_FG if pct > 0.3 else COL_RED, (bx, by, bar_w * pct, bar_h))
