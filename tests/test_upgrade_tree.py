"""Integridade da arvore de upgrades: todo tipo de torre precisa ter
3 caminhos x 6 tiers, cada tier com nome/descricao, e cada caminho
uma habilidade de tier 6 implementada em ABILITIES."""
import pytest

from towerdefense import upgrades as up
from towerdefense.config import TOWER_TYPE_KEYS
from towerdefense.systems.abilities import ABILITIES


@pytest.mark.parametrize("ttype", TOWER_TYPE_KEYS)
def test_torre_tem_tres_caminhos(ttype):
    assert len(up.UPGRADE_TREE[ttype]) == 3


@pytest.mark.parametrize("ttype", TOWER_TYPE_KEYS)
def test_cada_caminho_tem_seis_tiers_e_habilidade(ttype):
    for path in up.UPGRADE_TREE[ttype]:
        assert len(path["tiers"]) == 6, f"{ttype}/{path['name']} deveria ter 6 tiers"
        assert "ability" in path, f"{ttype}/{path['name']} sem habilidade tier 6"


@pytest.mark.parametrize("ttype", TOWER_TYPE_KEYS)
def test_todo_tier_tem_nome_e_descricao(ttype):
    for path in up.UPGRADE_TREE[ttype]:
        for tier in path["tiers"]:
            assert tier["name"], f"tier sem nome em {ttype}/{path['name']}"
            assert tier["desc"], f"tier sem descricao em {ttype}/{path['name']}"


def test_total_de_evolucoes_e_seis_por_tres_por_tipo():
    total = sum(
        len(path["tiers"])
        for ttype in TOWER_TYPE_KEYS
        for path in up.UPGRADE_TREE[ttype]
    )
    expected = len(TOWER_TYPE_KEYS) * 18
    assert total == expected


@pytest.mark.parametrize("ttype", TOWER_TYPE_KEYS)
@pytest.mark.parametrize("path_index", [0, 1, 2])
def test_habilidade_de_tier_6_esta_implementada(ttype, path_index):
    kind = up.ability_def(ttype, path_index)["kind"]
    assert kind in ABILITIES, f"habilidade '{kind}' sem implementacao"
