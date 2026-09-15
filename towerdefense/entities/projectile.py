"""Projeteis disparados pelas torres.

Tem DOIS modos de voo, escolhidos pelos upgrades da torre que atirou:

- GUIADO (padrao): segue o alvo ate encostar nele e ai detona. Com o mod
  `homing` ele troca de alvo sozinho se o original morrer no caminho;
  sem `homing`, ele segue viajando ate o ultimo ponto conhecido.
- PERFURANTE (quando a torre tem `pierce > 0`): voa em linha reta na
  direcao em que foi disparado e atravessa varios inimigos, acertando
  cada um UMA vez (`_hit` guarda quem ja levou), ate esgotar as
  perfuracoes ou sair do alcance.

Nenhuma conta de dano mora aqui: o projetil so decide QUEM e QUANDO, e
delega o QUANTO para `systems/combat.py` (ver o comentario de topo de la
sobre por que a resolucao de dano e centralizada).

`world` e o objeto `Game` (precisa ter `.enemies`, `.vfx`,
`.pending_blasts`).
"""

import math

import pygame

from ..systems import combat


class Projectile:
    __slots__ = ("x", "y", "target", "speed", "damage", "color", "alive",
                 "eff", "shape", "angle", "dir_x", "dir_y", "pierce",
                 "ricochet", "homing", "travelled", "max_dist", "_hit")

    def __init__(self, x, y, target, speed, damage, color, eff,
                 shape="circle", angle=None, max_dist=1400.0):
        self.x = x
        self.y = y
        self.target = target
        self.speed = speed
        self.damage = damage
        self.color = color
        self.eff = eff
        self.shape = shape
        self.alive = True
        self.pierce = int(eff.get("pierce", 0))
        self.ricochet = int(eff.get("ricochet", 0))
        self.homing = bool(eff.get("homing", False))
        self.travelled = 0.0
        self.max_dist = max_dist
        self._hit = set()

        if angle is None and target is not None:
            angle = math.atan2(target.y - y, target.x - x)
        self.angle = angle or 0.0
        self.dir_x = math.cos(self.angle)
        self.dir_y = math.sin(self.angle)

    # ------------------------------------------------------------------
    @property
    def piercing(self):
        return self.pierce > 0

    def update(self, dt, world):
        if self.piercing:
            self._update_piercing(dt, world)
        else:
            self._update_guided(dt, world)

    # ------------------------------------------------------------------
    def _update_guided(self, dt, world):
        if self.target is None or not self.target.alive:
            if self.homing:
                self.target = self._find_new_target(world)
            if self.target is None or not self.target.alive:
                # nao some no ar: detona onde esta (se tiver splash, ainda
                # pega quem estiver por perto -- e o comportamento que o
                # jogador espera de um tiro explosivo)
                self._detonate(world, None)
                return

        dx, dy = self.target.x - self.x, self.target.y - self.y
        dist = math.hypot(dx, dy)
        if dist > 0:
            self.angle = math.atan2(dy, dx)
        move = self.speed * dt
        self.travelled += move
        if dist <= move or dist == 0:
            self.x, self.y = self.target.x, self.target.y
            self._impact(world, self.target)
        else:
            self.x += dx / dist * move
            self.y += dy / dist * move
            if self.travelled > self.max_dist:
                self._detonate(world, None)

    def _impact(self, world, enemy):
        """Acerto em cheio no alvo guiado. Pode ricochetear em vez de
        acabar (mod `ricochet` da Tempestade Celestial)."""
        if self.eff.get("splash", 0.0) > 0:
            self._detonate(world, enemy)
            return
        combat.resolve_hit(world, enemy, self.damage, self.eff)
        self._hit.add(id(enemy))
        if self.ricochet > 0:
            nxt = self._find_new_target(world, exclude_hit=True)
            if nxt is not None:
                self.ricochet -= 1
                self.target = nxt
                self.damage *= 0.85
                return
        self.alive = False

    def _detonate(self, world, enemy):
        combat.explode(world, self.x, self.y, self.damage, self.eff,
                       direct_target=enemy, color=self.color)
        self.alive = False

    # ------------------------------------------------------------------
    def _update_piercing(self, dt, world):
        move = self.speed * dt
        self.x += self.dir_x * move
        self.y += self.dir_y * move
        self.travelled += move

        for e in world.enemies:
            if not e.alive or id(e) in self._hit:
                continue
            rr = e.radius + 6
            if (e.x - self.x) ** 2 + (e.y - self.y) ** 2 <= rr * rr:
                self._hit.add(id(e))
                combat.resolve_hit(world, e, self.damage, self.eff)
                self.pierce -= 1
                if self.pierce <= 0:
                    # ultima perfuracao: se a torre tem splash, a parada
                    # do projetil ainda gera a explosao
                    if self.eff.get("splash", 0.0) > 0:
                        self._detonate(world, None)
                    else:
                        self.alive = False
                    return

        if self.travelled > self.max_dist:
            self.alive = False

    # ------------------------------------------------------------------
    def _find_new_target(self, world, exclude_hit=False):
        best = None
        best_d = 1e18
        for e in world.enemies:
            if not e.alive:
                continue
            if exclude_hit and id(e) in self._hit:
                continue
            d = (e.x - self.x) ** 2 + (e.y - self.y) ** 2
            if d < best_d and d < 220 ** 2:
                best = e
                best_d = d
        return best

    # ------------------------------------------------------------------
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
