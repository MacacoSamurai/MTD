"""Resolucao de dano e efeitos -- o "motor de combate" compartilhado.

Por que existe: com a arvore de upgrades (ver `towerdefense/upgrades.py`)
o mesmo conjunto de efeitos (critico, bonus contra pesados, queimadura,
veneno, congelamento, marcacao, estilhacos, explosoes secundarias...)
pode chegar ao inimigo por tres caminhos diferentes:

    1. um projetil comum acertando;
    2. uma explosao em area (splash/fragmento);
    3. uma habilidade tier 6 disparada pela IA (systems/abilities.py).

Sem um lugar unico, cada um desses reimplementaria a mesma conta e eles
divergiriam na primeira mudanca de balanceamento. Entao TODO dano do
jogo passa por `resolve_hit` / `area_damage` / `explode` daqui.

O "dicionario de efeitos" (`eff`) e produzido por `Tower.build_effects()`
a partir dos mods dos upgrades comprados, ja com valores ABSOLUTOS
(ex.: `burn_dps` ja multiplicado pelo dano da torre) -- este modulo nunca
volta na arvore de upgrades, so le o dicionario.

Convencao de `world`: qualquer objeto com `.enemies`, `.projectiles`,
`.vfx` e `.pending_blasts` (na pratica, o `Game`). Entities e systems
nunca importam `Game` -- so recebem esse objeto e usam esses atributos.
"""

import math
import random

from .vfx import Blast, Beam


# ----------------------------------------------------------------------------
# ACERTO EM UM INIMIGO
# ----------------------------------------------------------------------------
def resolve_hit(world, enemy, damage, eff, ignore_dodge=False):
    """Aplica UM acerto em `enemy`. Retorna True se matou.

    Ordem das contas (importa pro balanceamento):
        esquiva -> critico -> bonus situacionais -> quebra de armadura ->
        dano -> status -> explosao de congelado
    """
    if enemy is None or not enemy.alive:
        return False
    if not ignore_dodge and enemy.dodges(eff.get("camo_detect", False)):
        return False

    dmg = damage
    crit = False
    chance = eff.get("crit_chance", 0.0)
    if chance > 0 and random.random() < chance:
        crit = True
        dmg *= eff.get("crit_mult", 2.0)

    if enemy.is_heavy:
        dmg *= eff.get("heavy_mult", 1.0)
    else:
        dmg *= eff.get("small_mult", 1.0)
        # "Lenda do Tiro"/"Deus do Tiro": um critico fulmina inimigos comuns
        if crit and eff.get("execute_small", False):
            dmg = max(dmg, enemy.hp * 4 + 1)

    if enemy.hp < enemy.max_hp * 0.5:
        dmg *= eff.get("wounded_mult", 1.0)
    was_frozen = enemy.frozen
    if was_frozen:
        dmg *= eff.get("bonus_vs_frozen", 1.0)

    shred = eff.get("armor_shred", 0.0)
    if shred > 0:
        enemy.apply_shred(shred)

    killed = enemy.take_damage(dmg, ignore_armor=eff.get("armor_pierce", False))

    _apply_statuses(enemy, eff)

    if killed and was_frozen and eff.get("frozen_explode", 0.0) > 0:
        # "Explosao de Gelo": congelado destruido estilhaca em area
        radius = max(40.0, eff.get("splash", 0.0) * 1.2)
        world.vfx.append(Blast(enemy.x, enemy.y, radius, (190, 240, 255)))
        area_damage(world, enemy.x, enemy.y, radius,
                    damage * eff.get("frozen_explode"), eff,
                    exclude=enemy, apply_statuses=False)
    return killed


def _apply_statuses(enemy, eff):
    if not enemy.alive:
        return
    dot = eff.get("dot_dps", 0.0)
    if dot > 0:
        enemy.apply_burn(dot, eff.get("dot_time", 3.0))
    burn = eff.get("burn_dps", 0.0)
    if burn > 0:
        enemy.apply_burn(burn, eff.get("burn_time", 3.0))
    poison = eff.get("poison_dps", 0.0)
    if poison > 0:
        enemy.apply_poison(poison, eff.get("poison_time", 4.0),
                           eff.get("poison_stack_max", 3))
    slow = eff.get("slow")
    if slow is not None:
        factor, duration, chance = slow
        if chance >= 1.0 or random.random() < chance:
            enemy.apply_slow(factor, duration)
    fchance = eff.get("freeze_chance", 0.0)
    if fchance > 0 and random.random() < fchance:
        enemy.apply_freeze(eff.get("freeze_time", 1.0))
    if eff.get("mark_on_hit", False):
        enemy.apply_mark(eff.get("mark_amp", 0.2), eff.get("mark_time", 3.0))


# ----------------------------------------------------------------------------
# DANO EM AREA
# ----------------------------------------------------------------------------
def area_damage(world, x, y, radius, damage, eff, exclude=None,
                apply_statuses=True, max_targets=None, falloff=0.0):
    """Dano circular. `falloff` (0..1) reduz o dano na borda da explosao.
    Retorna a quantidade de inimigos atingidos."""
    if radius <= 0:
        return 0
    hits = 0
    r2 = radius * radius
    sub_eff = eff if apply_statuses else _no_status(eff)
    for e in world.enemies:
        if not e.alive or e is exclude:
            continue
        dx, dy = e.x - x, e.y - y
        d2 = dx * dx + dy * dy
        if d2 > r2:
            continue
        dmg = damage
        if falloff > 0:
            t = math.sqrt(d2) / radius
            dmg *= 1.0 - falloff * t
        resolve_hit(world, e, dmg, sub_eff, ignore_dodge=True)
        hits += 1
        if max_targets is not None and hits >= max_targets:
            break
    return hits


_STATUS_KEYS = ("dot_dps", "burn_dps", "poison_dps", "slow", "freeze_chance",
                "mark_on_hit")


def _no_status(eff):
    """Copia do dicionario de efeitos sem os status (usada em dano
    secundario: fragmento/explosao encadeada nao deve re-aplicar veneno e
    congelamento infinitamente)."""
    return {k: v for k, v in eff.items() if k not in _STATUS_KEYS}


# ----------------------------------------------------------------------------
# EXPLOSAO COMPLETA (splash + estilhacos + explosoes secundarias)
# ----------------------------------------------------------------------------
def explode(world, x, y, damage, eff, direct_target=None, color=(255, 180, 90)):
    """Detonacao "cheia" de um projetil: dano direto/em area, estilhacos e
    explosoes secundarias, tudo conforme os mods da torre."""
    splash = eff.get("splash", 0.0)
    if splash > 0:
        world.vfx.append(Blast(x, y, splash, color))
        area_damage(world, x, y, splash, damage, eff, falloff=0.25)
    elif direct_target is not None:
        resolve_hit(world, direct_target, damage, eff)

    frags = int(eff.get("frag_count", 0))
    if frags > 0:
        frag_radius = max(50.0, splash * 1.6)
        frag_damage = damage * eff.get("frag_damage", 0.35)
        # estilhacos: cada um atinge um inimigo proximo diferente, em vez
        # de virar um segundo splash gigante no mesmo ponto (o efeito
        # pretendido e "espalhar pros vizinhos", nao "dobrar o splash")
        near = _nearest_enemies(world, x, y, frag_radius, frags, exclude=direct_target)
        for e in near:
            world.vfx.append(Beam(x, y, e.x, e.y, (255, 220, 150), life=0.14, width=2))
            resolve_hit(world, e, frag_damage, _no_status(eff), ignore_dodge=True)

    secondary = int(eff.get("secondary_blasts", 0))
    for i in range(secondary):
        ang = random.uniform(0, math.tau)
        dist = max(30.0, splash * 0.8)
        bx = x + math.cos(ang) * dist
        by = y + math.sin(ang) * dist
        schedule_blast(world, bx, by, delay=0.18 * (i + 1),
                       damage=damage * 0.6, radius=max(40.0, splash * 0.8),
                       eff=_no_status(eff), color=color)


def _nearest_enemies(world, x, y, radius, count, exclude=None):
    cands = []
    r2 = radius * radius
    for e in world.enemies:
        if not e.alive or e is exclude:
            continue
        d2 = (e.x - x) ** 2 + (e.y - y) ** 2
        if d2 <= r2:
            cands.append((d2, e))
    cands.sort(key=lambda p: p[0])
    return [e for _, e in cands[:count]]


# ----------------------------------------------------------------------------
# EXPLOSOES ATRASADAS
# Usadas por explosoes secundarias e pelas habilidades tier 6 que fazem
# "sequencia de detonacoes" (APOCALIPSE, FIM DOS TEMPOS). Ficam numa lista
# no `world` e sao resolvidas por `update_pending_blasts` a cada frame.
# ----------------------------------------------------------------------------
class PendingBlast:
    __slots__ = ("x", "y", "delay", "damage", "radius", "eff", "color")

    def __init__(self, x, y, delay, damage, radius, eff, color):
        self.x = x
        self.y = y
        self.delay = delay
        self.damage = damage
        self.radius = radius
        self.eff = eff
        self.color = color


def schedule_blast(world, x, y, delay, damage, radius, eff, color=(255, 180, 90)):
    world.pending_blasts.append(PendingBlast(x, y, delay, damage, radius, eff, color))


def update_pending_blasts(world, dt):
    if not world.pending_blasts:
        return
    remaining = []
    for pb in world.pending_blasts:
        pb.delay -= dt
        if pb.delay > 0:
            remaining.append(pb)
            continue
        world.vfx.append(Blast(pb.x, pb.y, pb.radius, pb.color))
        area_damage(world, pb.x, pb.y, pb.radius, pb.damage, pb.eff,
                    apply_statuses=False, falloff=0.2)
    world.pending_blasts = remaining


# ----------------------------------------------------------------------------
# CONSULTAS USADAS PELA IA DAS HABILIDADES
# ----------------------------------------------------------------------------
def best_cluster(world, radius, min_count=1):
    """Ponto com maior "peso" de inimigos dentro de `radius`.

    Varre usando cada inimigo vivo como centro candidato (O(n^2), mas n
    aqui e dezenas, nao milhares) e pontua pela vida somada dos vizinhos,
    nao pela contagem crua: 3 tanques valem mais que 6 swarms, que e
    exatamente o que uma ogiva quer acertar.

    Retorna (x, y, contagem, peso) ou None.
    """
    alive = [e for e in world.enemies if e.alive]
    if not alive:
        return None
    r2 = radius * radius
    best = None
    for c in alive:
        count = 0
        weight = 0.0
        sx = sy = 0.0
        for e in alive:
            if (e.x - c.x) ** 2 + (e.y - c.y) ** 2 <= r2:
                count += 1
                weight += e.hp
                sx += e.x
                sy += e.y
        if count < min_count:
            continue
        if best is None or weight > best[3]:
            best = (sx / count, sy / count, count, weight)
    return best


def strongest_enemy(world, heavy_only=False):
    """Inimigo com maior `danger_score` (ver entities/enemy.py)."""
    total = world.map_path.total_len
    best = None
    best_score = 0.0
    for e in world.enemies:
        if not e.alive:
            continue
        if heavy_only and not e.is_heavy:
            continue
        s = e.danger_score(total)
        if s > best_score:
            best = e
            best_score = s
    return best


def top_enemies(world, count, heavy_only=False):
    total = world.map_path.total_len
    alive = [e for e in world.enemies
             if e.alive and (not heavy_only or e.is_heavy)]
    alive.sort(key=lambda e: e.danger_score(total), reverse=True)
    return alive[:count]
