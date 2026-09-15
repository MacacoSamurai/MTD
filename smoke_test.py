"""Teste headless do sistema de torres (arvore de caminhos + tier 6).

O projeto nao usa pytest: este arquivo e um script proprio, feito pra
rodar sem display (SDL dummy) e sem interacao nenhuma. Ele cobre o que
seria caro validar na mao a cada mudanca de balanceamento:

    - as regras de crosspath (quantos caminhos, onde o secundario trava);
    - a integridade da arvore (5 x 3 x 6 = 90 evolucoes, todas com nome,
      descricao e habilidade tier 6 implementada);
    - a regra fundamental de UM tier 6 por tipo de torre na partida;
    - que o merge nao consegue driblar o crosspath;
    - 90 segundos de partida de verdade (update + draw), conferindo que
      as cinco habilidades chegam a disparar sozinhas e que inimigos
      morrem.

Rodar:

    python smoke_test.py

Sai com codigo != 0 se alguma checagem falhar.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from towerdefense import Game                     # noqa: E402
from towerdefense import upgrades as up           # noqa: E402
from towerdefense.config import TOWER_TYPE_KEYS   # noqa: E402
from towerdefense.entities import Tower           # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("  FALHA:", msg)


# ---------------------------------------------------------------- crosspath
print("== regras de crosspath ==")
check(up.can_upgrade([0, 0, 0], 0)[0], "deveria poder abrir o 1o caminho")
check(up.can_upgrade([2, 2, 0], 2)[0] is False, "3o caminho deveria estar bloqueado")
check(up.can_upgrade([3, 2, 0], 1)[0] is False, "secundario deveria travar no tier 2")
check(up.can_upgrade([3, 2, 0], 0)[0], "principal deveria continuar subindo")
check(up.can_upgrade([5, 2, 0], 0)[0], "tier 6 deveria ser permitido no principal")
check(up.can_upgrade([6, 2, 0], 0)[0] is False, "tier 6 e o maximo")
check(up.is_legal_config([5, 5, 0]) is False, "5-5-0 e ilegal")
check(up.is_legal_config([5, 2, 0]), "5-2-0 e legal")
check(up.is_legal_config([1, 1, 1]) is False, "tres caminhos abertos e ilegal")

# ---------------------------------------------------------------- arvore
print("== integridade da arvore (5 x 3 x 6 = 90) ==")
total = 0
for ttype in TOWER_TYPE_KEYS:
    paths = up.UPGRADE_TREE[ttype]
    check(len(paths) == 3, f"{ttype} deveria ter 3 caminhos")
    for pi, path in enumerate(paths):
        check(len(path["tiers"]) == 6, f"{ttype}/{path['name']} deveria ter 6 tiers")
        total += len(path["tiers"])
        check("ability" in path, f"{ttype}/{path['name']} sem habilidade tier 6")
        for t in path["tiers"]:
            check(bool(t["name"]) and bool(t["desc"]), f"tier sem nome/desc em {ttype}")
check(total == 90, f"deveriam existir 90 evolucoes, achei {total}")

from towerdefense.systems.abilities import ABILITIES  # noqa: E402
for ttype in TOWER_TYPE_KEYS:
    for pi in range(3):
        kind = up.ability_def(ttype, pi)["kind"]
        check(kind in ABILITIES, f"habilidade '{kind}' sem implementacao")

# ---------------------------------------------------------------- partida
print("== simulacao de partida ==")
g = Game()
g.start_map(g.selected_map_id)
g.gold = 10 ** 9

free = [c for c in ((x, y) for y in range(9) for x in range(15))
        if c not in g.map_path.cell_set]

# uma torre tier 6 de cada tipo, um caminho diferente em cada, com crosspath
plan = [("canhao", 0), ("flecha", 1), ("gelo", 2), ("canhao_pesado", 0), ("sniper", 2)]
placed = []
for i, (ttype, path) in enumerate(plan):
    cell = free[i * 7]
    g.towers[cell] = Tower(cell[0], cell[1], ttype=ttype)
    t = g.towers[cell]
    for _ in range(6):
        ok, cost, reason = g.path_purchase_state(t, path)
        check(ok, f"{ttype} caminho {path}: compra recusada ({reason})")
        if not ok:
            break
        g.gold -= cost
        t.buy_path(path)
    cross = (path + 1) % 3
    for _ in range(2):
        ok, cost, _r = g.path_purchase_state(t, cross)
        if ok:
            g.gold -= cost
            t.buy_path(cross)
    check(t.tiers[path] == 6, f"{ttype} deveria estar no tier 6 ({t.tiers})")
    check(t.tiers[cross] == 2, f"{ttype} deveria ter crosspath 2 ({t.tiers})")
    check(t.has_ability, f"{ttype} tier 6 sem habilidade")
    placed.append((cell, t))

# regra fundamental: um unico tier 6 por tipo
cell2 = free[60]
g.towers[cell2] = Tower(cell2[0], cell2[1], ttype="canhao")
t2 = g.towers[cell2]
for _ in range(5):
    ok, cost, _r = g.path_purchase_state(t2, 0)
    if ok:
        g.gold -= cost
        t2.buy_path(0)
ok, cost, reason = g.path_purchase_state(t2, 0)
check(not ok and "tier 6" in reason, f"2o tier 6 de canhao deveria ser bloqueado ({reason})")
# o caminho secundario ainda pode ir ate o tier 2 (5-2-0 e legal)...
for _ in range(2):
    ok2, cost2, reason2 = g.path_purchase_state(t2, 1)
    check(ok2, f"crosspath ate o tier 2 deveria ser permitido ({reason2})")
    if ok2:
        g.gold -= cost2
        t2.buy_path(1)
# ...mas nao alem dele
ok2, _c, reason2 = g.path_purchase_state(t2, 1)
check(not ok2 and "tier 2" in reason2, f"secundario deveria travar no tier 2 ({reason2})")
check(not g.path_purchase_state(t2, 2)[0], "terceiro caminho deveria estar fechado")

# merge nao pode driblar o crosspath
a = Tower(0, 0, ttype="gelo")
b = Tower(0, 1, ttype="gelo")
for _ in range(5):
    a.buy_path(0)
    b.buy_path(1)
merged = [max(x, y) for x, y in zip(a.tiers, b.tiers)]
check(not up.is_legal_config(merged), "merge 5-0-0 + 0-5-0 deveria ser ilegal")

# roda varios segundos de jogo de verdade
g.wave_mgr.wave_num = 14
g.wave_mgr.start_next_wave()
frames = 0
used = set()
for _ in range(60 * 90):  # 90 segundos simulados
    g.update(1 / 60)
    g.draw()
    frames += 1
    for cell, t in placed:
        if t.ability_active > 0 or t.ability_cd > 0:
            used.add(t.ttype)
check(frames == 60 * 90, "simulacao interrompida")
check(len(used) == 5, f"habilidades que chegaram a disparar: {sorted(used)}")
check(g.total_kills > 0, "nenhum inimigo morreu em 90s com 5 torres tier 6")
print(f"  abates: {g.total_kills} | ondas: {g.wave_mgr.wave_num} | vidas: {g.lives}")
print(f"  habilidades usadas por: {sorted(used)}")

print()
if fails:
    print(f"{len(fails)} FALHA(S)")
    sys.exit(1)
print("tudo certo")
