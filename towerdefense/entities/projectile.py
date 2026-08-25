"""Projeteis disparados pelas torres."""

import math
import pygame


class Projectile:
    __slots__ = ("x", "y", "target", "speed", "damage", "color", "alive",
                 "splash", "slow", "pierce_hits", "shape", "armor_pierce", "angle")

    def __init__(self, x, y, target, speed, damage, color, splash=0, slow=None,
                 shape="circle", armor_pierce=False):
        self.x = x
        self.y = y
        self.target = target
        self.speed = speed
        self.damage = damage
        self.color = color
        self.alive = True
        self.splash = splash
        self.slow = slow  # (factor, duration) ou None
        self.pierce_hits = 0
        self.shape = shape
        self.armor_pierce = armor_pierce
        self.angle = 0.0

    def update(self, dt, enemies):
        if self.target is None or not self.target.alive:
            self.alive = False
            return
        tx, ty = self.target.x, self.target.y
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        self.angle = math.atan2(dy, dx)
        move = self.speed * dt
        if dist <= move or dist == 0:
            self.hit(enemies)
        else:
            self.x += dx / dist * move
            self.y += dy / dist * move

    def hit(self, enemies):
        self.alive = False
        dmg = self.damage
        if self.splash > 0:
            for e in enemies:
                if not e.alive:
                    continue
                d = math.hypot(e.x - self.target.x, e.y - self.target.y)
                if d <= self.splash:
                    e.take_damage(dmg, ignore_armor=self.armor_pierce)
                    if self.slow:
                        e.apply_slow(*self.slow)
        else:
            self.target.take_damage(dmg, ignore_armor=self.armor_pierce)
            if self.slow:
                self.target.apply_slow(*self.slow)

    def draw(self, surf, offset):
        ox, oy = offset
        px, py = self.x + ox, self.y + oy
        if self.shape == "arrow":
            length = 12
            ex = px + math.cos(self.angle) * length
            ey = py + math.sin(self.angle) * length
            pygame.draw.line(surf, self.color, (px, py), (ex, ey), 3)
        elif self.shape == "line":
            length = 22
            ex = px - math.cos(self.angle) * length
            ey = py - math.sin(self.angle) * length
            pygame.draw.line(surf, self.color, (px, py), (ex, ey), 2)
        elif self.shape == "square":
            rect = pygame.Rect(0, 0, 9, 9)
            rect.center = (px, py)
            pygame.draw.rect(surf, self.color, rect, border_radius=2)
        elif self.shape == "shard":
            pts = [(px, py - 6), (px + 4, py), (px, py + 6), (px - 4, py)]
            pygame.draw.polygon(surf, self.color, pts)
        else:
            pygame.draw.circle(surf, self.color, (int(px), int(py)), 5)
