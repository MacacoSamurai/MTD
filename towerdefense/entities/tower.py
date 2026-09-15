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


def draw_tower_shape(surf, cx, cy, ttype, level=1, angle=None, radius=None, show_level=False):
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
    color = tower_color(level)
    if radius is None:
        radius = (19 + min(level, 10) * 1.1) * _SIZE_SCALE.get(ttype, _DEFAULT_SIZE_SCALE)
    outline = _shade(color, -0.6)

    ang = angle if angle is not None else _NEUTRAL_ANGLE
    body_rotation = ang - _NEUTRAL_ANGLE
    shape = TOWER_TYPES[ttype]["tower_shape"]
    bspec = BARREL_SPECS.get(ttype, _DEFAULT_BARREL)

    # cano: mesmo desenho "por baixo" usado no jogo de verdade -- ver
    # comentario longo em Tower.draw sobre a ordem cano -> base -> corpo.
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
        gx, gy = int(gx), int(gy)

        color = tower_color(self.level)
        # raio base reduzido (torres menores no geral) + multiplicador por
        # tipo (_SIZE_SCALE) -- a sniper encolhe mais que o resto.
        radius = (19 + min(self.level, 10) * 1.1) * _SIZE_SCALE.get(self.ttype, _DEFAULT_SIZE_SCALE)

        # range indicator quando arrastando ou hover
        if dragging_this:
            range_surf = pygame.Surface((self.range * 2, self.range * 2), pygame.SRCALPHA)
            pygame.draw.circle(range_surf, (*color, 40), (self.range, self.range), self.range)
            pygame.draw.circle(range_surf, (*color, 120), (self.range, self.range), self.range, 2)
            surf.blit(range_surf, (gx - self.range, gy - self.range))

        # mira: quem gira e a TORRE INTEIRA (base + corpo + cano, como um
        # bloco rigido), nao um cano sozinho girando sobre um corpo parado.
        # `ang` e a direcao do alvo (ou a pose neutra, pra cima, sem alvo) --
        # ver comentario de _NEUTRAL_ANGLE e de draw_tower_shape.
        if self.target is not None and self.target.alive:
            ang = math.atan2(self.target.y - gy, self.target.x - gx)
        else:
            ang = None

        # Enquanto arrastando, a torre e desenhada numa CAMADA separada
        # (surface propria com alpha) e so no final colada com
        # transparencia em cima do jogo -- em vez de pintar direto e
        # totalmente opaco na `surf` principal. Sem isso, ao passar a
        # torre arrastada por cima de uma vizinha, a base/prato escuro
        # (opaco) cobria a torre de baixo com um corte duro e sem
        # suavidade, dando a impressao de "borda errada" na sobreposicao.
        # Com alpha, a sobreposicao fica um efeito "fantasma" translucido,
        # legivel e sem corte abrupto.
        if dragging_this:
            margin = int(radius * 2.6) + 40
            layer = pygame.Surface((margin * 2, margin * 2), pygame.SRCALPHA)
            lx, ly = margin, margin
            target = layer
        else:
            lx, ly = gx, gy
            target = surf

        # corpo/base/cano/nivel: nucleo de aparencia compartilhado com
        # qualquer preview de UI (ver draw_tower_shape acima) -- assim a
        # torre no grid e o card de compra/ghost de arrasto nunca ficam
        # dessincronizados visualmente.
        draw_tower_shape(target, lx, ly, self.ttype, self.level, angle=ang,
                          radius=radius, show_level=True)

        if dragging_this:
            pygame.draw.circle(target, COL_MERGE_GLOW, (lx, ly), int(radius) + 10, 3)
            layer.set_alpha(215)
            surf.blit(layer, (gx - margin, gy - margin))
