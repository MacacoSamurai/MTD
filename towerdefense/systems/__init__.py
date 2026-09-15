"""Sistemas: regras que orquestram entidades ao longo do tempo.

A ordem dos imports aqui NAO e cosmetica: `combat` e `vfx` sao
importados primeiro porque `entities/tower.py` e `entities/projectile.py`
dependem deles, e `abilities` (que importa entities) vem por ultimo --
assim o ciclo entities <-> systems sempre encontra o modulo de que
precisa ja carregado.
"""

from . import combat, vfx
from .waves import WaveManager
from .meta_upgrades import MetaUpgrades
from .abilities import AbilityController

__all__ = ["combat", "vfx", "WaveManager", "MetaUpgrades", "AbilityController"]
