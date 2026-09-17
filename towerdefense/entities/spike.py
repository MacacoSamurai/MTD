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

import pygame

from ..config import GRID_ORIGIN_X, GRID_ORIGIN_Y, CELL_SIZE
from ..systems import combat


class Spike:
    """Um espinho plantado numa celula do caminho.

    `col`/`row`: celula do caminho onde ele vive (posicao fixa).
    `charges`: quantos acertos ainda aguenta antes de sumir.
    `damage`: dano por acerto.
    `tower`: a torre dona (usada pra ler `effects`/`mods` atuais).
    `hit_ids`: ids (id()) dos inimigos ja acertados NESTA passagem, pra
    um mesmo inimigo parado em cima nao ser furado a cada frame -- so
    quando ele "chega" ao espinho (ver Game.update_spikes).
    """

    __slots__ = (
        "col", "row", "x", "y", "charges", "damage", "tower",
        "hidden", "pool_timer", "pool_dps", "pool_radius",
        "guaranteed_crit", "_hit_recently", "_cooldown",
    )

    def __init__(self, col, row, charges, damage, tower):
        self.col = col
        self.row = row
        self.x = GRID_ORIGIN_X + col * CELL_SIZE + CELL_SIZE // 2
        self.y = GRID_ORIGIN_Y + row * CELL_SIZE + CELL_SIZE // 2
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

    @property
    def alive(self):
        return self.charges > 0

    def try_hit(self, world, enemy):
        """Chamado quando `enemy` esta em cima da celula do espinho.
        Aplica dano/efeitos e consome 1 carga (a menos que "Armadilha
        Mortal"/"ARMADILHA DO ABISMO" digam o contrario). Retorna True
        se o espinho ainda existe depois do acerto."""
        if not self.alive or enemy is None or not enemy.alive:
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
            import random
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
        """Poca toxica residual (Pantano Toxico): dano por segundo em
        area ao redor do espinho enquanto ativa."""
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
