"""Efeitos visuais descartaveis (explosoes, ondas de choque, marcadores).

E um sistema deliberadamente burro: uma lista de objetos com `update` e
`draw` que se apagam sozinhos quando `life` acaba. Nenhum deles causa
dano -- o dano ja foi resolvido por quem criou o efeito (ver
`systems/combat.py`); aqui e so feedback pro jogador entender o que
acabou de acontecer, o que importa muito num jogo onde as habilidades
tier 6 disparam SOZINHAS (o jogador precisa ver que algo aconteceu).

Uso tipico:

    world.vfx.append(Blast(x, y, raio, cor))

`world` e o objeto `Game` (ver comentario em entities/projectile.py sobre
a convencao de "world").
"""

import math
import pygame


class Blast:
    """Anel de explosao que cresce e some."""

    __slots__ = ("x", "y", "radius", "color", "life", "max_life", "width")

    def __init__(self, x, y, radius, color, life=0.35, width=3):
        self.x = x
        self.y = y
        self.radius = max(8.0, radius)
        self.color = color
        self.life = life
        self.max_life = life
        self.width = width

    @property
    def alive(self):
        return self.life > 0

    def update(self, dt):
        self.life -= dt

    def draw(self, surf, offset):
        t = 1.0 - max(0.0, self.life / self.max_life)
        r = int(self.radius * (0.35 + 0.65 * t))
        alpha = int(200 * (1.0 - t))
        if r <= 0 or alpha <= 0:
            return
        layer = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        c = (*self.color[:3], alpha)
        pygame.draw.circle(layer, (*self.color[:3], alpha // 4), (r + 2, r + 2), r)
        pygame.draw.circle(layer, c, (r + 2, r + 2), r, self.width)
        surf.blit(layer, (self.x + offset[0] - r - 2, self.y + offset[1] - r - 2))


class Field:
    """Area persistente (auras de gelo/permafrost, chuva de flechas,
    zona de bombardeio). So desenha -- quem aplica o efeito e a torre ou
    a habilidade dona dela."""

    __slots__ = ("x", "y", "radius", "color", "life", "max_life", "pulse")

    def __init__(self, x, y, radius, color, life=0.2):
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
        self.life = life
        self.max_life = life
        self.pulse = 0.0

    @property
    def alive(self):
        return self.life > 0

    def update(self, dt):
        self.life -= dt
        self.pulse += dt

    def draw(self, surf, offset):
        r = int(self.radius)
        if r <= 0:
            return
        alpha = int(70 * min(1.0, self.life / max(0.001, self.max_life * 0.5)))
        layer = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(layer, (*self.color[:3], max(12, alpha // 2)), (r + 2, r + 2), r)
        wobble = int(2 + 1.5 * math.sin(self.pulse * 6))
        pygame.draw.circle(layer, (*self.color[:3], min(200, alpha + 60)),
                           (r + 2, r + 2), r, wobble)
        surf.blit(layer, (self.x + offset[0] - r - 2, self.y + offset[1] - r - 2))


class Beam:
    """Linha rapida (tiro divino, execucao titanica) entre dois pontos."""

    __slots__ = ("x1", "y1", "x2", "y2", "color", "life", "max_life", "width")

    def __init__(self, x1, y1, x2, y2, color, life=0.25, width=4):
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.color = color
        self.life = life
        self.max_life = life
        self.width = width

    @property
    def alive(self):
        return self.life > 0

    def update(self, dt):
        self.life -= dt

    def draw(self, surf, offset):
        t = max(0.0, self.life / self.max_life)
        w = max(1, int(self.width * t))
        ox, oy = offset
        pygame.draw.line(surf, self.color,
                         (self.x1 + ox, self.y1 + oy), (self.x2 + ox, self.y2 + oy), w)


def update_vfx(vfx_list, dt):
    for v in vfx_list:
        v.update(dt)
    return [v for v in vfx_list if v.alive]
