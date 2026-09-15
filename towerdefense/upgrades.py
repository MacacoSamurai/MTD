"""
ARVORE DE EVOLUCAO DAS TORRES (estilo Bloons TD 6).

Este modulo e 100% DADOS + regras puras de caminho/crosspath. Nao
desenha nada e nao conhece `Game`, `Tower` ou pygame -- exatamente como
`config.py`, so que grande demais pra caber la dentro sem virar um
arquivo ilegivel.

ESTRUTURA
---------
Cada tipo de torre (as 5 chaves de `TOWER_TYPES`) tem 3 caminhos
independentes; cada caminho tem 6 tiers. A configuracao de uma torre e
sempre uma tupla de 3 inteiros 0..6, na mesma notacao do BTD6:

    (6, 0, 0) -> tier 6 do primeiro caminho
    (5, 2, 0) -> tier 5 do primeiro + crosspath tier 2 no segundo

REGRAS DE CROSSPATH (ver `can_upgrade`)
---------------------------------------
1. No maximo DOIS caminhos podem sair do zero.
2. No maximo UM caminho pode passar do tier 2 (o "principal").
3. O caminho secundario fica travado no tier 2.
4. Tier 6 so e liberado num caminho que ja esteja no tier 5.
5. Tier 6 tem ainda uma regra GLOBAL de partida (uma unica torre tier 6
   por TIPO de torre) que NAO mora aqui -- ela depende do estado da
   partida inteira e vive em `Game` (ver `Game.tier6_blocked_reason`).

EFEITOS (`mods`)
----------------
Cada tier carrega um dicionario `mods` com os efeitos que ele adiciona.
Os mods de todos os tiers comprados sao combinados por `combine_mods` e
aplicados em `Tower.recalc_stats`. As chaves seguem sufixos com
significado fixo, pra combinacao ser mecanica (sem if por upgrade):

    *_mult   -> multiplicam entre si (1.0 = neutro)
    *_add    -> somam (0 = neutro)
    *_chance -> somam, saturando em 1.0
    slow_factor        -> vence o MENOR (lentidao mais forte)
    *_time / *_amp     -> vence o MAIOR
    booleanos          -> OR

Adicionar um efeito novo = escolher um nome com um desses sufixos, usar
em algum tier aqui, e ler `tower.mods[...]` em entities/tower.py (ou em
projectile.py, via o payload do projetil).
"""

# ----------------------------------------------------------------------------
# CUSTOS
# Custo base por tier (indice 0 = tier 1), multiplicado pelo fator do tipo
# de torre. Tier 6 e deliberadamente caro: e a "super torre" da partida.
# ----------------------------------------------------------------------------
TIER_COSTS = [90, 220, 560, 1500, 4200, 15000]

TYPE_COST_FACTOR = {
    "canhao": 1.00,
    "flecha": 0.85,
    "gelo": 0.90,
    "canhao_pesado": 1.25,
    "sniper": 1.15,
}

# Cor de cada caminho (usada na UI e no brilho da torre especializada).
PATH_COLORS = {
    "canhao": [(255, 120, 70), (255, 210, 90), (120, 200, 255)],
    "flecha": [(140, 230, 120), (255, 160, 90), (190, 130, 255)],
    "gelo": [(150, 225, 255), (110, 160, 255), (200, 240, 255)],
    "canhao_pesado": [(255, 110, 80), (255, 190, 90), (200, 120, 255)],
    "sniper": [(255, 90, 140), (255, 200, 120), (120, 230, 220)],
}

MAX_TIER = 6
CROSSPATH_MAX = 2  # tier maximo de um caminho secundario


def _u(name, desc, **mods):
    """Atalho pra declarar um tier: nome, descricao curta e os mods."""
    return {"name": name, "desc": desc, "mods": mods}


def _ability(name, desc, kind, cooldown, duration=0.0, **extra):
    d = {"name": name, "desc": desc, "kind": kind,
         "cooldown": cooldown, "duration": duration}
    d.update(extra)
    return d


# ============================================================================
# 1. CANHAO -- torre equilibrada, tiros explosivos
# ============================================================================
_CANHAO = [
    {
        "name": "Demolidor",
        "short": "Explosao e dano bruto",
        "tiers": [
            _u("Polvora Reforcada", "Mais dano no projetil e na explosao.",
               damage_mult=1.30),
            _u("Municao Explosiva", "Aumenta o raio da explosao.",
               splash_add=16, splash_mult=1.15),
            _u("Granada Fragmentada", "A explosao libera estilhacos em varias direcoes.",
               frag_count=6, frag_damage=0.35),
            _u("Artilharia Pesada", "Dano e explosao muito maiores, mas dispara mais devagar.",
               damage_mult=1.85, splash_add=22, rate_mult=1.35, frag_count=2),
            _u("Canhao Demolidor", "Explosoes enormes, especialista em destruir grupos.",
               damage_mult=2.30, splash_add=34, splash_mult=1.2, frag_count=4, frag_damage=0.45),
            _u("CANHAO APOCALIPTICO", "Explosoes colossais com detonacoes secundarias.",
               damage_mult=3.40, splash_add=48, splash_mult=1.25,
               frag_count=8, frag_damage=0.55, secondary_blasts=2),
        ],
        "ability": _ability(
            "APOCALIPSE",
            "Lanca uma ogiva na maior concentracao de inimigos: explosao colossal "
            "seguida de varias explosoes secundarias.",
            "apocalipse", cooldown=26.0),
    },
    {
        "name": "Artilheiro",
        "short": "Cadencia e volume de fogo",
        "tiers": [
            _u("Recarga Rapida", "Aumenta a velocidade de ataque.",
               rate_mult=0.78),
            _u("Carregador Duplo", "Cada ataque dispara dois projeteis.",
               shots_add=1),
            _u("Rajada de Canhoes", "Dispara tres projeteis em rapida sucessao.",
               burst_add=2, rate_mult=0.92),
            _u("Artilharia Automatica", "Intervalo entre disparos muito menor.",
               rate_mult=0.58),
            _u("Metralhadora de Cerco", "Torrente de tiros explosivos; cada um doi menos.",
               rate_mult=0.55, shots_add=1, damage_mult=0.80, splash_add=10),
            _u("DEUS DA ARTILHARIA", "Volume de fogo absurdo, explosao em cada disparo.",
               rate_mult=0.45, shots_add=2, burst_add=1, damage_mult=1.05, splash_add=18),
        ],
        "ability": _ability(
            "BARRAGEM INFINITA",
            "Entra em modo de bombardeio e castiga sem parar as regioes com mais inimigos.",
            "barragem", cooldown=30.0, duration=6.0),
    },
    {
        "name": "Engenheiro de Cerco",
        "short": "Alcance, precisao e suporte",
        "tiers": [
            _u("Mira Aprimorada", "Aumenta o alcance.",
               range_mult=1.22),
            _u("Mira de Precisao", "Projeteis mais rapidos e precisos.",
               proj_speed_mult=1.5, damage_mult=1.12),
            _u("Mira Longa", "Aumenta muito o alcance.",
               range_mult=1.40),
            _u("Marcador de Alvos", "Inimigos atingidos ficam marcados e sofrem mais dano.",
               mark_on_hit=True, mark_amp=0.25, mark_time=4.0),
            _u("Torre de Cerco", "Alcance gigantesco; projeteis atravessam varios inimigos.",
               range_mult=1.45, pierce_add=3, damage_mult=1.45, proj_speed_mult=1.3),
            _u("SENTINELA DO FIM", "Alcance colossal, projeteis velocissimos e perfurantes.",
               range_mult=1.70, pierce_add=6, damage_mult=1.80,
               proj_speed_mult=1.8, mark_on_hit=True, mark_amp=0.45, mark_time=6.0),
        ],
        "ability": _ability(
            "OLHO DO APOCALIPSE",
            "Marca os inimigos mais perigosos da pista, deixando-os extremamente "
            "vulneraveis por alguns segundos.",
            "olho_apocalipse", cooldown=28.0, duration=8.0),
    },
]

# ============================================================================
# 2. TORRE DE FLECHAS -- cadencia altissima, dano baixo por tiro
# ============================================================================
_FLECHA = [
    {
        "name": "Atirador",
        "short": "Transformar volume em dano",
        "tiers": [
            _u("Flechas Afiadas", "Aumenta o dano.", damage_mult=1.35),
            _u("Flechas Perfurantes", "Cada flecha atravessa mais inimigos.", pierce_add=2),
            _u("Flechas Serrilhadas", "Flechas causam dano ao longo do tempo.",
               dot_dps=0.55, dot_time=3.0),
            _u("Chuva de Flechas", "Cada ataque dispara varias flechas.",
               shots_add=2, damage_mult=1.15),
            _u("Tempestade de Flechas", "Quantidade enorme de flechas cobrindo uma grande area.",
               shots_add=3, range_mult=1.15, damage_mult=1.35, pierce_add=1),
            _u("TEMPESTADE CELESTIAL", "Flechas sem fim, perfurantes e que ricocheteiam.",
               shots_add=4, damage_mult=2.10, pierce_add=3, ricochet=2,
               rate_mult=0.80, range_mult=1.20),
        ],
        "ability": _ability(
            "CHUVA DO APOCALIPSE",
            "Uma chuva massiva de flechas cai sobre a pista, atingindo repetidamente "
            "todos os inimigos da area.",
            "chuva_flechas", cooldown=26.0, duration=5.0),
    },
    {
        "name": "Cacador",
        "short": "Eliminar alvos prioritarios",
        "tiers": [
            _u("Mira Rapida", "Aumenta o alcance.", range_mult=1.20),
            _u("Mira Avancada", "Passa a priorizar os inimigos mais fortes.",
               target_priority="strongest"),
            _u("Flecha Perseguidora", "As flechas perseguem o alvo.",
               homing=True, proj_speed_mult=1.2),
            _u("Cacador de Elite", "Dano muito maior contra inimigos de elite e chefes.",
               heavy_mult=1.90),
            _u("Mestre Cacador", "Procura sozinho os alvos mais perigosos e os castiga.",
               heavy_mult=2.40, damage_mult=1.40, target_priority="strongest"),
            _u("DESTRUIDOR CELESTIAL", "Perseguicao implacavel e dano brutal em alvos prioritarios.",
               heavy_mult=3.20, damage_mult=1.90, homing=True,
               target_priority="strongest", rate_mult=0.80, pierce_add=1),
        ],
        "ability": _ability(
            "CACADA SUPREMA",
            "Escolhe o inimigo mais poderoso da pista e despeja nele uma sequencia "
            "devastadora de flechas.",
            "cacada_suprema", cooldown=24.0, duration=3.0),
    },
    {
        "name": "Arqueiro Tatico",
        "short": "Efeitos elementais",
        "tiers": [
            _u("Flechas Incendiarias", "Aplica queimadura.", burn_dps=0.50, burn_time=3.0),
            _u("Flechas Congelantes", "Chance de reduzir a velocidade dos inimigos.",
               slow_factor=0.70, slow_time=1.6, slow_chance=0.45),
            _u("Flechas Envenenadas", "Aplica veneno acumulavel.",
               poison_dps=0.35, poison_time=4.0, poison_stack_max=5),
            _u("Arsenal Elemental", "Alterna entre fogo, gelo e veneno a cada disparo.",
               elemental_cycle=True, damage_mult=1.20),
            _u("Flechas Ancestrais", "Cada flecha aplica varios efeitos e atravessa inimigos.",
               elemental_all=True, pierce_add=3, damage_mult=1.35,
               burn_dps=0.75, poison_dps=0.55, slow_chance=0.8),
            _u("ARQUEIRO DIVINO", "Mestre dos elementos: fogo, gelo e veneno em cada ataque.",
               elemental_all=True, damage_mult=1.80, pierce_add=4,
               burn_dps=1.20, burn_time=4.0, poison_dps=0.90, poison_stack_max=8,
               slow_factor=0.55, slow_time=2.5, slow_chance=1.0,
               mark_on_hit=True, mark_amp=0.30, mark_time=3.0),
        ],
        "ability": _ability(
            "IRA DOS ELEMENTOS",
            "Por alguns segundos cada ataque queima, congela e envenena ao mesmo tempo, "
            "com pulsos elementais na area.",
            "ira_elementos", cooldown=28.0, duration=6.0),
    },
]

# ============================================================================
# 3. TORRE DE GELO -- controle; todo inimigo atingido e desacelerado
# ============================================================================
_GELO = [
    {
        "name": "Congelador",
        "short": "Controle extremo",
        "tiers": [
            _u("Frio Intenso", "Lentidao mais intensa.", slow_factor=0.45),
            _u("Gelo Pegajoso", "A lentidao dura mais tempo.", slow_time=3.0),
            _u("Congelamento", "Inimigos podem ficar completamente paralisados.",
               freeze_chance=0.25, freeze_time=1.0),
            _u("Geada Profunda", "A area de efeito aumenta e atinge inimigos proximos.",
               splash_add=30, freeze_chance=0.35, range_mult=1.12),
            _u("Era Glacial", "Mantem uma enorme area permanentemente congelada.",
               freeze_chance=0.55, freeze_time=1.4, splash_add=24,
               aura_slow_factor=0.65, aura_radius_mult=0.85),
            _u("SENHOR DA ERA GLACIAL", "Zona de congelamento extremo ao redor da torre.",
               freeze_chance=0.85, freeze_time=2.0, slow_factor=0.30, slow_time=4.0,
               splash_add=40, range_mult=1.30,
               aura_slow_factor=0.45, aura_radius_mult=1.0, aura_freeze_chance=0.20),
        ],
        "ability": _ability(
            "ERA DO GELO",
            "Congela todos os inimigos da pista. Inimigos muito resistentes sofrem "
            "uma reducao enorme de velocidade no lugar do congelamento.",
            "era_do_gelo", cooldown=30.0, duration=5.0),
    },
    {
        "name": "Criomante",
        "short": "Gelo como fonte de dano",
        "tiers": [
            _u("Estilhacos", "Inimigos congelados recebem dano adicional.",
               bonus_vs_frozen=1.50),
            _u("Gelo Cortante", "Aumenta o dano dos ataques.", damage_mult=1.60),
            _u("Explosao de Gelo", "Congelados explodem ao serem destruidos.",
               frozen_explode=0.80),
            _u("Tempestade de Gelo", "Aumenta muito a area de ataque.",
               splash_add=34, splash_mult=1.2, range_mult=1.12),
            _u("Coracao Glacial", "Congelados sofrem dano continuo altissimo.",
               damage_mult=1.70, dot_dps=1.10, dot_time=3.0, bonus_vs_frozen=1.8),
            _u("CORACAO DO INVERNO ETERNO", "Gelo vira uma fonte massiva de dano em area.",
               damage_mult=2.60, splash_add=40, dot_dps=1.60, dot_time=4.0,
               bonus_vs_frozen=2.2, frozen_explode=1.40, freeze_chance=0.35,
               freeze_time=1.2, aura_damage_dps=0.35, aura_radius_mult=0.9),
        ],
        "ability": _ability(
            "SUPERNOVA GLACIAL",
            "Explosao gigantesca de gelo: dano massivo e congelamento em todos os "
            "inimigos atingidos.",
            "supernova", cooldown=26.0),
    },
    {
        "name": "Permafrost",
        "short": "Debuff e suporte",
        "tiers": [
            _u("Frio Persistente", "Os efeitos duram mais tempo.",
               slow_time=3.2, mark_time=3.0),
            _u("Armadura Congelada", "Reduz a resistencia dos inimigos atingidos.",
               armor_shred=6),
            _u("Quebra-Gelo", "Inimigos lentos recebem mais dano de todas as torres.",
               mark_on_hit=True, mark_amp=0.22, mark_time=3.5),
            _u("Campo de Permafrost", "Cria uma area que enfraquece todos os inimigos.",
               aura_slow_factor=0.72, aura_vuln_amp=0.20, aura_radius_mult=0.9),
            _u("Senhor do Inverno", "Na area, inimigos ficam lentissimos e vulneraveis.",
               aura_slow_factor=0.55, aura_vuln_amp=0.35, aura_armor_shred=8,
               aura_radius_mult=1.05, range_mult=1.15),
            _u("DEUS DO PERMAFROST", "Area gigantesca de lentidao, resistencia quebrada e "
               "vulnerabilidade extrema.",
               aura_slow_factor=0.40, aura_vuln_amp=0.60, aura_armor_shred=14,
               aura_radius_mult=1.45, range_mult=1.35, armor_shred=12,
               mark_on_hit=True, mark_amp=0.50, mark_time=5.0, damage_mult=1.30),
        ],
        "ability": _ability(
            "DOMINIO ETERNO",
            "A pista inteira entra no dominio do Permafrost: todos os inimigos ficam "
            "lentissimos e recebem muito mais dano de todas as torres.",
            "dominio_eterno", cooldown=34.0, duration=8.0),
    },
]

# ============================================================================
# 4. CANHAO PESADO -- tiro lento e caro, dano gigante em area
# ============================================================================
_CANHAO_PESADO = [
    {
        "name": "Megaexplosao",
        "short": "Explosao maxima",
        "tiers": [
            _u("Carga Pesada", "Aumenta o dano.", damage_mult=1.35),
            _u("Explosivo Instavel", "Aumenta o tamanho da explosao.",
               splash_add=20, splash_mult=1.15),
            _u("Ogiva", "Aumenta enormemente o dano.", damage_mult=1.90),
            _u("Superexplosivo", "As explosoes passam a limpar grandes grupos.",
               splash_add=30, splash_mult=1.2, frag_count=4, frag_damage=0.4),
            _u("Cataclismo", "Cada disparo e uma explosao colossal.",
               damage_mult=2.20, splash_add=40, secondary_blasts=1),
            _u("DESTRUIDOR DE MUNDOS", "A maior arma de area do jogo; cadencia baixissima.",
               damage_mult=3.60, splash_add=60, splash_mult=1.3,
               secondary_blasts=3, frag_count=8, frag_damage=0.5, rate_mult=1.20),
        ],
        "ability": _ability(
            "FIM DOS TEMPOS",
            "Dispara uma superogiva que provoca uma sequencia de explosoes devastadoras.",
            "fim_dos_tempos", cooldown=32.0),
    },
    {
        "name": "Artilharia",
        "short": "Corrigir a cadencia baixa",
        "tiers": [
            _u("Recarga Reforcada", "Reduz o tempo de recarga.", rate_mult=0.80),
            _u("Carregamento Automatico", "Reduz ainda mais a recarga.", rate_mult=0.78),
            _u("Canhao Duplo", "Dispara duas cargas por ataque.", shots_add=1),
            _u("Bateria de Artilharia", "Dispara varias cargas em sequencia.",
               burst_add=2, rate_mult=0.88),
            _u("Bombardeio", "Solta uma barragem de projeteis por ataque.",
               shots_add=2, burst_add=1, damage_mult=0.85, splash_add=12),
            _u("LEGIONARIO DA ARTILHARIA", "Uma bateria inteira numa torre so.",
               shots_add=3, burst_add=2, rate_mult=0.60,
               damage_mult=1.20, splash_add=24, range_mult=1.20),
        ],
        "ability": _ability(
            "BOMBARDEIO TOTAL",
            "Por alguns segundos, dezenas de projeteis caem continuamente sobre a pista.",
            "bombardeio_total", cooldown=32.0, duration=7.0),
    },
    {
        "name": "Especialista em Colossos",
        "short": "Contra gigantes e chefes",
        "tiers": [
            _u("Municao Perfurante", "Ignora parte da armadura.", armor_shred=10),
            _u("Projetil Anti-Blindagem", "Mais dano contra inimigos pesados.",
               heavy_mult=1.60),
            _u("Ogiva Perfurante", "Projeteis atravessam inimigos grandes.",
               pierce_add=3, armor_shred=8),
            _u("Caca-Colossos", "Dano enormemente maior contra inimigos pesados.",
               heavy_mult=2.40, armor_pierce=True),
            _u("Exterminador", "Dano gigantesco em pesados, mas fraco contra pequenos.",
               heavy_mult=3.20, small_mult=0.65, armor_pierce=True, damage_mult=1.30),
            _u("EXECUTOR TITANICO", "A arma definitiva contra os maiores inimigos.",
               heavy_mult=4.50, small_mult=0.55, armor_pierce=True,
               damage_mult=1.80, pierce_add=5, target_priority="strongest"),
        ],
        "ability": _ability(
            "EXECUCAO TITANICA",
            "Identifica o inimigo pesado mais perigoso e dispara uma municao especial "
            "de dano massivo.",
            "execucao_titanica", cooldown=24.0),
    },
]

# ============================================================================
# 5. SNIPER -- alcance enorme, dano alto, ignora armadura
# ============================================================================
_SNIPER = [
    {
        "name": "Atirador de Elite",
        "short": "Dano de alvo unico",
        "tiers": [
            _u("Mira Precisa", "Aumenta o dano.", damage_mult=1.40),
            _u("Tiro Critico", "Chance de causar dano multiplicado.",
               crit_chance=0.20, crit_mult=2.2),
            _u("Ponto Fraco", "Mais dano contra inimigos ja feridos.",
               wounded_mult=1.60),
            _u("Atirador de Elite", "Muito mais dano e chance de critico.",
               damage_mult=1.70, crit_chance=0.20, crit_mult=2.8),
            _u("Lenda do Tiro", "Criticos arrasadores, capazes de fulminar inimigos comuns.",
               damage_mult=1.80, crit_chance=0.20, crit_mult=4.0, execute_small=True),
            _u("DEUS DO TIRO", "O apice do dano de alvo unico.",
               damage_mult=2.60, crit_chance=0.25, crit_mult=6.0,
               execute_small=True, armor_pierce=True, heavy_mult=1.80,
               target_priority="strongest"),
        ],
        "ability": _ability(
            "TIRO DIVINO",
            "Encontra o inimigo mais poderoso da pista e dispara uma bala que ignora "
            "praticamente todas as defesas.",
            "tiro_divino", cooldown=22.0),
    },
    {
        "name": "Sniper Automatico",
        "short": "Cadencia",
        "tiers": [
            _u("Recarga Rapida", "Aumenta a velocidade de ataque.", rate_mult=0.78),
            _u("Ferrolho Automatico", "Aumenta ainda mais a velocidade.", rate_mult=0.75),
            _u("Semiautomatico", "Dispara em rapida sucessao.", burst_add=1, rate_mult=0.90),
            _u("Automatico", "Cadencia extremamente alta.", rate_mult=0.55),
            _u("Metralhadora de Precisao", "Fogo continuo sem abrir mao do alcance.",
               rate_mult=0.62, burst_add=1, damage_mult=0.90, range_mult=1.10),
            _u("LEGIONARIO DE FERRO", "Plataforma de fogo continuo com alcance extremo.",
               rate_mult=0.42, burst_add=2, damage_mult=1.35,
               range_mult=1.25, armor_pierce=True),
        ],
        "ability": _ability(
            "EXECUCAO AUTOMATICA",
            "Por alguns segundos dispara quase sem intervalo, trocando sozinho entre "
            "os inimigos mais perigosos.",
            "execucao_automatica", cooldown=26.0, duration=5.0),
    },
    {
        "name": "Observador",
        "short": "Alcance, informacao e suporte",
        "tiers": [
            _u("Binoculo", "Aumenta o alcance.", range_mult=1.25),
            _u("Visao Tatica", "Detecta inimigos esquivos/camuflados.", camo_detect=True),
            _u("Marcador", "Inimigos atingidos ficam marcados.",
               mark_on_hit=True, mark_amp=0.20, mark_time=4.0),
            _u("Comandante de Campo", "Marcados recebem mais dano de todas as torres.",
               mark_amp=0.40, mark_time=5.0),
            _u("Olho do Exercito", "Revela e marca alvos prioritarios, ampliando o dano neles.",
               mark_amp=0.60, mark_time=6.0, camo_detect=True,
               range_mult=1.30, target_priority="strongest"),
            _u("OLHO DE DEUS", "Alcance praticamente global; marca sozinho os alvos prioritarios.",
               range_mult=3.00, mark_on_hit=True, mark_amp=0.90, mark_time=8.0,
               camo_detect=True, armor_pierce=True, damage_mult=1.40,
               target_priority="strongest", aura_mark_amp=0.30, aura_radius_mult=1.0),
        ],
        "ability": _ability(
            "VISAO ABSOLUTA",
            "Revela e marca todos os inimigos da pista, que passam a receber um enorme "
            "multiplicador de dano de todas as torres.",
            "visao_absoluta", cooldown=30.0, duration=8.0),
    },
]

UPGRADE_TREE = {
    "canhao": _CANHAO,
    "flecha": _FLECHA,
    "gelo": _GELO,
    "canhao_pesado": _CANHAO_PESADO,
    "sniper": _SNIPER,
}


# ----------------------------------------------------------------------------
# CONSULTAS
# ----------------------------------------------------------------------------
def path_def(ttype, path_index):
    return UPGRADE_TREE[ttype][path_index]


def tier_def(ttype, path_index, tier):
    """`tier` e 1..6 (o tier 0 nao existe como upgrade, e o estado inicial)."""
    return UPGRADE_TREE[ttype][path_index]["tiers"][tier - 1]


def ability_def(ttype, path_index):
    return UPGRADE_TREE[ttype][path_index]["ability"]


def tier_cost(ttype, tier):
    return int(round(TIER_COSTS[tier - 1] * TYPE_COST_FACTOR.get(ttype, 1.0)))


def main_path(tiers):
    """Indice do caminho de especializacao (o de maior tier), ou None se a
    torre ainda nao investiu em nada."""
    best = max(tiers)
    if best == 0:
        return None
    return tiers.index(best)


def is_tier6(tiers):
    return max(tiers) >= MAX_TIER


def total_tiers(tiers):
    return sum(tiers)


# ----------------------------------------------------------------------------
# REGRAS DE CROSSPATH
# ----------------------------------------------------------------------------
def can_upgrade(tiers, path_index):
    """Retorna (True, "") se comprar o proximo tier de `path_index` e legal
    pelas regras de crosspath, ou (False, motivo) explicando o bloqueio.

    NAO cobre a regra global de "um tier 6 por tipo na partida" -- essa
    depende do estado da partida e e checada em `Game`.
    """
    cur = tiers[path_index]
    if cur >= MAX_TIER:
        return False, "Caminho ja esta no tier maximo"

    nxt = cur + 1
    others = [t for i, t in enumerate(tiers) if i != path_index]
    opened = [t for t in others if t > 0]

    # regra 1: no maximo dois caminhos abertos
    if cur == 0 and len(opened) >= 2:
        return False, "Uma torre so pode abrir dois caminhos"

    # regra 2/3: so um caminho pode passar do tier 2
    if nxt > CROSSPATH_MAX and any(t > CROSSPATH_MAX for t in others):
        return False, f"Caminho secundario trava no tier {CROSSPATH_MAX}"

    # regra 4: tier 6 exige tier 5 no mesmo caminho (garantido por nxt)
    return True, ""


def is_legal_config(tiers):
    """Valida uma configuracao inteira (usada no merge, que combina os
    tiers de duas torres e pode gerar algo ilegal)."""
    opened = [t for t in tiers if t > 0]
    if len(opened) > 2:
        return False
    if sum(1 for t in tiers if t > CROSSPATH_MAX) > 1:
        return False
    return all(0 <= t <= MAX_TIER for t in tiers)


# ----------------------------------------------------------------------------
# COMBINACAO DE MODS
# ----------------------------------------------------------------------------
_MIN_KEYS = ("slow_factor", "aura_slow_factor", "small_mult")


def combine_mods(mod_dicts):
    """Funde varios dicionarios de mods num so, seguindo o significado do
    sufixo de cada chave (ver docstring do modulo)."""
    out = {}
    for mods in mod_dicts:
        for key, val in mods.items():
            if key not in out:
                out[key] = val
                continue
            cur = out[key]
            if isinstance(val, bool):
                out[key] = cur or val
            elif isinstance(val, str):
                out[key] = val
            elif key in _MIN_KEYS:
                out[key] = min(cur, val)
            elif key.endswith("_mult"):
                out[key] = cur * val
            elif key.endswith("_chance"):
                out[key] = min(1.0, cur + val)
            elif key.endswith("_time") or key.endswith("_amp"):
                out[key] = max(cur, val)
            else:  # *_add, contagens (frag_count, pierce_add, shots_add...)
                out[key] = cur + val
    return out


def mods_for(ttype, tiers):
    """Mods acumulados de TODOS os tiers ja comprados da torre."""
    collected = []
    for path_index, tier in enumerate(tiers):
        for t in range(1, tier + 1):
            collected.append(tier_def(ttype, path_index, t)["mods"])
    return combine_mods(collected)
