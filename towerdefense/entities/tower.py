"""Torres: helpers de nivel (cor/nome), a classe Tower e seu merge/upgrade."""

import math
import random

import pygame

from ..config import (
    TOWER_TYPES, TOWER_LEVEL_COLORS, TOWER_LEVEL_NAMES,
    GRID_ORIGIN_X, GRID_ORIGIN_Y, CELL_SIZE, COL_MERGE_GLOW,
    AURA_PULSE_INTERVAL, BURST_INTERVAL, SHOT_SPREAD,
)
from ..fonts import get_font
from .. import upgrades as up
from ..systems import combat
from ..systems.vfx import Field
from .projectile import Projectile
from .spike import Spike


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


def spec_name(ttype, tiers):
    """Nome de exibicao da especializacao: nome do tier mais alto comprado
    (ex.: "Canhao Demolidor"), ou None se a torre ainda e basica."""
    if tiers is None:
        return None
    mp = up.main_path(tiers)
    if mp is None:
        return None
    return up.tier_def(ttype, mp, tiers[mp])["name"]


def _shade(color, amount):
    """Clareia (amount > 0) ou escurece (amount < 0) uma cor RGB.
    Copia minuscula de ui/theme.shade: entities/ nao deve depender de
    ui/ (a dependencia e sempre ui -> entities, nunca o contrario), entao
    esse helper de poucas linhas fica duplicado aqui de proposito."""
    r, g, b = color[0], color[1], color[2]
    if amount >= 0:
        r = min(255, int(r + (255 - r) * amount))
        g = min(255, int(g + (255 - g) * amount))
        b = min(255, int(b + (255 - b) * amount))
    else:
        f = 1 + amount
        r = max(0, int(r * f))
        g = max(0, int(g * f))
        b = max(0, int(b * f))
    return (r, g, b)


def _polygon_points(cx, cy, radius, sides, rotation, y_scale=1.0, extra_rotation=0.0):
    """Vertices de um poligono regular -- forma limpa e geometrica (sem
    nenhuma perturbacao/jitter: torres tortas/rabiscadas nao sao o
    visual desejado, cada tipo so precisa de uma silhueta propria e
    reta pra ser reconhecivel de longe).

    `extra_rotation` gira o poligono inteiro como corpo rigido (usado
    pra torre acompanhar a mira). E aplicado DEPOIS do y_scale, como uma
    rotacao 2D de verdade sobre o ponto ja no referencial "de fabrica"
    da forma -- se aplicasse antes (ou so somasse ao angulo de cada
    vertice junto com o y_scale), formas assimetricas como o diamond
    ficariam esticando/deformando ao girar em vez de girar rigidas."""
    cos_e, sin_e = math.cos(extra_rotation), math.sin(extra_rotation)
    pts = []
    for i in range(sides):
        ang = rotation + i * (2 * math.pi / sides)
        lx = math.cos(ang) * radius
        ly = math.sin(ang) * radius * y_scale
        rx = lx * cos_e - ly * sin_e
        ry = lx * sin_e + ly * cos_e
        pts.append((cx + rx, cy + ry))
    return pts


def _shape_points(shape, cx, cy, radius, extra_rotation=0.0):
    """Vertices de cada silhueta de torre (None para circulo, que usa
    pygame.draw.circle diretamente). `extra_rotation` gira a silhueta
    toda -- ver `_polygon_points`."""
    if shape == "square":  # canhao pesado
        return _polygon_points(cx, cy, radius * 1.05, 4, math.pi / 4, extra_rotation=extra_rotation)
    if shape == "triangle":  # torre de flechas
        return _polygon_points(cx, cy, radius * 1.15, 3, -math.pi / 2, extra_rotation=extra_rotation)
    if shape == "hexagon":  # torre de gelo
        return _polygon_points(cx, cy, radius, 6, math.pi / 6, extra_rotation=extra_rotation)
    if shape == "diamond":  # sniper
        return _polygon_points(cx, cy, radius * 1.15, 4, -math.pi / 2, y_scale=1.3, extra_rotation=extra_rotation)
    if shape == "circle":  # canhao
        return None
    if shape == "spikes":  # armadilheiro: estrela quebrada (8 pontas irregulares)
        pts = []
        cos_e, sin_e = math.cos(extra_rotation), math.sin(extra_rotation)
        for i in range(8):
            ang = i * (math.pi / 4)
            r = radius * (1.0 if i % 2 == 0 else 0.55)
            lx = math.cos(ang) * r
            ly = math.sin(ang) * r
            rx = lx * cos_e - ly * sin_e
            ry = lx * sin_e + ly * cos_e
            pts.append((cx + rx, cy + ry))
        return pts
    return _polygon_points(cx, cy, radius, 8, 0.0, extra_rotation=extra_rotation)  # fallback p/ tipo novo sem forma definida


def _draw_shape(surf, shape, cx, cy, radius, fill_color, outline_color=None, outline_width=0, extra_rotation=0.0):
    """Desenha uma silhueta (preenchimento + contorno opcional). Usada
    tanto pra "base" escura de apoio quanto pro corpo colorido por cima
    -- ambas com a MESMA forma, pra a base nunca aparecer como um
    circulo generico atras de torres quadradas/triangulares/etc (isso
    fazia elas parecerem borradas/arredondadas nos cantos). `extra_rotation`
    gira a silhueta pra acompanhar a mira (circulo ignora, e simetrico)."""
    pts = _shape_points(shape, cx, cy, radius, extra_rotation=extra_rotation)
    if pts is None:
        pygame.draw.circle(surf, fill_color, (cx, cy), radius)
        if outline_color is not None:
            pygame.draw.circle(surf, outline_color, (cx, cy), radius, outline_width)
    else:
        pygame.draw.polygon(surf, fill_color, pts)
        if outline_color is not None:
            pygame.draw.polygon(surf, outline_color, pts, outline_width)


# ----------------------------------------------------------------------------
# Mira/cano: cada tipo de torre tem uma proporcao propria, pra dar pra
# reconhecer o tipo so pelo cano sem precisar olhar a cor/forma do corpo.
# "length"/"near_w"/"far_w" sao fracoes do RAIO da torre (por isso o cano
# cresce em escala junto com a torre, nivel apos nivel). O cano comeca na
# borda da silhueta do corpo (ver _body_edge_dist) deslocado por "offset"
# (tambem fracao do raio; positivo empurra o cano pra FORA/ponta, negativo
# RECUA ele pra dentro/centro) -- so a partir dali ele se estende por
# "length".
#   canhao:        reto, tamanho medio, cano recuado um pouco
#   flecha:        cano curto e fino (arqueiro leve), avancado um pouco
#                   pra ponta
#   sniper:        cano fino e bem longo (precisao a distancia), recuado
#                   um pouco
#   canhao_pesado: base fina alargando MUITO na ponta (boca de trabuco),
#                   bem recuado pra ficar na borda da torre
#   gelo:          reto e mais GROSSO que o normal, mais comprido e
#                   recuado soh um pouco pro centro
#
# O CANO E FIXO NO CORPO (nao gira sozinho pra mirar): quem mira e a
# TORRE INTEIRA, girando como bloco rigido (corpo + base + cano) ate o
# cano apontar pro alvo -- ver Tower.draw. _NEUTRAL_ANGLE e a direcao
# "de fabrica" (torre parada, sem alvo, apontando pra cima) usada como
# referencia: a torre gira exatamente `ang - _NEUTRAL_ANGLE` a partir
# dessa pose neutra. Por isso o cano sempre nasce na mesma borda
# RELATIVA do corpo -- _body_edge_dist e sempre calculado com
# _NEUTRAL_ANGLE (nunca com o `ang` real), pois a rotacao do corpo ja
# absorve a diferenca.
# ----------------------------------------------------------------------------
_NEUTRAL_ANGLE = -math.pi / 2

BARREL_SPECS = {
    "canhao":        dict(length=0.80, near_w=0.35, far_w=0.35, offset=-0.12),
    "flecha":        dict(length=0.50, near_w=0.24, far_w=0.24, offset=0.44),
    "sniper":        dict(length=1.35, near_w=0.16, far_w=0.16, offset=-0.12),
    "canhao_pesado": dict(length=0.80, near_w=0.24, far_w=0.60, offset=-0.40),
    "gelo":          dict(length=0.85, near_w=0.50, far_w=0.50, offset=-0.08),
}
_DEFAULT_BARREL = dict(length=0.72, near_w=0.30, far_w=0.30, offset=0.0)

# Multiplicador de tamanho por tipo, aplicado sobre o raio base da torre
# (ver Tower.draw). 1.0 = tamanho padrao; a sniper e reduzida mais que o
# resto (mais leve/precisa) e o canhao pesado e um pouco maior que o
# resto (mais imponente/pesado, condizente com o splash e o dano dele).
_SIZE_SCALE = {
    "sniper": 0.80,
    "canhao_pesado": 1.10,
}
_DEFAULT_SIZE_SCALE = 1.0


def _regular_polygon_edge_dist(ang, rotation, sides, circumradius):
    """Distancia do centro ate a BORDA (nao o vertice) de um poligono
    regular, na direcao `ang` -- formula padrao apotema/cos(desvio ate
    o lado mais proximo)."""
    apothem = circumradius * math.cos(math.pi / sides)
    seg = 2 * math.pi / sides
    rel = (ang - rotation) % seg
    if rel > seg / 2:
        rel -= seg
    return apothem / math.cos(rel)


def _body_edge_dist(shape, radius, ang):
    """Distancia do centro da torre ate a borda da SUA silhueta, na
    direcao `ang` (o angulo em que o cano esta apontando). E o que faz
    o cano nascer sempre rente a frente do corpo, e nao flutuando perto
    do centro -- em qualquer forma e em qualquer angulo de mira."""
    if shape == "circle":
        return radius
    if shape == "square":
        return _regular_polygon_edge_dist(ang, math.pi / 4, 4, radius * 1.05)
    if shape == "triangle":
        return _regular_polygon_edge_dist(ang, -math.pi / 2, 3, radius * 1.15)
    if shape == "hexagon":
        return _regular_polygon_edge_dist(ang, math.pi / 6, 6, radius)
    if shape == "diamond":
        # losango (kite): meio-eixo horizontal "a" e vertical "b"
        # (y_scale 1.3 aplicado na forma) -- borda = 1/(|cos|/a + |sin|/b)
        a = radius * 1.15
        b = radius * 1.15 * 1.3
        return 1.0 / (abs(math.cos(ang)) / a + abs(math.sin(ang)) / b)
    if shape == "spikes":
        return radius * 0.8  # aproximacao (forma irregular); nunca desenha cano mesmo
    return _regular_polygon_edge_dist(ang, 0.0, 8, radius)


def _barrel_points(cx, cy, ang, radius, shape, spec):
    """Poligono reto (retangulo ou trapezio, conforme near_w/far_w) do
    cano apontado no angulo `ang`. Comeca na BORDA do corpo (nao no
    centro) e se estende por `spec['length']` (fracao do raio, entao
    acompanha a escala da torre)."""
    dx, dy = math.cos(ang), math.sin(ang)
    px, py = -dy, dx
    # borda calculada sempre no angulo neutro: o cano e fixo no corpo, e
    # e o corpo que gira ate essa borda apontar pra `ang` (ver comentario
    # acima de _NEUTRAL_ANGLE) -- entao a distancia relativa nunca muda.
    # "offset" desloca esse ponto de partida pra fora (positivo) ou pra
    # dentro/centro (negativo, "recuar"), fracao do raio da torre.
    r1 = _body_edge_dist(shape, radius, _NEUTRAL_ANGLE) + radius * spec.get("offset", 0.0)
    r2 = r1 + radius * spec["length"]
    w1, w2 = radius * spec["near_w"], radius * spec["far_w"]
    x1, y1 = cx + dx * r1, cy + dy * r1
    x2, y2 = cx + dx * r2, cy + dy * r2
    return [
        (x1 + px * w1, y1 + py * w1),
        (x2 + px * w2, y2 + py * w2),
        (x2 - px * w2, y2 - py * w2),
        (x1 - px * w1, y1 - py * w1),
    ]


def draw_tower_shape(surf, cx, cy, ttype, level=1, angle=None, radius=None,
                      show_level=False, tiers=None):
    """Desenha o visual "de verdade" de uma torre (base + corpo + cano +
    placa de nivel opcional) num ponto qualquer da tela, sem nenhuma logica
    de mira/alvo, arrasto ou indicador de alcance.

    Esse e o NUCLEO de aparencia compartilhado entre o desenho real da
    torre no grid (`Tower.draw`, que chama esta funcao) e qualquer preview
    de UI que precise mostrar "como a torre e" -- card de compra na loja,
    ghost seguindo o mouse durante o arrasto, etc. Ao usar esta funcao em
    vez de um icone generico (`ui/theme.draw_shape_icon`), qualquer ajuste
    futuro na aparencia da torre (cor por nivel, silhueta, cano, escala)
    aparece automaticamente em todo lugar que a use, sem precisar duplicar
    ou lembrar de atualizar cada preview manualmente.

    `angle` e a direcao (radianos) para onde o cano aponta; `None` usa a
    pose neutra (parada, apontando pra cima) -- a mesma usada quando uma
    torre real ainda nao tem alvo. `radius` permite forcar um tamanho
    (util pra icones pequenos de UI); se omitido, usa o mesmo calculo de
    tamanho por nivel/tipo do jogo de verdade."""
    cx, cy = int(cx), int(cy)
    # cor SEMPRE pela tabela de nivel (merge) -- a arvore de upgrades nao
    # tinge a torre, so muda a silhueta (tamanho, halo do tier 6 e os
    # marcadores de caminho desenhados mais abaixo).
    color = tower_color(level)
    if radius is None:
        radius = (19 + min(level, 10) * 1.1) * _SIZE_SCALE.get(ttype, _DEFAULT_SIZE_SCALE)
    # torres especializadas ficam um pouco maiores conforme sobem de tier
    # (a tier 6 e visivelmente "a super torre" da partida)
    if tiers is not None and max(tiers) > 0:
        radius *= 1.0 + 0.035 * max(tiers) + 0.012 * sum(tiers)
    outline = _shade(color, -0.6)

    # anel dourado pulsante marcando uma torre tier 6
    if tiers is not None and max(tiers) >= up.MAX_TIER:
        halo = pygame.Surface((int(radius * 3), int(radius * 3)), pygame.SRCALPHA)
        hc = (int(radius * 1.5), int(radius * 1.5))
        pygame.draw.circle(halo, (255, 225, 120, 55), hc, int(radius * 1.45))
        pygame.draw.circle(halo, (255, 225, 120, 170), hc, int(radius * 1.35), 3)
        surf.blit(halo, (cx - radius * 1.5, cy - radius * 1.5))

    ang = angle if angle is not None else _NEUTRAL_ANGLE
    body_rotation = ang - _NEUTRAL_ANGLE
    shape = TOWER_TYPES[ttype]["tower_shape"]

    # cano: mesmo desenho "por baixo" usado no jogo de verdade -- ver
    # comentario longo em Tower.draw sobre a ordem cano -> base -> corpo.
    # A torre de espinhos nao mira/atira, entao nao tem cano nenhum.
    if shape != "spikes":
        bspec = BARREL_SPECS.get(ttype, _DEFAULT_BARREL)
        bpts = _barrel_points(cx, cy, ang, radius, shape, bspec)
        pygame.draw.polygon(surf, outline, bpts)
        pygame.draw.polygon(surf, (15, 15, 18), bpts, 2)

    _draw_shape(surf, shape, cx, cy, radius + 4, (24, 26, 32), extra_rotation=body_rotation)
    _draw_shape(surf, shape, cx, cy, radius, color, outline_color=outline, outline_width=3,
                extra_rotation=body_rotation)

    if show_level:
        font = get_font(12, bold=True)
        txt = font.render(str(level), True, (24, 24, 28))
        tag_w = txt.get_width() + 12
        tag_h = txt.get_height() + 4
        tag_rect = pygame.Rect(0, 0, tag_w, tag_h)
        tag_rect.center = (cx, cy + radius + 9)
        pygame.draw.rect(surf, color, tag_rect, border_radius=tag_h // 2)
        pygame.draw.rect(surf, outline, tag_rect, 2, border_radius=tag_h // 2)
        surf.blit(txt, txt.get_rect(center=tag_rect.center))

    return radius


class Tower:
    """Uma torre no grid.

    Duas progressoes convivem e sao INDEPENDENTES:

    - `level` -- vem do MERGE (arrastar uma torre sobre outra igual).
      Escala as stats base de forma generica e nao tem teto.
    - `tiers` -- os tres caminhos da arvore de upgrades (ver
      `towerdefense/upgrades.py`), comprados com ouro no painel lateral.
      E o que da IDENTIDADE a torre: efeitos, comportamento de tiro,
      auras e (no tier 6) uma habilidade automatica.

    O merge multiplica; a arvore especializa. Uma torre 5-2-0 de nivel 4
    e uma torre de nivel 4 com os mods dos 7 upgrades comprados.
    """

    def __init__(self, col, row, ttype="canhao", level=1, tiers=None, invested=0):
        self.col = col
        self.row = row
        self.ttype = ttype
        self.level = level
        self.tiers = list(tiers) if tiers else [0, 0, 0]
        # ouro total gasto nesta torre (compra + upgrades de caminho +, em
        # merges, o investimento da torre absorvida) -- e sobre isso que
        # `Game.sell_tower` calcula o reembolso ao vender. Nao inclui o
        # custo de compra caso a torre ja nasca com nivel > 1 por meta
        # upgrade (esse bonus e de graca, entao nao teria por que "vender").
        self.invested = invested
        self.cooldown = 0.0
        self.target = None
        # rajada: tiros extras do MESMO ataque, disparados com um
        # intervalinho entre si (mod `burst_add`)
        self.pending_burst = 0
        self.burst_timer = 0.0
        self.aura_timer = 0.0
        self.elemental_index = 0
        # habilidade tier 6 (gerida por systems/abilities.py)
        self.ability_cd = 0.0
        self.ability_active = 0.0
        self.ability_ready_for = 0.0  # ha quanto tempo esta pronta e a IA segura
        self.ability_tick = 0.0
        self.ability_eval_timer = 0.0
        # espinhos plantados por ESTA torre (so usado por ttype="espinhos";
        # ver Spike em entities/spike.py e Game.update_spikes)
        self.spikes = []
        self.recalc_stats()
        # posicao visual (para animacao de drag)
        self.drag_offset = (0, 0)
        self.being_dragged = False

    # ------------------------------------------------------------------
    # STATS
    # ------------------------------------------------------------------
    def recalc_stats(self):
        spec = TOWER_TYPES[self.ttype]
        lvl = self.level
        growth = 1.55 ** (lvl - 1)
        self.range = spec["base_range"] + (lvl - 1) * 14
        self.damage = spec["base_damage"] * growth
        self.fire_rate = max(0.10, spec["base_rate"] - (lvl - 1) * 0.03)
        self.splash = 0.0
        sfl = spec["splash_from_lvl"]
        if sfl is not None and lvl >= sfl:
            self.splash = spec["splash_base"] + (lvl - sfl) * spec["splash_step"]
        self.armor_pierce = spec.get("armor_pierce", False)
        self.proj_speed = spec["proj_speed"]

        # --- mods da arvore de upgrades ---
        self.mods = up.mods_for(self.ttype, self.tiers)
        m = self.mods
        self.damage *= m.get("damage_mult", 1.0)
        self.range *= m.get("range_mult", 1.0)
        self.fire_rate = max(0.04, self.fire_rate * m.get("rate_mult", 1.0))
        self.splash = (self.splash + m.get("splash_add", 0.0)) * m.get("splash_mult", 1.0)
        self.proj_speed *= m.get("proj_speed_mult", 1.0)
        if m.get("armor_pierce", False):
            self.armor_pierce = True
        self.shots = 1 + int(m.get("shots_add", 0))
        self.burst = 1 + int(m.get("burst_add", 0))
        self.aura_radius = self.range * m.get("aura_radius_mult", 0.0)
        self.effects = self.build_effects()
        # compatibilidade com a UI antiga de tooltip (menus.draw_tower_range_hover)
        self.slow = self.effects.get("slow")

        # --- torre "espinhos": nao mira/atira, planta no caminho ---
        if spec.get("no_targeting", False):
            self.plant_range = self.range  # reaproveita `range` como raio de plantio
            self.spike_charges = int(spec["base_charges"] + (lvl - 1) // 2
                                      + m.get("spike_charges_add", 0))
            self.spike_max = int(spec["base_max_spikes"] + (lvl - 1) // 3
                                  + m.get("spike_max_add", 0))
            self.plant_range *= m.get("spike_range_mult", 1.0)
            self.plant_count = 1 + int(m.get("spike_plant_count_add", 0))

    def build_effects(self):
        """Traduz os `mods` (percentuais/fracoes) no dicionario de efeitos
        com valores ABSOLUTOS que `systems/combat.py` consome. Fracoes de
        dano-por-segundo viram dps de verdade aqui, entao combat.py nunca
        precisa saber quanto a torre bate."""
        m = self.mods
        d = self.damage
        spec = TOWER_TYPES[self.ttype]
        eff = {
            "splash": self.splash,
            "pierce": int(m.get("pierce_add", 0)),
            "ricochet": int(m.get("ricochet", 0)),
            "homing": bool(m.get("homing", False)),
            "armor_pierce": self.armor_pierce,
            "armor_shred": m.get("armor_shred", 0.0),
            "crit_chance": m.get("crit_chance", 0.0),
            "crit_mult": m.get("crit_mult", 2.0),
            "heavy_mult": m.get("heavy_mult", 1.0),
            "small_mult": m.get("small_mult", 1.0),
            "wounded_mult": m.get("wounded_mult", 1.0),
            "bonus_vs_frozen": m.get("bonus_vs_frozen", 1.0),
            "execute_small": bool(m.get("execute_small", False)),
            "camo_detect": bool(m.get("camo_detect", False)),
            "frag_count": int(m.get("frag_count", 0)),
            "frag_damage": m.get("frag_damage", 0.35),
            "secondary_blasts": int(m.get("secondary_blasts", 0)),
            "frozen_explode": m.get("frozen_explode", 0.0),
            "freeze_chance": m.get("freeze_chance", 0.0),
            "freeze_time": m.get("freeze_time", 1.0),
        }
        if m.get("dot_dps"):
            eff["dot_dps"] = m["dot_dps"] * d
            eff["dot_time"] = m.get("dot_time", 3.0)
        if m.get("burn_dps"):
            eff["burn_dps"] = m["burn_dps"] * d
            eff["burn_time"] = m.get("burn_time", 3.0)
        if m.get("poison_dps"):
            eff["poison_dps"] = m["poison_dps"] * d
            eff["poison_time"] = m.get("poison_time", 4.0)
            eff["poison_stack_max"] = m.get("poison_stack_max", 3)
        if m.get("mark_on_hit"):
            eff["mark_on_hit"] = True
            eff["mark_amp"] = m.get("mark_amp", 0.2)
            eff["mark_time"] = m.get("mark_time", 3.0)

        # lentidao: a da torre de gelo (`always_slow`, sempre aplica) e a
        # dos upgrades (que pode ter chance < 1) se resolvem no mesmo
        # campo -- vence a mais forte, e a chance vira 100% se a torre ja
        # desacelera por natureza.
        base_slow = spec.get("always_slow")
        factor = m.get("slow_factor")
        duration = m.get("slow_time", 0.0)
        chance = m.get("slow_chance", 1.0)
        if base_slow is not None:
            factor = min(factor, base_slow[0]) if factor else base_slow[0]
            duration = max(duration, base_slow[1])
            chance = 1.0
        if factor is not None and factor < 1.0:
            eff["slow"] = (factor, max(duration, 1.2), chance)
        return eff

    def shot_effects(self):
        """Efeitos deste disparo especifico. So difere de `self.effects`
        no caminho Arqueiro Tatico: o "Arsenal Elemental" ALTERNA fogo,
        gelo e veneno tiro a tiro (em vez de aplicar os tres), e por isso
        precisa de uma versao filtrada por disparo."""
        if not self.mods.get("elemental_cycle") or self.mods.get("elemental_all"):
            return self.effects
        eff = dict(self.effects)
        element = self.elemental_index % 3
        if element != 0:
            eff.pop("burn_dps", None)
        if element != 1:
            eff.pop("slow", None)
            eff["freeze_chance"] = 0.0
        if element != 2:
            eff.pop("poison_dps", None)
        return eff

    # ------------------------------------------------------------------
    # ARVORE DE UPGRADES
    # ------------------------------------------------------------------
    @property
    def tier6_path(self):
        """Indice do caminho em que a torre e tier 6, ou None."""
        for i, t in enumerate(self.tiers):
            if t >= up.MAX_TIER:
                return i
        return None

    @property
    def has_ability(self):
        return self.tier6_path is not None

    def ability(self):
        p = self.tier6_path
        return None if p is None else up.ability_def(self.ttype, p)

    def next_tier_cost(self, path_index):
        tier = self.tiers[path_index] + 1
        if tier > up.MAX_TIER:
            return None
        return up.tier_cost(self.ttype, tier)

    def buy_path(self, path_index):
        self.tiers[path_index] += 1
        self.recalc_stats()
        if self.has_ability:
            ab = self.ability()
            # entra em cooldown ao nascer: a super torre nao dispara a
            # habilidade no mesmo instante da compra
            self.ability_cd = ab["cooldown"] * 0.5

    def display_name(self):
        return spec_name(self.ttype, self.tiers) or TOWER_TYPES[self.ttype]["label"]

    def color(self):
        return tower_color(self.level)

    def grid_pos(self):
        gx = GRID_ORIGIN_X + self.col * CELL_SIZE + CELL_SIZE // 2
        gy = GRID_ORIGIN_Y + self.row * CELL_SIZE + CELL_SIZE // 2
        return gx, gy

    # ------------------------------------------------------------------
    # COMBATE
    # ------------------------------------------------------------------
    def _acquire_target(self, world):
        """Escolhe alvo dentro do alcance. O padrao e "o que esta mais
        longe no caminho" (prestes a vazar); com o mod `target_priority`
        = "strongest" a torre passa a cacar o inimigo mais perigoso, que
        e a identidade dos caminhos Cacador/Executor/Deus do Tiro."""
        gx, gy = self.grid_pos()
        r2 = self.range * self.range
        strongest = self.mods.get("target_priority") == "strongest"
        detector = self.effects.get("camo_detect", False)
        total = world.map_path.total_len
        best = None
        best_score = -1.0
        for e in world.enemies:
            if not e.alive:
                continue
            if e.evasive and not detector:
                # sem deteccao a torre ainda atira, mas prefere quem ela
                # consegue acertar de forma confiavel
                pass
            if (e.x - gx) ** 2 + (e.y - gy) ** 2 > r2:
                continue
            score = e.danger_score(total) if strongest else e.dist
            if score > best_score:
                best = e
                best_score = score
        return best

    def update(self, dt, world):
        if self.being_dragged:
            return
        self.cooldown -= dt

        if TOWER_TYPES[self.ttype].get("no_targeting", False):
            self._update_spikes(dt, world)
            return

        self._update_aura(dt, world)

        gx, gy = self.grid_pos()
        if self.target is not None:
            if (not self.target.alive or
                    math.hypot(self.target.x - gx, self.target.y - gy) > self.range):
                self.target = None
        if self.target is None:
            self.target = self._acquire_target(world)

        # rajada em andamento (tiros extras do mesmo ataque)
        if self.pending_burst > 0:
            self.burst_timer -= dt
            if self.burst_timer <= 0:
                self.pending_burst -= 1
                self.burst_timer = BURST_INTERVAL
                self._fire_volley(world)

        if self.target is not None and self.cooldown <= 0:
            self.cooldown = self.fire_rate
            self._fire_volley(world)
            if self.burst > 1:
                self.pending_burst = self.burst - 1
                self.burst_timer = BURST_INTERVAL

    def _fire_volley(self, world):
        """Um "ataque": `self.shots` projeteis simultaneos, em leque."""
        if self.target is None or not self.target.alive:
            self.target = self._acquire_target(world)
            if self.target is None:
                return
        gx, gy = self.grid_pos()
        eff = self.shot_effects()
        self.elemental_index += 1
        color = self.color()
        spec = TOWER_TYPES[self.ttype]
        base_angle = math.atan2(self.target.y - gy, self.target.x - gx)
        n = self.shots
        for i in range(n):
            offset = 0.0 if n == 1 else (i - (n - 1) / 2) * SHOT_SPREAD
            world.projectiles.append(Projectile(
                gx, gy, self.target, self.proj_speed, self.damage, color, eff,
                shape=spec["proj_shape"], angle=base_angle + offset,
                max_dist=self.range * 1.8,
            ))

    def _update_spikes(self, dt, world):
        """Torre "espinhos": em vez de mirar/atirar, planta um (ou mais,
        com o upgrade certo) espinho novo no caminho a cada cooldown, se
        ainda nao estiver no limite de espinhos simultaneos vivos."""
        for sp in self.spikes:
            sp.update(world, dt)
        self.spikes = [sp for sp in self.spikes if sp.alive]

        if self.cooldown > 0:
            return
        self.cooldown = self.fire_rate
        if len(self.spikes) >= self.spike_max:
            return
        for _ in range(self.plant_count):
            if len(self.spikes) >= self.spike_max:
                break
            self._plant_spike(world)

    def _plant_spike(self, world):
        """Escolhe uma celula aleatoria do caminho dentro de `plant_range`
        que ainda nao tenha um espinho VIVO desta torre, e planta um novo
        ali. Se nenhuma celula livre existir no alcance, nao faz nada
        (tenta de novo no proximo cooldown)."""
        gx, gy = self.grid_pos()
        r2 = self.plant_range * self.plant_range
        occupied = {(sp.col, sp.row) for sp in self.spikes}
        candidates = []
        for (col, row) in world.map_path.cell_set:
            if (col, row) in occupied:
                continue
            cx = GRID_ORIGIN_X + col * CELL_SIZE + CELL_SIZE // 2
            cy = GRID_ORIGIN_Y + row * CELL_SIZE + CELL_SIZE // 2
            if (cx - gx) ** 2 + (cy - gy) ** 2 <= r2:
                candidates.append((col, row))
        if not candidates:
            return
        col, row = random.choice(candidates)
        self.spikes.append(Spike(col, row, self.spike_charges, self.damage, self))

    def _update_aura(self, dt, world):
        """Auras (Era Glacial, Campo de Permafrost, Olho de Deus): em vez
        de um efeito continuo por frame, pulsam a cada
        AURA_PULSE_INTERVAL aplicando status de duracao curta. Fica muito
        mais barato e o efeito pratico e o mesmo -- quem fica dentro da
        area nunca sai do debuff."""
        if self.aura_radius <= 0:
            return
        self.aura_timer -= dt
        if self.aura_timer > 0:
            return
        self.aura_timer = AURA_PULSE_INTERVAL
        m = self.mods
        gx, gy = self.grid_pos()
        r2 = self.aura_radius * self.aura_radius
        hold = AURA_PULSE_INTERVAL * 2.5  # status dura ate o proximo pulso
        color = self.color()
        world.vfx.append(Field(gx, gy, self.aura_radius, color, life=AURA_PULSE_INTERVAL * 1.6))
        for e in world.enemies:
            if not e.alive:
                continue
            if (e.x - gx) ** 2 + (e.y - gy) ** 2 > r2:
                continue
            if m.get("aura_slow_factor"):
                e.apply_slow(m["aura_slow_factor"], hold)
            if m.get("aura_vuln_amp"):
                e.apply_mark(m["aura_vuln_amp"], hold)
            if m.get("aura_mark_amp"):
                e.apply_mark(m["aura_mark_amp"], hold)
            if m.get("aura_armor_shred"):
                e.apply_shred(m["aura_armor_shred"], hold)
            if m.get("aura_freeze_chance") and random.random() < m["aura_freeze_chance"]:
                e.apply_freeze(m.get("freeze_time", 1.0))
            if m.get("aura_damage_dps"):
                combat.resolve_hit(world, e, self.damage * m["aura_damage_dps"] * AURA_PULSE_INTERVAL,
                                   {"armor_pierce": True}, ignore_dodge=True)

    # ------------------------------------------------------------------
    # DESENHO
    # ------------------------------------------------------------------
    def draw(self, surf, mouse_pos, dragging_this):
        if dragging_this:
            gx, gy = mouse_pos
        else:
            gx, gy = self.grid_pos()
        gx, gy = int(gx), int(gy)

        color = self.color()
        radius = (19 + min(self.level, 10) * 1.1) * _SIZE_SCALE.get(self.ttype, _DEFAULT_SIZE_SCALE)

        # range indicator quando arrastando ou hover
        if dragging_this:
            range_surf = pygame.Surface((self.range * 2, self.range * 2), pygame.SRCALPHA)
            pygame.draw.circle(range_surf, (*color, 40), (self.range, self.range), self.range)
            pygame.draw.circle(range_surf, (*color, 120), (self.range, self.range), self.range, 2)
            surf.blit(range_surf, (gx - self.range, gy - self.range))

        # mira: quem gira e a TORRE INTEIRA (base + corpo + cano, como um
        # bloco rigido), nao um cano sozinho girando sobre um corpo parado.
        if self.target is not None and self.target.alive:
            ang = math.atan2(self.target.y - gy, self.target.x - gx)
        else:
            ang = None

        # Enquanto arrastando, a torre e desenhada numa CAMADA separada
        # (surface propria com alpha) e so no final colada com
        # transparencia em cima do jogo -- sem isso a base opaca cortava
        # a torre de baixo com uma borda dura ao passar por cima dela.
        if dragging_this:
            margin = int(radius * 3.2) + 40
            layer = pygame.Surface((margin * 2, margin * 2), pygame.SRCALPHA)
            lx, ly = margin, margin
            target = layer
        else:
            lx, ly = gx, gy
            target = surf

        drawn_r = draw_tower_shape(target, lx, ly, self.ttype, self.level, angle=ang,
                                    radius=radius, show_level=True, tiers=self.tiers)

        # marcador dos caminhos comprados: tres tracinhos curtos abaixo da
        # torre, um por caminho, com o comprimento proporcional ao tier.
        # E a leitura rapida de "no que essa torre foi investida" sem
        # precisar clicar nela.
        if max(self.tiers) > 0:
            bw = 9
            total_w = bw * 3 + 4
            bx = lx - total_w // 2
            by = ly + drawn_r + 17
            for i, tier in enumerate(self.tiers):
                pc = up.PATH_COLORS[self.ttype][i]
                col = pc if tier > 0 else (60, 64, 74)
                h = 2 + tier
                pygame.draw.rect(target, col, (bx + i * (bw + 2), by - h, bw, h),
                                 border_radius=1)

        # anel de cooldown da habilidade tier 6
        if self.has_ability and not dragging_this:
            self._draw_ability_ring(target, lx, ly, drawn_r)

        if dragging_this:
            pygame.draw.circle(target, COL_MERGE_GLOW, (lx, ly), int(radius) + 10, 3)
            layer.set_alpha(215)
            surf.blit(layer, (gx - margin, gy - margin))

    def _draw_ability_ring(self, surf, cx, cy, radius):
        ab = self.ability()
        r = int(radius + 10)
        if self.ability_active > 0:
            pygame.draw.circle(surf, (255, 255, 180), (cx, cy), r, 3)
            return
        frac = 1.0 - max(0.0, min(1.0, self.ability_cd / ab["cooldown"]))
        if frac >= 1.0:
            pygame.draw.circle(surf, (255, 225, 120), (cx, cy), r, 2)
            return
        # arco de recarga (desenhado como pontinhos: pygame.draw.arc fica
        # serrilhado e sumido em raios pequenos como esse)
        steps = 28
        for i in range(int(steps * frac)):
            a = -math.pi / 2 + (i / steps) * math.tau
            px = cx + math.cos(a) * r
            py = cy + math.sin(a) * r
            pygame.draw.circle(surf, (255, 225, 120), (int(px), int(py)), 2)
