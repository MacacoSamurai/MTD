"""Roda uma partida de verdade (update + draw) por 90 segundos
simulados, com uma torre tier 6 de cada tipo (cada uma num caminho
diferente, com crosspath), conferindo que as habilidades chegam a
disparar sozinhas e que inimigos morrem.

E o teste mais caro da suite (90s de jogo simulado): marcado como
`slow` para poder ser pulado com `pytest -m "not slow"` durante
iteracao rapida.
"""
import pytest

from towerdefense.config import TOWER_TYPE_KEYS
from tests.conftest import buy_path_to_tier, place_tower

# um caminho diferente por torre, cobrindo os 3 indices de caminho
PLANO = [("canhao", 0), ("flecha", 1), ("gelo", 2), ("canhao_pesado", 0), ("sniper", 2)]


@pytest.fixture(scope="module")
def tipos_do_plano_existem():
    for ttype, _path in PLANO:
        assert ttype in TOWER_TYPE_KEYS, f"tipo '{ttype}' nao existe mais em TOWER_TYPE_KEYS"


@pytest.fixture
def partida_com_torres_tier6(game, free_cells, tipos_do_plano_existem):
    """Monta o cenario: 5 torres tier 6 (uma por tipo do PLANO), cada
    uma com o caminho principal no tier 6 e o crosspath ate o tier 2
    quando possivel. Retorna (game, [(cell, tower), ...])."""
    placed = []
    for i, (ttype, path) in enumerate(PLANO):
        cell = free_cells[i * 7]
        t = place_tower(game, cell, ttype)

        ok, _cost, reason = buy_path_to_tier(game, t, path, 6)
        assert ok, f"{ttype} caminho {path}: compra recusada ({reason})"

        cross = (path + 1) % 3
        buy_path_to_tier(game, t, cross, 2)

        assert t.tiers[path] == 6, f"{ttype} deveria estar no tier 6 ({t.tiers})"
        assert t.tiers[cross] == 2, f"{ttype} deveria ter crosspath 2 ({t.tiers})"
        assert t.has_ability, f"{ttype} tier 6 sem habilidade"
        placed.append((cell, t))
    return game, placed


@pytest.mark.slow
def test_noventa_segundos_de_partida_com_torres_tier6(partida_com_torres_tier6):
    game, placed = partida_com_torres_tier6

    game.wave_mgr.wave_num = 14
    game.wave_mgr.start_next_wave()

    frames = 0
    used = set()
    for _ in range(60 * 90):  # 90 segundos simulados a 60fps
        game.update(1 / 60)
        game.draw()
        frames += 1
        for _cell, t in placed:
            if t.ability_active > 0 or t.ability_cd > 0:
                used.add(t.ttype)

    assert frames == 60 * 90, "simulacao interrompida"
    assert len(used) == 5, f"habilidades que chegaram a disparar: {sorted(used)}"
    assert game.total_kills > 0, "nenhum inimigo morreu em 90s com 5 torres tier 6"
