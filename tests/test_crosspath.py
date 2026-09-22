"""Regras de crosspath: quantos caminhos podem abrir e onde o
caminho secundario trava."""
from towerdefense import upgrades as up


def test_pode_abrir_primeiro_caminho():
    assert up.can_upgrade([0, 0, 0], 0)[0]


def test_terceiro_caminho_bloqueado_quando_dois_ja_abertos():
    assert up.can_upgrade([2, 2, 0], 2)[0] is False


def test_secundario_trava_no_tier_2():
    assert up.can_upgrade([3, 2, 0], 1)[0] is False


def test_principal_continua_subindo_com_secundario_aberto():
    assert up.can_upgrade([3, 2, 0], 0)[0]


def test_tier_6_permitido_no_principal():
    assert up.can_upgrade([5, 2, 0], 0)[0]


def test_tier_6_e_o_maximo():
    assert up.can_upgrade([6, 2, 0], 0)[0] is False


def test_config_5_5_0_e_ilegal():
    assert up.is_legal_config([5, 5, 0]) is False


def test_config_5_2_0_e_legal():
    assert up.is_legal_config([5, 2, 0])


def test_tres_caminhos_abertos_e_ilegal():
    assert up.is_legal_config([1, 1, 1]) is False
