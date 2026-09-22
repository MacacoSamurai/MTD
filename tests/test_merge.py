"""O merge de duas torres do mesmo tipo usa o MAIOR tier de cada
caminho entre as duas -- mas nao pode driblar o crosspath: se o
resultado violar a regra (ex.: 5-0-0 + 0-5-0 = 5-5-0), a config
resultante deve ser ilegal."""
from towerdefense import upgrades as up
from towerdefense.entities import Tower


def test_merge_nao_pode_driblar_crosspath():
    a = Tower(0, 0, ttype="gelo")
    b = Tower(0, 1, ttype="gelo")
    for _ in range(5):
        a.buy_path(0)
        b.buy_path(1)
    merged = [max(x, y) for x, y in zip(a.tiers, b.tiers)]
    assert up.is_legal_config(merged) is False
