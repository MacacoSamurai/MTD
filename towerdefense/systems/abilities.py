"""Habilidades das torres TIER 6 e a IA que decide quando usa-las.

O jogador NUNCA clica numa habilidade: cada torre tier 6 tem um cooldown
e, quando ele zera, a IA olha a pista e decide se AGORA e uma boa hora.
Esse "se agora e uma boa hora" e o coracao deste modulo -- sem ele, a
habilidade viraria um efeito automatico a cada N segundos, e a sensacao
de super torre se perderia.

COMO CADA HABILIDADE E DESCRITA
-------------------------------
Uma entrada de `ABILITIES` tem ate tres funcoes:

    evaluate(world, tower) -> payload | None
        A IA. Recebe a pista inteira e devolve o "alvo" da habilidade
        (ponto, inimigo, lista de inimigos...) se valer a pena disparar
        agora, ou None pra continuar esperando.
    fire(world, tower, payload)
        O efeito imediato (explosao, tiro, marcacao...).
    tick(world, tower, payload, dt)
        Para habilidades com duracao: chamado todo frame enquanto ela
        estiver ativa (barragem, bombardeio, chuva de flechas...).

PACIENCIA
---------
Toda avaliacao passa por `_impatient`: se a habilidade esta pronta ha
muito tempo e existe QUALQUER inimigo na pista, ela dispara mesmo sem a
situacao ideal. Sem isso, uma torre anti-chefe poderia ficar em silencio
por ondas inteiras esperando um boss que nao vem.

Os efeitos globais (DOMINIO ETERNO, VISAO ABSOLUTA) sao aplicados
escrevendo em `Enemy.global_amp` / `Enemy.global_slow`, recalculados do
zero a cada frame em `AbilityController.update` -- assim nunca sobra
efeito ligado depois que a habilidade acaba.
"""

import math
import random

from ..config import GRID_ORIGIN_X, GRID_ORIGIN_Y, CELL_SIZE
from ..entities.enemy import Enemy
from . import combat
from .vfx import Blast, Beam, Field


# De quanto em quanto tempo a IA reavalia uma habilidade ja carregada.
ABILITY_EVAL_INTERVAL = 0.2


# ----------------------------------------------------------------------------
# Helpers de avaliacao
# ----------------------------------------------------------------------------
def _alive(world):
    return [e for e in world.enemies if e.alive]


def _impatient(tower, factor=1.0):
    """True quando a habilidade ja esta pronta ha tempo demais."""
    ab = tower.ability()
    return tower.ability_ready_for >= ab["cooldown"] * 0.9 * factor


def _leaking(world, enemies=None, frac=0.75):
    """Algum inimigo ja passou de `frac` do caminho? Situacao de perigo:
    vale queimar a habilidade mesmo fora do cenario ideal."""
    total = world.map_path.total_len
    for e in (enemies if enemies is not None else _alive(world)):
        if e.dist / total >= frac:
            return True
    return False


def _has_boss(world):
    return any(e.is_boss for e in _alive(world))


def _announce(world, tower, ab):
    gx, gy = tower.grid_pos()
    world.add_floating_text(gx, gy - 46, ab["name"], (255, 230, 140))
    world.ability_banner = [ab["name"], 2.2]


# ----------------------------------------------------------------------------
# CANHAO
# ----------------------------------------------------------------------------
def _eval_cluster(radius, min_count, min_weight_mult=0.0):
    """Fabrica de `evaluate` para habilidades de area: procura o melhor
    aglomerado e so aceita se tiver inimigos suficientes."""
    def ev(world, tower):
        enemies = _alive(world)
        if not enemies:
            return None
        cluster = combat.best_cluster(world, radius, min_count=1)
        if cluster is None:
            return None
        x, y, count, weight = cluster
        if count >= min_count or _has_boss(world) or _leaking(world, enemies) or _impatient(tower):
            return (x, y)
        return None
    return ev


def _fire_apocalipse(world, tower, payload):
    x, y = payload
    dmg = tower.damage * 12
    eff = dict(tower.effects)
    eff["splash"] = 0
    world.vfx.append(Blast(x, y, 170, (255, 160, 60), life=0.6, width=6))
    combat.area_damage(world, x, y, 170, dmg, eff, apply_statuses=False, falloff=0.25)
    for i in range(5):
        ang = random.uniform(0, math.tau)
        d = random.uniform(60, 190)
        combat.schedule_blast(world, x + math.cos(ang) * d, y + math.sin(ang) * d,
                              delay=0.25 * (i + 1), damage=dmg * 0.55, radius=95,
                              eff=eff, color=(255, 190, 90))


def _tick_barragem(world, tower, payload, dt):
    tower.ability_tick -= dt
    if tower.ability_tick > 0:
        return
    tower.ability_tick = 0.28
    cluster = combat.best_cluster(world, 110, min_count=1)
    if cluster is None:
        return
    x, y, _count, _w = cluster
    eff = dict(tower.effects)
    eff["splash"] = 0
    world.vfx.append(Blast(x, y, 95, (255, 200, 110), life=0.3))
    combat.area_damage(world, x, y, 95, tower.damage * 2.6, eff,
                       apply_statuses=False, falloff=0.2)


def _eval_support(min_count=3):
    """`evaluate` para habilidades de suporte/marcacao: precisam de gente
    na pista pra valer a pena, ou de um chefe pra marcar."""
    def ev(world, tower):
        enemies = _alive(world)
        if not enemies:
            return None
        if len(enemies) >= min_count or _has_boss(world) or _leaking(world, enemies) or _impatient(tower):
            return True
        return None
    return ev


def _fire_olho_apocalipse(world, tower, payload):
    ab = tower.ability()
    alvos = combat.top_enemies(world, 8)
    for e in alvos:
        e.apply_mark(1.20, ab["duration"])
        world.vfx.append(Beam(*tower.grid_pos(), e.x, e.y, (255, 140, 220), life=0.3, width=2))


def _tick_olho_apocalipse(world, tower, payload, dt):
    # mantem a marcacao em quem entrar na pista durante o efeito
    tower.ability_tick -= dt
    if tower.ability_tick > 0:
        return
    tower.ability_tick = 0.5
    for e in combat.top_enemies(world, 8):
        e.apply_mark(1.20, 1.0)


# ----------------------------------------------------------------------------
# TORRE DE FLECHAS
# ----------------------------------------------------------------------------
def _fire_chuva(world, tower, payload):
    x, y = payload
    tower.ability_payload = (x, y)
    world.vfx.append(Field(x, y, 190, (170, 255, 170), life=tower.ability_active))


def _tick_chuva(world, tower, payload, dt):
    tower.ability_tick -= dt
    if tower.ability_tick > 0:
        return
    tower.ability_tick = 0.22
    x, y = payload
    eff = dict(tower.effects)
    eff["splash"] = 0
    world.vfx.append(Blast(x + random.uniform(-120, 120), y + random.uniform(-120, 120),
                           40, (200, 255, 190), life=0.25, width=2))
    combat.area_damage(world, x, y, 190, tower.damage * 1.6, eff, falloff=0.1)


def _eval_cacada(world, tower):
    alvo = combat.strongest_enemy(world)
    if alvo is None:
        return None
    if alvo.is_heavy or alvo.hp > tower.damage * 12 or _leaking(world) or _impatient(tower):
        return alvo
    return None


def _tick_cacada(world, tower, payload, dt):
    tower.ability_tick -= dt
    if tower.ability_tick > 0:
        return
    tower.ability_tick = 0.10
    alvo = payload if (payload is not None and payload.alive) else combat.strongest_enemy(world)
    if alvo is None:
        return
    tower.ability_payload = alvo
    gx, gy = tower.grid_pos()
    world.vfx.append(Beam(gx, gy, alvo.x, alvo.y, (200, 255, 160), life=0.12, width=3))
    eff = dict(tower.effects)
    eff["splash"] = 0
    eff["armor_pierce"] = True
    combat.resolve_hit(world, alvo, tower.damage * 3.2, eff, ignore_dodge=True)


def _fire_ira(world, tower, payload):
    gx, gy = tower.grid_pos()
    world.vfx.append(Field(gx, gy, tower.range, (255, 180, 120), life=tower.ability_active))


def _tick_ira(world, tower, payload, dt):
    tower.ability_tick -= dt
    if tower.ability_tick > 0:
        return
    tower.ability_tick = 0.35
    gx, gy = tower.grid_pos()
    r2 = tower.range * tower.range
    d = tower.damage
    for e in _alive(world):
        if (e.x - gx) ** 2 + (e.y - gy) ** 2 > r2:
            continue
        e.apply_burn(d * 1.2, 2.0)
        e.apply_poison(d * 0.9, 3.0, 8)
        e.apply_freeze(0.5)
        e.apply_mark(0.35, 2.0)
        combat.resolve_hit(world, e, d * 0.8, {"armor_pierce": True}, ignore_dodge=True)


# ----------------------------------------------------------------------------
# TORRE DE GELO
# ----------------------------------------------------------------------------
def _eval_congelar(world, tower):
    enemies = _alive(world)
    if not enemies:
        return None
    if len(enemies) >= 6 or _has_boss(world) or _leaking(world, enemies, 0.6) or _impatient(tower):
        return True
    return None


def _fire_era_do_gelo(world, tower, payload):
    ab = tower.ability()
    gx, gy = tower.grid_pos()
    world.vfx.append(Blast(gx, gy, 520, (200, 245, 255), life=0.7, width=6))
    for e in _alive(world):
        # bosses nao congelam: levam lentidao extrema (regra da habilidade)
        e.apply_freeze(ab["duration"], boss_slow=0.22)


def _fire_supernova(world, tower, payload):
    x, y = payload
    eff = dict(tower.effects)
    eff["splash"] = 0
    world.vfx.append(Blast(x, y, 230, (170, 235, 255), life=0.6, width=6))
    combat.area_damage(world, x, y, 230, tower.damage * 10, eff, apply_statuses=False, falloff=0.2)
    for e in _alive(world):
        if (e.x - x) ** 2 + (e.y - y) ** 2 <= 230 * 230:
            e.apply_freeze(2.5)


def _fire_dominio(world, tower, payload):
    gx, gy = tower.grid_pos()
    world.vfx.append(Field(gx, gy, 900, (150, 210, 255), life=tower.ability_active))


# ----------------------------------------------------------------------------
# CANHAO PESADO
# ----------------------------------------------------------------------------
def _fire_fim_dos_tempos(world, tower, payload):
    x, y = payload
    eff = dict(tower.effects)
    eff["splash"] = 0
    dmg = tower.damage * 9
    world.vfx.append(Blast(x, y, 200, (255, 140, 70), life=0.7, width=7))
    combat.area_damage(world, x, y, 200, dmg, eff, apply_statuses=False, falloff=0.2)
    for i in range(7):
        ang = random.uniform(0, math.tau)
        d = random.uniform(40, 230)
        combat.schedule_blast(world, x + math.cos(ang) * d, y + math.sin(ang) * d,
                              delay=0.16 * (i + 1), damage=dmg * 0.5, radius=110,
                              eff=eff, color=(255, 170, 80))


def _tick_bombardeio(world, tower, payload, dt):
    tower.ability_tick -= dt
    if tower.ability_tick > 0:
        return
    tower.ability_tick = 0.16
    enemies = _alive(world)
    if not enemies:
        return
    alvo = random.choice(enemies)
    x = alvo.x + random.uniform(-45, 45)
    y = alvo.y + random.uniform(-45, 45)
    eff = dict(tower.effects)
    eff["splash"] = 0
    world.vfx.append(Blast(x, y, 85, (255, 190, 100), life=0.3))
    combat.area_damage(world, x, y, 85, tower.damage * 2.2, eff,
                       apply_statuses=False, falloff=0.2)


def _eval_executor(world, tower):
    alvo = combat.strongest_enemy(world, heavy_only=True)
    if alvo is not None:
        return alvo
    if _impatient(tower) or _leaking(world):
        return combat.strongest_enemy(world)
    return None


def _fire_execucao_titanica(world, tower, payload):
    alvo = payload
    if alvo is None or not alvo.alive:
        return
    gx, gy = tower.grid_pos()
    world.vfx.append(Beam(gx, gy, alvo.x, alvo.y, (255, 160, 90), life=0.35, width=6))
    world.vfx.append(Blast(alvo.x, alvo.y, 120, (255, 160, 90), life=0.5, width=5))
    eff = dict(tower.effects)
    eff["splash"] = 0
    eff["armor_pierce"] = True
    combat.resolve_hit(world, alvo, tower.damage * 22, eff, ignore_dodge=True)
    combat.area_damage(world, alvo.x, alvo.y, 120, tower.damage * 3, eff,
                       exclude=alvo, apply_statuses=False)


# ----------------------------------------------------------------------------
# SNIPER
# ----------------------------------------------------------------------------
def _eval_tiro_divino(world, tower):
    alvo = combat.strongest_enemy(world)
    if alvo is None:
        return None
    if alvo.is_heavy or alvo.hp > tower.damage * 8 or _leaking(world) or _impatient(tower):
        return alvo
    return None


def _fire_tiro_divino(world, tower, payload):
    alvo = payload
    if alvo is None or not alvo.alive:
        return
    gx, gy = tower.grid_pos()
    world.vfx.append(Beam(gx, gy, alvo.x, alvo.y, (255, 120, 170), life=0.4, width=5))
    combat.resolve_hit(world, alvo, tower.damage * 26,
                       {"armor_pierce": True, "crit_chance": 0.0}, ignore_dodge=True)
    world.vfx.append(Blast(alvo.x, alvo.y, 70, (255, 120, 170), life=0.4))


def _tick_execucao_automatica(world, tower, payload, dt):
    tower.ability_tick -= dt
    if tower.ability_tick > 0:
        return
    tower.ability_tick = 0.07
    alvo = combat.strongest_enemy(world)
    if alvo is None:
        return
    gx, gy = tower.grid_pos()
    world.vfx.append(Beam(gx, gy, alvo.x, alvo.y, (255, 220, 150), life=0.08, width=2))
    eff = dict(tower.effects)
    eff["splash"] = 0
    eff["armor_pierce"] = True
    combat.resolve_hit(world, alvo, tower.damage * 1.6, eff, ignore_dodge=True)


def _fire_visao_absoluta(world, tower, payload):
    for e in _alive(world):
        e.apply_mark(1.0, tower.ability_active)


# ----------------------------------------------------------------------------
# ESPINHOS (ARMADILHEIRO)
# ----------------------------------------------------------------------------
def _eval_espinhos_ready(world, tower):
    """As 3 habilidades de espinhos so fazem sentido se ha pista pela
    frente (senti-las com a pista vazia seria desperdicio); qualquer
    inimigo vivo ja basta -- sao habilidades baratas de reavaliar."""
    if _alive(world):
        return True
    return None


def _fire_campo_minado_total(world, tower, payload):
    """Planta instantaneamente um espinho em toda celula do caminho
    dentro do alcance de plantio que ainda nao tenha um espinho vivo
    desta torre (respeitando o limite normal de espinhos simultaneos)."""
    from ..entities.spike import Spike
    gx, gy = tower.grid_pos()
    r2 = tower.plant_range * tower.plant_range
    occupied = {(sp.col, sp.row) for sp in tower.spikes}
    for (col, row) in world.map_path.cell_set:
        if len(tower.spikes) >= tower.spike_max:
            break
        if (col, row) in occupied:
            continue
        cx = GRID_ORIGIN_X + col * CELL_SIZE + CELL_SIZE // 2
        cy = GRID_ORIGIN_Y + row * CELL_SIZE + CELL_SIZE // 2
        if (cx - gx) ** 2 + (cy - gy) ** 2 <= r2:
            tower.spikes.append(Spike(col, row, tower.spike_charges, tower.damage, tower))


def _fire_praga_do_abismo(world, tower, payload):
    """Todos os espinhos ativos da torre liberam uma explosao de veneno
    imediatamente (dano em area centrado em cada espinho)."""
    eff = dict(tower.effects)
    for sp in tower.spikes:
        if not sp.alive:
            continue
        world.vfx.append(Blast(sp.x, sp.y, 55, (120, 220, 110), life=0.4))
        combat.area_damage(world, sp.x, sp.y, 55, tower.damage * 2.0, eff,
                           apply_statuses=False)


def _fire_golpe_das_sombras(world, tower, payload):
    """O proximo acerto de cada espinho ativo e garantidamente critico
    por alguns segundos (a duracao da habilidade)."""
    for sp in tower.spikes:
        if sp.alive:
            sp.guaranteed_crit = True


def _tick_golpe_das_sombras(world, tower, payload, dt):
    # mantem o bonus em espinhos plantados durante a janela ativa
    for sp in tower.spikes:
        if sp.alive:
            sp.guaranteed_crit = True


# ----------------------------------------------------------------------------
# TABELA DE HABILIDADES (a chave e o campo "kind" em upgrades.py)
# ----------------------------------------------------------------------------
ABILITIES = {
    # --- canhao ---
    "apocalipse": {"evaluate": _eval_cluster(150, 5), "fire": _fire_apocalipse},
    "barragem": {"evaluate": _eval_cluster(130, 4), "tick": _tick_barragem},
    "olho_apocalipse": {"evaluate": _eval_support(3), "fire": _fire_olho_apocalipse,
                        "tick": _tick_olho_apocalipse},
    # --- torre de flechas ---
    "chuva_flechas": {"evaluate": _eval_cluster(170, 5), "fire": _fire_chuva, "tick": _tick_chuva},
    "cacada_suprema": {"evaluate": _eval_cacada, "tick": _tick_cacada},
    "ira_elementos": {"evaluate": _eval_support(4), "fire": _fire_ira, "tick": _tick_ira},
    # --- torre de gelo ---
    "era_do_gelo": {"evaluate": _eval_congelar, "fire": _fire_era_do_gelo},
    "supernova": {"evaluate": _eval_cluster(180, 4), "fire": _fire_supernova},
    "dominio_eterno": {"evaluate": _eval_support(5), "fire": _fire_dominio,
                       "global_amp": 0.85, "global_slow": 0.40},
    # --- canhao pesado ---
    "fim_dos_tempos": {"evaluate": _eval_cluster(180, 4), "fire": _fire_fim_dos_tempos},
    "bombardeio_total": {"evaluate": _eval_cluster(150, 5), "tick": _tick_bombardeio},
    "execucao_titanica": {"evaluate": _eval_executor, "fire": _fire_execucao_titanica},
    # --- sniper ---
    "tiro_divino": {"evaluate": _eval_tiro_divino, "fire": _fire_tiro_divino},
    "execucao_automatica": {"evaluate": _eval_support(3), "tick": _tick_execucao_automatica},
    "visao_absoluta": {"evaluate": _eval_support(4), "fire": _fire_visao_absoluta,
                       "global_amp": 1.10},
    # --- espinhos (armadilheiro) ---
    "campo_minado_total": {"evaluate": _eval_espinhos_ready, "fire": _fire_campo_minado_total},
    "praga_do_abismo": {"evaluate": _eval_espinhos_ready, "fire": _fire_praga_do_abismo},
    "golpe_das_sombras": {"evaluate": _eval_espinhos_ready, "fire": _fire_golpe_das_sombras,
                          "tick": _tick_golpe_das_sombras},
}


class AbilityController:
    """Roda as habilidades de todas as torres tier 6 da partida.

    Vive em `Game` e e atualizado uma vez por frame, depois das torres.
    Nao guarda lista de torres: varre `world.towers` toda vez (sao poucas
    e assim nao existe estado pra dessincronizar quando o jogador move,
    vende ou funde uma torre).
    """

    def __init__(self):
        self.last_used = None

    def update(self, world, dt):
        amp = 0.0
        slow = 1.0
        for tower in list(world.towers.values()):
            if not tower.has_ability or tower.being_dragged:
                continue
            ab = tower.ability()
            spec = ABILITIES.get(ab["kind"])
            if spec is None:
                continue

            if tower.ability_active > 0:
                tower.ability_active -= dt
                payload = getattr(tower, "ability_payload", None)
                tick = spec.get("tick")
                if tick is not None:
                    tick(world, tower, payload, dt)
                if "global_amp" in spec:
                    amp = max(amp, spec["global_amp"])
                if "global_slow" in spec:
                    slow = min(slow, spec["global_slow"])
                if tower.ability_active <= 0:
                    tower.ability_active = 0.0
                    tower.ability_cd = ab["cooldown"]
                    tower.ability_ready_for = 0.0
                continue

            if tower.ability_cd > 0:
                tower.ability_cd -= dt
                continue

            # pronta: a IA decide se a hora e boa. A avaliacao procura
            # aglomerados (varredura O(n^2) sobre os inimigos vivos),
            # entao roda algumas vezes por segundo em vez de todo frame
            # -- o atraso maximo de 0.2s e imperceptivel e o custo cai
            # por um fator de ~12 a 60fps.
            tower.ability_ready_for += dt
            tower.ability_eval_timer -= dt
            if tower.ability_eval_timer > 0:
                continue
            tower.ability_eval_timer = ABILITY_EVAL_INTERVAL
            payload = spec["evaluate"](world, tower)
            if payload is None:
                continue
            self._activate(world, tower, ab, spec, payload)

        Enemy.global_amp = amp
        Enemy.global_slow = slow

    def _activate(self, world, tower, ab, spec, payload):
        tower.ability_payload = payload
        tower.ability_tick = 0.0
        duration = ab.get("duration", 0.0)
        tower.ability_active = duration
        fire = spec.get("fire")
        if fire is not None:
            fire(world, tower, payload)
        if duration <= 0:
            tower.ability_cd = ab["cooldown"]
            tower.ability_ready_for = 0.0
        self.last_used = ab["name"]
        _announce(world, tower, ab)
