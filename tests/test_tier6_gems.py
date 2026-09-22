"""Tier 6 exige gemas (nao ha mais limite de "1 por tipo"): varias
torres do mesmo tipo podem chegar a tier 6, desde que o jogador pague
o custo em gemas de cada uma. Cobre tambem que o caminho secundario
trava no tier 2 e que o terceiro caminho fica fechado."""
from tests.conftest import buy_path_to_tier, place_tower


def test_segunda_torre_do_mesmo_tipo_pode_chegar_a_tier_6(game, free_cells):
    t1 = place_tower(game, free_cells[0], "canhao")
    buy_path_to_tier(game, t1, 0, 6)
    assert t1.tiers[0] == 6
    assert t1.has_ability

    t2 = place_tower(game, free_cells[7], "canhao")
    ok, cost, reason = buy_path_to_tier(game, t2, 0, 6)
    assert ok, f"2o tier 6 de canhao deveria ser permitido, tendo gemas ({reason})"
    assert t2.tiers[0] == 6
    assert t2.has_ability


def test_tier_6_e_recusado_sem_gemas_mesmo_com_ouro_sobrando(game, free_cells):
    t = place_tower(game, free_cells[0], "canhao")
    buy_path_to_tier(game, t, 0, 5)
    assert t.tiers[0] == 5

    game.gems = 0
    ok, _cost, reason = game.path_purchase_state(t, 0)
    assert not ok
    assert "gemas" in reason


def test_secundario_trava_no_tier_2_apos_principal_no_tier_6(game, free_cells):
    t = place_tower(game, free_cells[0], "canhao")
    buy_path_to_tier(game, t, 0, 6)

    ok, cost, reason = buy_path_to_tier(game, t, 1, 2)
    assert ok, f"crosspath ate o tier 2 deveria ser permitido ({reason})"
    assert t.tiers[1] == 2

    ok2, _cost2, reason2 = game.path_purchase_state(t, 1)
    assert not ok2
    assert "tier 2" in reason2


def test_terceiro_caminho_fechado_com_dois_ja_investidos(game, free_cells):
    t = place_tower(game, free_cells[0], "canhao")
    buy_path_to_tier(game, t, 0, 6)
    buy_path_to_tier(game, t, 1, 2)
    assert game.path_purchase_state(t, 2)[0] is False
