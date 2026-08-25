"""Loja de gemas: melhorias permanentes dentro da sessao atual, compradas
com o recurso mais raro do jogo (gemas, obtidas matando bosses)."""

from ..config import META_UPGRADE_DEFS, META_UPGRADE_KEYS


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
        if lvl >= spec["max_level"]:
            return None  # ja no maximo
        return spec["base_cost"] + lvl * spec["cost_step"]

    def buy(self, key):
        spec = META_UPGRADE_DEFS[key]
        if self.levels[key] >= spec["max_level"]:
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

    def bonus_lives(self):
        return int(self.levels["extra_lives"] * META_UPGRADE_DEFS["extra_lives"]["effect_per_level"])

    def upgrade_cost_mult(self):
        disc = self.levels["upgrade_discount"] * META_UPGRADE_DEFS["upgrade_discount"]["effect_per_level"]
        return max(0.3, 1.0 - disc)
