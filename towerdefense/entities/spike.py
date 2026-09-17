"""Espinhos plantados no caminho pela torre "espinhos" (Armadilheiro).

Um Spike NAO e um projetil: fica parado numa celula do caminho e reage
quando um inimigo passa por cima (ver Game.update_spikes). Cada acerto
consome 1 carga; ao zerar, o espinho some. Evasao/camuflagem e sempre
ignorada -- e a identidade da torre (ela nunca "erra").

Efeitos de status proprios (veneno/lentidao/poca toxica) sao aplicados
diretamente no Enemy aqui, em vez de passar por `systems/combat.py`,
porque usam as chaves `spike_*` (ver upgrades.py) em vez das chaves
genericas `poison_dps`/`slow_factor` -- assim nao competem/colidem com
o veneno e a lentidao de outras torres nesta mesma pilha de mods.
"""

import math
import random

import pygame

from ..config import GRID_ORIGIN_X, GRID_ORIGIN_Y, CELL_SIZE
from ..systems import combat


class Spike:
    """Um espinho plantado numa celula do caminho.

    `col`/`row`: celula do caminho onde ele vive (usada so pra achar
    espinhos numa area, ex.: `_plant_spike`; a posicao visual/de colisao
    de verdade e `x`/`y`, em pixel, que pode estar em qualquer ponto
    dentro da celula -- ver `towerdefense/entities/tower.py::_plant_spike`).
    `charges`: quantos acertos ainda aguenta antes de sumir.
    `damage`: dano por acerto.
    `tower`: a torre dona (usada pra ler `effects`/`mods` atuais).
    `hit_ids`: ids (id()) dos inimigos ja acertados NESTA passagem, pra
    um mesmo inimigo parado em cima nao ser furado a cada frame -- so
    quando ele "chega" ao espinho (ver Game.update_spikes).

    FASE DE VOO: o espinho nao aparece pronto na celula -- ele nasce na
    posicao da torre (`origin_px`) e anima ate o ponto final (`target_px`)
    num arco curto (ver `update`/`draw`). Enquanto `landed` for False ele
    nao machuca ninguem (`alive` continua True pra contar no limite de
    `spike_max` e reservar o lugar, mas `try_hit` recusa о acerto) -- so
    depois de pousar ele vira uma armadilha de verdade."""

    __slots__ = (
        "col", "row", "x", "y", "charges", "damage", "tower",
        "hidden", "pool_timer", "pool_dps", "pool_radius",
        "guaranteed_crit", "_hit_recently", "_cooldown",
        "origin_x", "origin_y", "target_x", "target_y",
        "flight_t", "flight_time", "landed", "spin",
    )

    FLIGHT_TIME = 0.42  # segundos de voo ate pousar

    def __init__(self, col, row, charges, damage, tower, target_px=None, origin_px=None):
        self.col = col
        self.row = row
        if target_px is not None:
            self.target_x, self.target_y = target_px
        else:
            self.target_x = GRID_ORIGIN_X + col * CELL_SIZE + CELL_SIZE // 2
            self.target_y = GRID_ORIGIN_Y + row * CELL_SIZE + CELL_SIZE // 2
        if origin_px is not None:
            self.origin_x, self.origin_y = origin_px
        else:
            self.origin_x, self.origin_y = self.target_x, self.target_y
        # posicao atual: comeca na origem (torre) e migra pro alvo em update()
        self.x, self.y = self.origin_x, self.origin_y
        self.charges = charges
        self.damage = damage
        self.tower = tower
        self.hidden = bool(tower.mods.get("spike_hidden", False))
        # poca toxica residual (Pantano Toxico): fica ativa por um tempo
        # depois do primeiro acerto que a criou
        self.pool_timer = 0.0
        self.pool_dps = 0.0
        self.pool_radius = 0.0
        # "Golpe das Sombras": proximo acerto garantidamente critico
        self.guaranteed_crit = False
        self._hit_recently = set()
        self._cooldown = 0.0
        # voo: se ja nasce "no lugar" (origem == alvo, plantio instantaneo
        # de fallback), pula a animacao -- so anima quando ha de fato uma
        # distancia da torre ate o ponto plantado
        dist = ((self.target_x - self.origin_x) ** 2 + (self.target_y - self.origin_y) ** 2) ** 0.5
        self.flight_time = self.FLIGHT_TIME if dist > 1.0 else 0.0
        self.flight_t = 0.0
        self.landed = self.flight_time <= 0.0
        self.spin = random.uniform(0, 6.283)

    @property
    def alive(self):
        return self.charges > 0

    def try_hit(self, world, enemy):
        """Chamado quando `enemy` esta em cima da celula do espinho.
        Aplica dano/efeitos e consome 1 carga (a menos que "Armadilha
        Mortal"/"ARMADILHA DO ABISMO" digam o contrario). Retorna True
        se o espinho ainda existe depois do acerto."""
        if not self.landed or not self.alive or enemy is None or not enemy.alive:
            return self.alive

        m = self.tower.mods
        eff = dict(self.tower.effects)
        eff["armor_pierce"] = eff.get("armor_pierce", False)
        if self.guaranteed_crit:
            eff["crit_chance"] = 1.0
        # espinho sempre acerta: evasao/camuflagem nunca se aplicam aqui
        killed = combat.resolve_hit(world, enemy, self.damage, eff, ignore_dodge=True)
        self.guaranteed_crit = False

        # veneno/corrosao/lentidao proprios do espinho (chaves spike_*)
        poison_dps = m.get("spike_poison_dps", 0.0)
        if poison_dps > 0:
            enemy.apply_poison(poison_dps * self.damage, m.get("spike_poison_time", 3.0), 5)
            shred = m.get("spike_poison_shred", 0.0)
            if shred > 0:
                enemy.apply_shred(shred, m.get("spike_poison_time", 3.0))
        slow_factor = m.get("spike_slow_factor")
        if slow_factor is not None and slow_factor < 1.0:
            enemy.apply_slow(slow_factor, m.get("spike_slow_time", 1.0))

        pool_dps = m.get("spike_pool_dps", 0.0)
        if pool_dps > 0:
            self.pool_dps = pool_dps * self.damage
            self.pool_timer = m.get("spike_pool_time", 3.0)
            self.pool_radius = m.get("spike_pool_radius", 40.0)

        cloud_chance = m.get("spike_cloud_chance", 0.0)
        if cloud_chance > 0 and killed:
            if random.random() < cloud_chance:
                combat.area_damage(world, self.x, self.y, max(50.0, self.pool_radius or 50.0),
                                   self.damage * 1.5, eff, exclude=enemy, apply_statuses=False)

        free = False
        if killed and m.get("spike_free_on_kill", False):
            free = True
        if not free:
            self.charges -= 1
        if killed and m.get("spike_recharge_on_kill", False):
            base_charges = self.tower.spike_charges
            self.charges = min(base_charges, self.charges + 1)
        return self.alive

    def update(self, world, dt):
        """Alem da poca toxica residual (Pantano Toxico -- dano por
        segundo em area enquanto ativa), avanca a animacao de voo: o
        espinho interpola de `origin` ate `target` e SO passa a `landed`
        (podendo furar inimigos, ver `try_hit`) quando o voo termina."""
        if not self.landed:
            self.flight_t += dt
            if self.flight_t >= self.flight_time:
                self.flight_t = self.flight_time
                self.x, self.y = self.target_x, self.target_y
                self.landed = True
            else:
                t = self.flight_t / self.flight_time
                self.x = self.origin_x + (self.target_x - self.origin_x) * t
                self.y = self.origin_y + (self.target_y - self.origin_y) * t

        if self.pool_timer <= 0:
            return
        self.pool_timer -= dt
        if self.pool_timer <= 0:
            self.pool_dps = 0.0
            return
        eff = {"armor_pierce": True}
        combat.area_damage(world, self.x, self.y, self.pool_radius,
                           self.pool_dps * dt, eff, apply_statuses=False)

    def draw(self, surf, offset):
        ox, oy = offset
        if not self.landed:
            self._draw_flying(surf, ox, oy)
            return
        px, py = int(self.x + ox), int(self.y + oy)
        if self.hidden:
            # camuflado: quase invisivel, so um brilho fraco no chao
            color = (90, 80, 60)
            alpha_pts = 60
        else:
            color = (150, 130, 90)
            alpha_pts = 255
        size = 6 + self.charges * 2
        pts = [
            (px, py - size), (px + size * 0.6, py),
            (px, py + size), (px - size * 0.6, py),
        ]
        if self.hidden:
            spike_surf = pygame.Surface((size * 2 + 4, size * 2 + 4), pygame.SRCALPHA)
            cx, cy = size + 2, size + 2
            local_pts = [(cx, cy - size), (cx + size * 0.6, cy),
                         (cx, cy + size), (cx - size * 0.6, cy)]
            pygame.draw.polygon(spike_surf, (*color, alpha_pts), local_pts)
            surf.blit(spike_surf, (px - cx, py - cy))
        else:
            pygame.draw.polygon(surf, color, pts)
            pygame.draw.polygon(surf, (40, 34, 22), pts, 1)
        if self.pool_timer > 0:
            pool_surf = pygame.Surface((int(self.pool_radius * 2), int(self.pool_radius * 2)), pygame.SRCALPHA)
            pygame.draw.circle(pool_surf, (110, 200, 90, 60),
                               (int(self.pool_radius), int(self.pool_radius)), int(self.pool_radius))
            surf.blit(pool_surf, (px - self.pool_radius, py - self.pool_radius))

    def _draw_flying(self, surf, ox, oy):
        """Espinho em voo (torre -> ponto plantado): a POSICAO horizontal
        ja vem interpolada em `update` (self.x/self.y); aqui so soma um
        arco vertical (sobe e desce, seno de 0 a pi) por cima disso pra
        parecer arremesso de verdade, e nao um deslizar reto rente ao
        chao. O espinho gira livremente durante o voo (`self.spin`) e
        encolhe/gira ate ficar reto e do tamanho final ao pousar. Uma
        sombra no ponto de pouso cresce conforme ele se aproxima, pra dar
        a leitura de profundidade e avisar onde ele vai cair."""
        t = 0.0 if self.flight_time <= 0 else self.flight_t / self.flight_time
        arc_h = 26.0 + 4.0 * self.charges
        arc = math.sin(t * math.pi) * arc_h
        px = int(self.x + ox)
        py = int(self.y + oy - arc)

        # sombra no ponto de pouso, crescendo conforme o espinho se aproxima
        land_px, land_py = int(self.target_x + ox), int(self.target_y + oy)
        shadow_r = max(2, int((3 + self.charges * 1.5) * (0.4 + 0.6 * t)))
        shadow_alpha = int(120 * (0.3 + 0.7 * t))
        shadow_surf = pygame.Surface((shadow_r * 2 + 2, shadow_r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(shadow_surf, (10, 8, 4, shadow_alpha),
                            (shadow_r + 1, shadow_r + 1), shadow_r)
        surf.blit(shadow_surf, (land_px - shadow_r - 1, land_py - shadow_r - 1))

        color = (90, 80, 60) if self.hidden else (150, 130, 90)
        size = 6 + self.charges * 2
        ang = self.spin + t * 10.5  # gira bastante no comeco, quase para ao pousar
        cos_a, sin_a = math.cos(ang), math.sin(ang)

        def rot(lx, ly):
            return (px + lx * cos_a - ly * sin_a, py + lx * sin_a + ly * cos_a)

        pts = [rot(0, -size), rot(size * 0.6, 0), rot(0, size), rot(-size * 0.6, 0)]
        pygame.draw.polygon(surf, color, pts)
        pygame.draw.polygon(surf, (40, 34, 22), pts, 1)