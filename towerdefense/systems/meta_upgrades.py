"""Loja de gemas: melhorias permanentes dentro da sessao atual, compradas
com o recurso mais raro do jogo (gemas, obtidas matando bosses)."""

from ..config import (
    META_UPGRADE_DEFS, META_UPGRADE_KEYS,
    SECOND_CHANCE_CAP, SECOND_CHANCE_DECAY,
)


class MetaUpgrades:
    """Guarda os niveis comprados de cada melhoria permanente (com gemas)
    durante a sessao de jogo atual."""

    def __init__(self):
        self.levels = {k: 0 for k in META_UPGRADE_KEYS}

    def level(self, key):
        return self.levels.get(key, 0)

    def cost_for_next(self, key):
        spec = META_UPGRADE_DEFS[key]
        lvl = self.levels[key]
        max_lvl = spec["max_level"]
        if max_lvl is not None and lvl >= max_lvl:
            return None  # ja no maximo (upgrades sem teto nunca caem aqui)
        return spec["base_cost"] + lvl * spec["cost_step"]

    def buy(self, key):
        spec = META_UPGRADE_DEFS[key]
        max_lvl = spec["max_level"]
        if max_lvl is not None and self.levels[key] >= max_lvl:
            return False
        self.levels[key] += 1
        return True

    # --- efeitos aplicados no jogo -------------------------------------
    def gold_mult(self):
        return 1.0 + self.levels["gold_gain"] * META_UPGRADE_DEFS["gold_gain"]["effect_per_level"]

    def start_tower_level_bonus(self):
        return self.levels["start_level"] * META_UPGRADE_DEFS["start_level"]["effect_per_level"]

    def tower_cost_mult(self):
        disc = self.levels["tower_cost"] * META_UPGRADE_DEFS["tower_cost"]["effect_per_level"]
        return max(0.25, 1.0 - disc)

    def bonus_starting_gold(self):
        return self.levels["starting_gold"] * META_UPGRADE_DEFS["starting_gold"]["effect_per_level"]

    def second_chance_prob(self):
        """Chance (0..1) de um inimigo que chegaria ao fim voltar pro
        comeco em vez de tirar uma vida. Curva assintotica: cada nivel
        novo soma cada vez menos, e o valor nunca alcanca SECOND_CHANCE_CAP
        (que ja fica longe de 100%) -- e assim que o upgrade continua
        valendo a pena comprar pra sempre (nivel sem teto) sem trivializar
        o jogo.
        """
        lvl = self.levels["extra_lives"]
        if lvl <= 0:
            return 0.0
        return SECOND_CHANCE_CAP * (1.0 - SECOND_CHANCE_DECAY ** lvl)

    def upgrade_cost_mult(self):
        disc = self.levels["upgrade_discount"] * META_UPGRADE_DEFS["upgrade_discount"]["effect_per_level"]
        return max(0.3, 1.0 - disc)
