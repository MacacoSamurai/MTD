"""Configuracao compartilhada da suite pytest.

Forca o SDL_VIDEODRIVER/SDL_AUDIODRIVER para "dummy" ANTES de qualquer
import de pygame/towerdefense, para rodar headless (sem display, sem
audio) em CI ou em qualquer maquina sem janela grafica.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from towerdefense import Game  # noqa: E402
from towerdefense.entities import Tower  # noqa: E402


@pytest.fixture
def game():
    """Uma partida nova, no mapa selecionado por padrao, com ouro e
    gemas efetivamente ilimitados para nao travar testes de compra."""
    g = Game()
    g.start_map(g.selected_map_id)
    g.gold = 10 ** 9
    g.gems = 10 ** 6
    return g


@pytest.fixture
def free_cells(game):
    """Celulas livres (fora do caminho) do mapa da fixture `game`,
    na ordem de varredura y depois x, prontas pra posicionar torres."""
    return [
        cell
        for cell in ((x, y) for y in range(9) for x in range(15))
        if cell not in game.map_path.cell_set
    ]


def place_tower(game, cell, ttype):
    """Cria e registra uma torre `ttype` na celula `cell` de `game`,
    retornando a torre. Helper compartilhado entre modulos de teste."""
    game.towers[cell] = Tower(cell[0], cell[1], ttype=ttype)
    return game.towers[cell]


def buy_path_to_tier(game, tower, path_index, tier):
    """Compra o caminho `path_index` de `tower` ate o tier alvo (ou ate
    a compra ser recusada). Retorna (ok, cost, reason) da ULTIMA
    tentativa de compra feita."""
    result = (True, 0, "")
    while tower.tiers[path_index] < tier:
        ok, cost, reason = game.path_purchase_state(tower, path_index)
        result = (ok, cost, reason)
        if not ok:
            break
        game.gold -= cost
        if tower.tiers[path_index] == 5:
            # a compra que leva ao tier 6 tambem cobra gemas
            game.gems -= game.path_upgrade_gem_cost(tower, path_index)
        tower.buy_path(path_index)
    return result
