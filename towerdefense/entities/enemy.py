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
    HEAVY_ENEMY_ARMOR, EVASION_CHANCE, FLYING_DODGE_CHANCE,
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
        # onda em que este inimigo nasceu (guardado so para o sistema de
        # save: permite recalcular hp_mult/speed_mult ao recarregar uma
        # partida sem precisar persistir esses multiplicadores tambem)
        self.spawn_wave = wave
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
        # "voadores": esquiva FISICA e independente (ver `dodges`), e nao
        # colidem com espinhos plantados no chao (ver Game.update_spikes
        # e Tower._plant_spike, que ja excluem `flying` de proposito).
        self.flying = base.get("flying", False)
        # divisao ao morrer (Slime): ver Game.update, bloco "morreu por
        # dano de torre". None se este tipo nao divide.
        self.splits_into = base.get("splits_into")
        self.split_count = base.get("split_count", 0)
        self.split_hp_frac = base.get("split_hp_frac", 1.0)
        self.x, self.y, self.angle = map_path.point_at_distance(0)
        self.alive = True
        self.reached_end = False
        self._processed_death = False
        # "Segunda Chance" (meta-upgrade de gemas, ver systems/meta_upgrades):
        # cada inimigo so pode ser devolvido ao comeco do caminho UMA vez,
        # senao um upgrade forte deixaria certos inimigos imortais.
        self.used_second_chance = False

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

    def try_second_chance(self, prob):
        """Chamado pelo Game quando este inimigo chegou ao fim do
        caminho. Com chance `prob` (e so se ainda nao usou a sua unica
        chance), devolve o inimigo ao INICIO do caminho em vez de deixar
        a vida ser perdida. Retorna True se o inimigo foi devolvido
        (e portanto NAO deve tirar vida nem ser removido)."""
        if self.used_second_chance or prob <= 0:
            return False
        if random.random() >= prob:
            return False
        self.used_second_chance = True
        self.dist = 0.0
        self.reached_end = False
        self.alive = True
        self._processed_death = False
        self.x, self.y, self.angle = self.map_path.point_at_distance(0)
        return True

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
        """True se o acerto deve ser ignorado por esquiva. Duas fontes
        INDEPENDENTES, cada uma testada separadamente (um inimigo poderia
        no futuro ter as duas ao mesmo tempo):

        - camuflagem (`evasive`): torres com deteccao (`camo_detect`,
          caminho Observador) nunca erram por causa dela.
        - voo (`flying`): esquiva FISICA (esta fora de alcance confiavel
          de acerto, nao "escondido"), entao NENHUMA deteccao a anula --
          `detector` e ignorado aqui de proposito.
        """
        if self.evasive and not detector and random.random() < EVASION_CHANCE:
            return True
        if self.flying and random.random() < FLYING_DODGE_CHANCE:
            return True
        return False

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

    # ------------------------------------------------------------------
    # SILHUETAS por tipo (ver `shape` em ENEMY_TYPES) -- cada uma so
    # preenchimento + contorno, no mesmo espirito simples/geometrico do
    # resto do jogo (ver entities/tower.py). Recebem o CENTRO ja em
    # coordenadas de tela (px, py) e o raio base do tipo (r).
    # ------------------------------------------------------------------
    def _draw_regular_polygon(self, surf, px, py, r, sides, color, outline, rotation=0.0):
        pts = []
        for i in range(sides):
            ang = rotation + i * (2 * math.pi / sides)
            pts.append((px + r * math.cos(ang), py + r * math.sin(ang)))
        pygame.draw.polygon(surf, color, pts)
        pygame.draw.polygon(surf, outline, pts, 1)

    def _draw_arrow_tri(self, surf, px, py, r, color, outline):
        """Runner: triangulo apontando na direcao do movimento (self.angle),
        pra comunicar velocidade so pela silhueta."""
        ang = self.angle if self.angle is not None else -math.pi / 2
        tip = (px + math.cos(ang) * r * 1.3, py + math.sin(ang) * r * 1.3)
        back_ang1 = ang + math.pi * 0.78
        back_ang2 = ang - math.pi * 0.78
        p1 = (px + math.cos(back_ang1) * r, py + math.sin(back_ang1) * r)
        p2 = (px + math.cos(back_ang2) * r, py + math.sin(back_ang2) * r)
        pts = [tip, p1, p2]
        pygame.draw.polygon(surf, color, pts)
        pygame.draw.polygon(surf, outline, pts, 1)

    def _draw_swarm_pair(self, surf, px, py, r, color, outline):
        """Swarm: dois losangos pequenos colados lado a lado -- sugere
        "vem em grupo" mesmo quando so um esta sendo desenhado."""
        off = r * 0.62
        for cx in (px - off, px + off):
            rr = r * 0.72
            pts = [(cx, py - rr), (cx + rr, py), (cx, py + rr), (cx - rr, py)]
            pygame.draw.polygon(surf, color, pts)
            pygame.draw.polygon(surf, outline, pts, 1)

    def _draw_phantom_ring(self, surf, px, py, r, color, outline):
        """Phantom: anel VAZADO (nao preenchido) com pontinhos internos --
        parece "instavel/translucido", condizente com a camuflagem."""
        layer = pygame.Surface((r * 2 + 6, r * 2 + 6), pygame.SRCALPHA)
        cx, cy = r + 3, r + 3
        pygame.draw.circle(layer, (*color, 90), (cx, cy), r)
        pygame.draw.circle(layer, (*color, 230), (cx, cy), r, 2)
        for i in range(4):
            ang = i * (math.pi / 2) + 0.4
            dx, dy = math.cos(ang) * r * 0.45, math.sin(ang) * r * 0.45
            pygame.draw.circle(layer, (*color, 255), (int(cx + dx), int(cy + dy)), 2)
        surf.blit(layer, (px - cx, py - cy))
        pygame.draw.circle(surf, outline, (int(px), int(py)), r, 1)

    def _draw_bird(self, surf, px, py, r, color, outline):
        """Voador: silhueta em "V" (duas asas abertas pra tras, como um
        passaro visto de cima), alinhada com a direcao do movimento --
        formato bem mais reconhecivel a distancia do que um losango
        alongado, e nao se confunde com nenhuma silhueta terrestre."""
        ang = self.angle if self.angle is not None else -math.pi / 2
        cos_a, sin_a = math.cos(ang), math.sin(ang)

        def rot(lx, ly):
            return (px + lx * cos_a - ly * sin_a, py + lx * sin_a + ly * cos_a)

        nose = rot(r * 1.15, 0)
        wing_tip1 = rot(-r * 1.05, r * 1.3)
        wing_tip2 = rot(-r * 1.05, -r * 1.3)
        notch = rot(-r * 0.35, 0)  # reentrancia central: da o formato de "V"/asas
        pts = [nose, wing_tip1, notch, wing_tip2]
        pygame.draw.polygon(surf, color, pts)
        pygame.draw.polygon(surf, outline, pts, 1)
        # sombra elipsoide no chao (reforca a leitura de "esta no ar")
        shadow = pygame.Surface((int(r * 2.4), int(r * 1.1)), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (10, 10, 14, 70), shadow.get_rect())
        surf.blit(shadow, (px - r * 1.2, py + r * 0.9))

    def _draw_slime_blob(self, surf, px, py, r, color, outline):
        """Slime: contorno ONDULADO (nao um circulo perfeito), pra parecer
        gosma -- mesmo visual pro slime grande e pros filhotes menores
        (so o raio muda), deixando claro que sao "a mesma coisa" em
        tamanhos diferentes."""
        bumps = 8
        pts = []
        for i in range(bumps):
            ang = i * (2 * math.pi / bumps)
            wobble = 1.0 + 0.12 * math.sin(ang * 3 + self.dist * 0.01)
            pts.append((px + r * wobble * math.cos(ang), py + r * wobble * math.sin(ang)))
        pygame.draw.polygon(surf, color, pts)
        pygame.draw.polygon(surf, outline, pts, 1)
        # brilho pequeno no canto: da uma sensacao de "superficie molhada"
        hl_r = max(1, int(r * 0.22))
        hl_color = tuple(min(255, c + 60) for c in color)
        pygame.draw.circle(surf, hl_color, (int(px - r * 0.35), int(py - r * 0.35)), hl_r)

    def draw(self, surf, offset):
        ox, oy = offset
        px, py = self.x + ox, self.y + oy
        r = self.radius
        color = (255, 255, 255) if self.flash > 0 else self.color
        outline = (0, 0, 0)
        shape = self.shape

        if shape == "circle":
            pygame.draw.circle(surf, color, (int(px), int(py)), r)
            pygame.draw.circle(surf, outline, (int(px), int(py)), r, 1)
        elif shape == "square":
            rect = pygame.Rect(0, 0, r * 1.8, r * 1.8)
            rect.center = (px, py)
            pygame.draw.rect(surf, color, rect, border_radius=4)
            pygame.draw.rect(surf, outline, rect, 2, border_radius=4)
        elif shape == "diamond":
            pts = [(px, py - r), (px + r, py), (px, py + r), (px - r, py)]
            pygame.draw.polygon(surf, color, pts)
            pygame.draw.polygon(surf, outline, pts, 1)
        elif shape == "star":
            pts = []
            for i in range(10):
                ang = -math.pi / 2 + i * math.pi / 5
                rr = r if i % 2 == 0 else r * 0.5
                pts.append((px + rr * math.cos(ang), py + rr * math.sin(ang)))
            pygame.draw.polygon(surf, color, pts)
            pygame.draw.polygon(surf, outline, pts, 1)
        elif shape == "arrow_tri":
            self._draw_arrow_tri(surf, px, py, r, color, outline)
        elif shape == "swarm_pair":
            self._draw_swarm_pair(surf, px, py, r, color, outline)
        elif shape == "hexagon":
            self._draw_regular_polygon(surf, px, py, r, 6, color, outline)
        elif shape == "octagon":
            self._draw_regular_polygon(surf, px, py, r, 8, color, outline)
        elif shape == "phantom_ring":
            self._draw_phantom_ring(surf, px, py, r, color, outline)
        elif shape == "bird":
            self._draw_bird(surf, px, py, r, color, outline)
        elif shape == "slime_blob":
            self._draw_slime_blob(surf, px, py, r, color, outline)
        else:
            pygame.draw.circle(surf, color, (int(px), int(py)), r)
            pygame.draw.circle(surf, outline, (int(px), int(py)), r, 1)

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
