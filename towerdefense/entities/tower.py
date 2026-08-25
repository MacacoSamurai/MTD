"""Torres: helpers de nivel (cor/nome), a classe Tower e seu merge/upgrade."""

import math
import pygame

from ..config import (
    TOWER_TYPES, TOWER_LEVEL_COLORS, TOWER_LEVEL_NAMES,
    GRID_ORIGIN_X, GRID_ORIGIN_Y, CELL_SIZE,
    UPGRADE_DAMAGE_PCT, UPGRADE_RANGE_PCT, UPGRADE_RATE_PCT, UPGRADE_BASE_COST,
    COL_MERGE_GLOW,
)
from ..fonts import get_font
from .projectile import Projectile


def tower_color(level):
    if level - 1 < len(TOWER_LEVEL_COLORS):
        return TOWER_LEVEL_COLORS[level - 1]
    # niveis 8+: gera cores infinitas girando o matiz (nunca estagna)
    extra = level - len(TOWER_LEVEL_COLORS)
    hue = (extra * 47) % 360  # 47 eh coprimo de 360, boa distribuicao
    c = pygame.Color(0)
    c.hsva = (hue, 85, 100, 100)
    return (c.r, c.g, c.b)


def tower_name(level):
    if level - 1 < len(TOWER_LEVEL_NAMES):
        return TOWER_LEVEL_NAMES[level - 1]
    return f"Ascendido +{level - len(TOWER_LEVEL_NAMES)}"


class Tower:
    def __init__(self, col, row, ttype="canhao", level=1):
        self.col = col
        self.row = row
        self.ttype = ttype
        self.level = level
        self.cooldown = 0.0
        self.target = None
        self.upgrades = {"damage": 0, "range": 0, "rate": 0}
        self.recalc_stats()
        # posicao visual (para animacao de drag)
        self.drag_offset = (0, 0)
        self.being_dragged = False

    def recalc_stats(self):
        spec = TOWER_TYPES[self.ttype]
        lvl = self.level
        growth = 1.55 ** (lvl - 1)
        self.range = spec["base_range"] + (lvl - 1) * 14
        self.damage = spec["base_damage"] * growth
        self.fire_rate = max(0.10, spec["base_rate"] - (lvl - 1) * 0.03)
        self.splash = 0
        self.slow = spec.get("always_slow")
        sfl = spec["splash_from_lvl"]
        if sfl is not None and lvl >= sfl:
            self.splash = spec["splash_base"] + (lvl - sfl) * spec["splash_step"]
        # niveis muito altos (alem do merge normal) tambem ganham lentidao,
        # mesmo em tipos que nao tem isso de base
        if lvl >= 6 and self.slow is None:
            self.slow = (0.6, 1.0)
        self.armor_pierce = spec.get("armor_pierce", False)

        # aplica as melhorias especificas compradas no menu de upgrades
        # (independentes do merge/nivel). Cada ponto de upgrade da um
        # incremento percentual sobre a stat base ja calculada acima.
        dmg_pts = self.upgrades["damage"]
        rng_pts = self.upgrades["range"]
        rate_pts = self.upgrades["rate"]
        self.damage *= (1 + UPGRADE_DAMAGE_PCT * dmg_pts)
        self.range *= (1 + UPGRADE_RANGE_PCT * rng_pts)
        self.fire_rate = max(0.05, self.fire_rate * (1 - UPGRADE_RATE_PCT * rate_pts))

    def upgrade_cost(self, aspect):
        """Custo em ouro para comprar o proximo ponto de melhoria daquele
        aspecto ('damage', 'range' ou 'rate'). Cresce a cada compra e
        tambem fica mais caro em torres de nivel mais alto."""
        pts = self.upgrades[aspect]
        base = UPGRADE_BASE_COST[aspect]
        return int(base * (1.6 ** pts) * (1 + 0.12 * (self.level - 1)))

    def buy_upgrade(self, aspect):
        self.upgrades[aspect] += 1
        self.recalc_stats()

    def grid_pos(self):
        gx = GRID_ORIGIN_X + self.col * CELL_SIZE + CELL_SIZE // 2
        gy = GRID_ORIGIN_Y + self.row * CELL_SIZE + CELL_SIZE // 2
        return gx, gy

    def update(self, dt, enemies, projectiles):
        if self.being_dragged:
            return
        self.cooldown -= dt
        gx, gy = self.grid_pos()

        # valida alvo atual
        if self.target is not None:
            if (not self.target.alive or
                    math.hypot(self.target.x - gx, self.target.y - gy) > self.range):
                self.target = None

        if self.target is None:
            best = None
            best_dist = -1
            for e in enemies:
                if not e.alive:
                    continue
                d = math.hypot(e.x - gx, e.y - gy)
                if d <= self.range and e.dist > best_dist:
                    best = e
                    best_dist = e.dist
            self.target = best

        if self.target is not None and self.cooldown <= 0:
            self.cooldown = self.fire_rate
            color = tower_color(self.level)
            spec = TOWER_TYPES[self.ttype]
            proj = Projectile(gx, gy, self.target, spec["proj_speed"], self.damage, color,
                               splash=self.splash, slow=self.slow,
                               shape=spec["proj_shape"], armor_pierce=self.armor_pierce)
            projectiles.append(proj)

    def draw(self, surf, mouse_pos, dragging_this):
        if dragging_this:
            gx, gy = mouse_pos
        else:
            gx, gy = self.grid_pos()

        color = tower_color(self.level)
        radius = 20 + min(self.level, 10) * 1.2

        # range indicator quando arrastando ou hover
        if dragging_this:
            range_surf = pygame.Surface((self.range * 2, self.range * 2), pygame.SRCALPHA)
            pygame.draw.circle(range_surf, (*color, 40), (self.range, self.range), self.range)
            pygame.draw.circle(range_surf, (*color, 120), (self.range, self.range), self.range, 2)
            surf.blit(range_surf, (gx - self.range, gy - self.range))

        # base: formato varia com o tipo de torre para diferenciar visualmente
        shape = TOWER_TYPES[self.ttype]["proj_shape"]
        pygame.draw.circle(surf, (30, 30, 36), (int(gx), int(gy)), radius + 4)
        if shape == "square":  # canhao pesado -> base quadrada
            rect = pygame.Rect(0, 0, radius * 1.8, radius * 1.8)
            rect.center = (gx, gy)
            pygame.draw.rect(surf, color, rect, border_radius=6)
            pygame.draw.rect(surf, (0, 0, 0), rect, 2, border_radius=6)
        elif shape == "line":  # sniper -> hexagono alongado
            pts = []
            for i in range(6):
                ang = math.pi / 6 + i * math.pi / 3
                pts.append((gx + math.cos(ang) * radius, gy + math.sin(ang) * radius))
            pygame.draw.polygon(surf, color, pts)
            pygame.draw.polygon(surf, (0, 0, 0), pts, 2)
        else:
            pygame.draw.circle(surf, color, (int(gx), int(gy)), radius)
            pygame.draw.circle(surf, (0, 0, 0), (int(gx), int(gy)), radius, 2)

        # canhao apontando pro alvo
        if self.target is not None and self.target.alive:
            ang = math.atan2(self.target.y - gy, self.target.x - gx)
        else:
            ang = -math.pi / 2
        bx = gx + math.cos(ang) * radius
        by = gy + math.sin(ang) * radius
        ex = gx + math.cos(ang) * (radius + 14)
        ey = gy + math.sin(ang) * (radius + 14)
        pygame.draw.line(surf, (20, 20, 24), (bx, by), (ex, ey), 6)

        # nivel no centro
        font = get_font(16, bold=True)
        txt = font.render(str(self.level), True, (20, 20, 24))
        rect = txt.get_rect(center=(gx, gy))
        surf.blit(txt, rect)

        # icone do tipo, pequeno, acima do nivel
        font_tiny = get_font(10, bold=True)
        label = TOWER_TYPES[self.ttype]["label"]
        abbrev = "".join(w[0] for w in label.split())[:2].upper()
        font_tiny.render(abbrev, True, (20, 20, 24, 160))

        if dragging_this:
            pygame.draw.circle(surf, COL_MERGE_GLOW, (int(gx), int(gy)), radius + 8, 3)
