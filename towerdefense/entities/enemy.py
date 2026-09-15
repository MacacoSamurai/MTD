"""Inimigos: dados de tipo (ENEMY_TYPES) e a classe Enemy.

Alem de andar pelo caminho, o inimigo carrega os EFEITOS DE STATUS que a
arvore de upgrades das torres aplica (ver `towerdefense/upgrades.py`):

    queimadura (burn)  -> dano por segundo, nao acumula (pega o mais forte)
    veneno (poison)    -> dano por segundo ACUMULAVEL ate um limite de pilhas
    lentidao (slow)    -> multiplicador de velocidade, pega o mais forte
    congelamento       -> velocidade zero enquanto durar
    marcacao (vuln)    -> multiplica TODO dano recebido, de qualquer torre
    armadura quebrada  -> reduz a armadura efetiva temporariamente

Todos sao temporizados e resolvidos em `update`. Como varias torres
aplicam o mesmo efeito, a regra geral e "o efeito mais forte vence"
(nunca somar duracoes), pra nao virar bola de neve incontrolavel -- a
unica excecao e o veneno, que acumula em pilhas de proposito (e a
identidade do caminho Arqueiro Tatico).
"""

import math
import random

import pygame

from ..config import (
    ENEMY_TYPES, COL_HP_BG, COL_HP_FG, COL_RED,
    BOSS_WAVE_INTERVAL, BOSS_HP_SCALE_PER_CYCLE, BOSS_GEMS_PER_CYCLE,
    HEAVY_ENEMY_ARMOR, EVASION_CHANCE,
)
from ..fonts import get_font


class Enemy:
    # Amplificacao/lentidao GLOBAL, escritas pelas habilidades de pista
    # inteira ("DOMINIO ETERNO", "VISAO ABSOLUTA") em systems/abilities.py.
    # Sao atributos de CLASSE de proposito: essas habilidades afetam a
    # pista toda, inclusive inimigos que ainda nem spawnaram quando foram
    # ativadas -- guardar por instancia exigiria re-marcar a lista a cada
    # spawn. Quem liga zera de volta ao fim da duracao.
    global_amp = 0.0
    global_slow = 1.0

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
        # inimigos "esquivos" (camuflados): tem chance de ignorar um acerto,
        # a menos que a torre tenha deteccao (caminho Observador da sniper).
        self.evasive = base.get("evasive", False)
        self.x, self.y, self.angle = map_path.point_at_distance(0)
        self.alive = True
        self.reached_end = False
        self._processed_death = False

        # --- efeitos de status ---
        self.slow_timer = 0.0
        self.slow_factor = 1.0
        self.freeze_timer = 0.0
        self.burn_dps = 0.0
        self.burn_timer = 0.0
        self.poison_stacks = 0
        self.poison_dps = 0.0
        self.poison_timer = 0.0
        self.vuln_amp = 0.0
        self.vuln_timer = 0.0
        self.shred = 0.0
        self.shred_timer = 0.0
        self.flash = 0.0  # feedback visual curto ao levar dano pesado

    # ------------------------------------------------------------------
    # CONSULTAS
    # ------------------------------------------------------------------
    @property
    def frozen(self):
        return self.freeze_timer > 0

    @property
    def slowed(self):
        return self.frozen or self.slow_timer > 0

    @property
    def is_heavy(self):
        """"Pesado" = chefes e inimigos blindados/enormes. E o criterio
        dos caminhos anti-colosso (Canhao Pesado 0-0-X, Cacador da
        flecha) pra aplicar o bonus de dano."""
        return self.is_boss or self.armor >= HEAVY_ENEMY_ARMOR

    def effective_armor(self):
        return max(0.0, self.armor - (self.shred if self.shred_timer > 0 else 0.0))

    def damage_taken_mult(self):
        amp = Enemy.global_amp
        if self.vuln_timer > 0:
            amp = max(amp, self.vuln_amp)
        return 1.0 + amp

    def danger_score(self, path_total):
        """Quanto esse inimigo "assusta" agora -- usado pela IA das
        habilidades tier 6 pra escolher alvos (ver systems/abilities.py).
        Combina vida restante, se e pesado/boss, e o quanto ja avancou
        no caminho (quem esta perto do fim e mais urgente)."""
        progress = self.dist / path_total if path_total else 0.0
        score = self.hp
        if self.is_boss:
            score *= 3.0
        elif self.is_heavy:
            score *= 1.8
        return score * (1.0 + progress * 1.5)

    # ------------------------------------------------------------------
    # ATUALIZACAO
    # ------------------------------------------------------------------
    def _tick_status(self, dt):
        if self.flash > 0:
            self.flash -= dt
        if self.slow_timer > 0:
            self.slow_timer -= dt
            if self.slow_timer <= 0:
                self.slow_factor = 1.0
        if self.freeze_timer > 0:
            self.freeze_timer -= dt
        if self.vuln_timer > 0:
            self.vuln_timer -= dt
            if self.vuln_timer <= 0:
                self.vuln_amp = 0.0
        if self.shred_timer > 0:
            self.shred_timer -= dt
            if self.shred_timer <= 0:
                self.shred = 0.0

        # dano ao longo do tempo: queimadura + veneno acumulavel. Ignoram
        # armadura de proposito (ja "passaram" por ela no acerto) mas
        # continuam sofrendo a amplificacao de marcacao.
        total_dot = 0.0
        if self.burn_timer > 0:
            self.burn_timer -= dt
            total_dot += self.burn_dps
            if self.burn_timer <= 0:
                self.burn_dps = 0.0
        if self.poison_timer > 0:
            self.poison_timer -= dt
            total_dot += self.poison_dps * self.poison_stacks
            if self.poison_timer <= 0:
                self.poison_stacks = 0
                self.poison_dps = 0.0
        if total_dot > 0:
            self.take_damage(total_dot * dt, ignore_armor=True, silent=True)

    def update(self, dt):
        self._tick_status(dt)
        if not self.alive:
            return
        eff_speed = self.speed * self.slow_factor * Enemy.global_slow
        if self.frozen:
            eff_speed = 0.0
        self.dist += eff_speed * dt
        if self.dist >= self.map_path.total_len:
            self.reached_end = True
            self.alive = False
            return
        self.x, self.y, self.angle = self.map_path.point_at_distance(self.dist)

    # ------------------------------------------------------------------
    # EFEITOS APLICADOS PELAS TORRES
    # ------------------------------------------------------------------
    def apply_slow(self, factor, duration):
        # sempre pega o slow mais forte ativo
        if factor < self.slow_factor or self.slow_timer <= 0:
            self.slow_factor = factor
        self.slow_timer = max(self.slow_timer, duration)

    def apply_freeze(self, duration, boss_slow=0.30):
        """Congela. Chefes NAO congelam (seriam trivializados): levam uma
        lentidao muito forte pela mesma duracao -- exatamente a regra
        descrita na habilidade "ERA DO GELO"."""
        if self.is_boss:
            self.apply_slow(boss_slow, duration)
        else:
            self.freeze_timer = max(self.freeze_timer, duration)

    def apply_burn(self, dps, duration):
        self.burn_dps = max(self.burn_dps, dps)
        self.burn_timer = max(self.burn_timer, duration)

    def apply_poison(self, dps, duration, max_stacks):
        self.poison_dps = max(self.poison_dps, dps)
        self.poison_stacks = min(int(max_stacks), self.poison_stacks + 1)
        self.poison_timer = max(self.poison_timer, duration)

    def apply_mark(self, amp, duration):
        self.vuln_amp = max(self.vuln_amp, amp)
        self.vuln_timer = max(self.vuln_timer, duration)

    def apply_shred(self, amount, duration=4.0):
        self.shred = max(self.shred, amount)
        self.shred_timer = max(self.shred_timer, duration)

    def dodges(self, detector):
        """True se o acerto deve ser ignorado por esquiva. Torres com
        deteccao (`camo_detect`, caminho Observador) nunca erram."""
        if not self.evasive or detector:
            return False
        return random.random() < EVASION_CHANCE

    # ------------------------------------------------------------------
    def take_damage(self, dmg, ignore_armor=False, silent=False):
        if not self.alive:
            return False
        real = dmg if ignore_armor else max(1.0, dmg - self.effective_armor())
        real *= self.damage_taken_mult()
        self.hp -= real
        if not silent and real > self.max_hp * 0.08:
            self.flash = 0.12
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    # ------------------------------------------------------------------
    # DESENHO
    # ------------------------------------------------------------------
    def _status_color(self):
        """Cor do anel de status (o efeito mais "informativo" vence)."""
        if self.frozen:
            return (200, 245, 255)
        if self.vuln_timer > 0 or Enemy.global_amp > 0:
            return (255, 120, 220)
        if self.poison_stacks > 0:
            return (150, 255, 130)
        if self.burn_timer > 0:
            return (255, 150, 60)
        if self.slow_timer > 0:
            return (140, 210, 255)
        return None

    def draw(self, surf, offset):
        ox, oy = offset
        px, py = self.x + ox, self.y + oy
        r = self.radius
        color = (255, 255, 255) if self.flash > 0 else self.color
        if self.shape == "circle":
            pygame.draw.circle(surf, color, (int(px), int(py)), r)
            pygame.draw.circle(surf, (0, 0, 0), (int(px), int(py)), r, 1)
        elif self.shape == "square":
            rect = pygame.Rect(0, 0, r * 1.8, r * 1.8)
            rect.center = (px, py)
            pygame.draw.rect(surf, color, rect, border_radius=4)
            pygame.draw.rect(surf, (0, 0, 0), rect, 1, border_radius=4)
        elif self.shape == "diamond":
            pts = [(px, py - r), (px + r, py), (px, py + r), (px - r, py)]
            pygame.draw.polygon(surf, color, pts)
            pygame.draw.polygon(surf, (0, 0, 0), pts, 1)
        elif self.shape == "star":
            pts = []
            for i in range(10):
                ang = -math.pi / 2 + i * math.pi / 5
                rr = r if i % 2 == 0 else r * 0.5
                pts.append((px + rr * math.cos(ang), py + rr * math.sin(ang)))
            pygame.draw.polygon(surf, color, pts)
            pygame.draw.polygon(surf, (0, 0, 0), pts, 1)

        scol = self._status_color()
        if scol is not None:
            pygame.draw.circle(surf, scol, (int(px), int(py)), r + 4, 2)
        if self.frozen:
            # cristalzinho acima do inimigo congelado, pra diferenciar de
            # "so lento" a distancia
            pts = [(px, py - r - 8), (px + 4, py - r - 3),
                   (px, py - r + 2), (px - 4, py - r - 3)]
            pygame.draw.polygon(surf, (225, 250, 255), pts)

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
