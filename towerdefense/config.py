"""
Configuracoes gerais e constantes do jogo.

Nenhuma logica mora aqui - apenas numeros, cores e tabelas de dados
que os outros modulos importam. Manter tudo centralizado facilita
balancear o jogo sem precisar mexer no codigo de comportamento.
"""

# ----------------------------------------------------------------------------
# JANELA / GRADE
# ----------------------------------------------------------------------------
WIDTH, HEIGHT = 1280, 800
FPS = 60

# A grade cobre toda a area de jogo (o caminho serpenteia por dentro dela).
# Torres so podem ser construidas em celulas que NAO fazem parte do caminho.
GRID_COLS = 15
GRID_ROWS = 9
CELL_SIZE = 72
TOP_HUD_HEIGHT = 90
BOTTOM_HUD_HEIGHT = 70

GRID_ORIGIN_X = (WIDTH - GRID_COLS * CELL_SIZE) // 2
GRID_ORIGIN_Y = TOP_HUD_HEIGHT

PANEL_WIDTH = WIDTH  # mantido por compatibilidade com HUD que usa toda a largura

# ----------------------------------------------------------------------------
# PAINEL LATERAL DE TORRES (estilo Bloons TD)
# Fica sobreposto na frente do grid (nao redimensiona a area de jogo).
# Pode abrir/fechar deslizando; quando fechado fica totalmente fora da tela.
# ----------------------------------------------------------------------------
TOWER_PANEL_WIDTH = 230
TOWER_PANEL_CARD_H = 96
TOWER_PANEL_CARD_GAP = 10
TOWER_PANEL_SLIDE_SPEED = 1900  # px/s da animacao de abrir/fechar
TOWER_PANEL_DOUBLE_CLICK_MS = 400  # janela para o "2 cliques = auto-coloca"

# ----------------------------------------------------------------------------
# ECONOMIA / REGRAS GERAIS
# ----------------------------------------------------------------------------
STARTING_GOLD = 220
STARTING_LIVES = 20
TOWER_BASE_COST = 60
SKIP_WAVE_BASE_BONUS = 40   # ouro extra ganho ao pular a onda
SKIP_WAVE_BONUS_PER_WAVE = 6  # cresce um pouco a cada onda

# Melhorias especificas de torre (menu de upgrade por clique).
# Cada ponto aplica um incremento percentual sobre a stat ja calculada
# pelo nivel/merge. O custo de cada ponto cresce exponencialmente.
UPGRADE_DAMAGE_PCT = 0.18   # +18% de dano por ponto
UPGRADE_RANGE_PCT = 0.08    # +8% de alcance por ponto
UPGRADE_RATE_PCT = 0.10     # -10% no intervalo entre tiros por ponto
UPGRADE_BASE_COST = {"damage": 35, "range": 25, "rate": 40}
UPGRADE_LABELS = {"damage": "Dano", "range": "Alcance", "rate": "Cadencia"}
CLICK_DRAG_THRESHOLD = 8  # pixels; abaixo disso, soltar o mouse conta como clique

BOSS_WAVE_INTERVAL = 10  # a cada quantas ondas surge um boss
BOSS_HP_SCALE_PER_CYCLE = 0.55  # bosses ficam mais fortes a cada ciclo de 10 ondas
BOSS_GEMS_PER_CYCLE = 1  # gemas extras a cada ciclo de boss (alem da base)

# ----------------------------------------------------------------------------
# CORES
# ----------------------------------------------------------------------------
COL_BG = (18, 22, 30)
COL_PANEL = (26, 32, 44)
COL_PATH = (72, 60, 44)
COL_PATH_EDGE = (50, 40, 28)
COL_GRID_EMPTY = (40, 48, 62)
COL_GRID_EMPTY_HOVER = (55, 66, 84)
COL_GRID_BORDER = (60, 70, 90)
COL_TEXT = (235, 235, 240)
COL_TEXT_DIM = (160, 168, 182)
COL_GOLD = (255, 210, 90)
COL_GEM = (120, 220, 255)
COL_HP_BG = (60, 20, 20)
COL_HP_FG = (90, 220, 110)
COL_WHITE = (255, 255, 255)
COL_RED = (230, 70, 70)
COL_GREEN = (90, 220, 110)
COL_MERGE_GLOW = (255, 255, 140)

# Niveis de torre: cores fixas para os primeiros niveis; alem disso a cor
# eh gerada proceduralmente (ciclo de matiz infinito) para nunca "estourar".
TOWER_LEVEL_COLORS = [
    (110, 190, 255),   # nivel 1 - azul claro
    (110, 255, 170),   # nivel 2 - verde
    (255, 220, 90),    # nivel 3 - amarelo
    (255, 150, 70),    # nivel 4 - laranja
    (255, 90, 90),     # nivel 5 - vermelho
    (220, 90, 255),    # nivel 6 - roxo
    (255, 255, 255),   # nivel 7 - branco/lendario
]

TOWER_LEVEL_NAMES = ["Recruta", "Soldado", "Veterano", "Elite", "Campeao", "Mestre", "Lendario"]

# ----------------------------------------------------------------------------
# TIPOS DE TORRE
# Cada tipo tem sua propria progressao de dano/alcance/cadencia e um
# comportamento especial que se intensifica com o nivel (vindo de merges).
# Torres so se fundem com outra do MESMO tipo E MESMO nivel.
# ----------------------------------------------------------------------------
TOWER_TYPES = {
    "canhao": {
        "label": "Canhao",
        "desc": "Dano solido, bom alcance. Equilibrado.",
        "base_color": (110, 190, 255),
        "base_range": 120, "base_damage": 14, "base_rate": 0.70,
        "splash_from_lvl": 3, "splash_base": 24, "splash_step": 6,
        "proj_speed": 420, "proj_shape": "circle",
    },
    "flecha": {
        "label": "Torre de Flechas",
        "desc": "Ataca muito rapido, dano baixo por tiro.",
        "base_color": (140, 230, 120),
        "base_range": 130, "base_damage": 6, "base_rate": 0.28,
        "splash_from_lvl": None, "splash_base": 0, "splash_step": 0,
        "proj_speed": 620, "proj_shape": "arrow",
    },
    "gelo": {
        "label": "Torre de Gelo",
        "desc": "Dano baixo, mas sempre desacelera o alvo.",
        "base_color": (140, 220, 255),
        "base_range": 105, "base_damage": 5, "base_rate": 0.55,
        "splash_from_lvl": 4, "splash_base": 30, "splash_step": 8,
        "proj_speed": 380, "proj_shape": "shard",
        "always_slow": (0.55, 1.0),
    },
    "canhao_pesado": {
        "label": "Canhao Pesado",
        "desc": "Tiro lento e caro, dano gigante em area.",
        "base_color": (255, 140, 70),
        "base_range": 135, "base_damage": 46, "base_rate": 1.35,
        "splash_from_lvl": 1, "splash_base": 34, "splash_step": 7,
        "proj_speed": 340, "proj_shape": "square",
    },
    "sniper": {
        "label": "Sniper",
        "desc": "Alcance enorme, dano alto, cadencia lenta.",
        "base_color": (230, 90, 220),
        "base_range": 260, "base_damage": 38, "base_rate": 1.1,
        "splash_from_lvl": None, "splash_base": 0, "splash_step": 0,
        "proj_speed": 900, "proj_shape": "line",
        "armor_pierce": True,
    },
}
TOWER_TYPE_KEYS = list(TOWER_TYPES.keys())

# ----------------------------------------------------------------------------
# TIPOS DE INIMIGOS
# ----------------------------------------------------------------------------
ENEMY_TYPES = {
    "grunt": {
        "color": (200, 90, 90), "radius": 12, "speed": 60, "hp": 40,
        "gold": 8, "shape": "circle", "min_wave": 1, "armor": 0,
    },
    "runner": {
        "color": (250, 200, 60), "radius": 9, "speed": 120, "hp": 22,
        "gold": 7, "shape": "circle", "min_wave": 2, "armor": 0,
    },
    "tank": {
        "color": (110, 110, 190), "radius": 18, "speed": 34, "hp": 160,
        "gold": 18, "shape": "square", "min_wave": 4, "armor": 4,
    },
    "swarm": {
        "color": (230, 130, 220), "radius": 7, "speed": 95, "hp": 14,
        "gold": 4, "shape": "circle", "min_wave": 3, "armor": 0,
    },
    "brute": {
        "color": (150, 70, 40), "radius": 22, "speed": 40, "hp": 340,
        "gold": 30, "shape": "square", "min_wave": 7, "armor": 8,
    },
    "phantom": {
        "color": (170, 230, 255), "radius": 11, "speed": 85, "hp": 70,
        "gold": 14, "shape": "diamond", "min_wave": 6, "armor": 2,
    },
    "titan": {
        "color": (255, 80, 80), "radius": 28, "speed": 26, "hp": 900,
        "gold": 70, "shape": "square", "min_wave": 12, "armor": 15,
    },
    "boss": {
        "color": (255, 215, 0), "radius": 34, "speed": 22, "hp": 2200,
        "gold": 180, "shape": "star", "min_wave": 10, "armor": 20,
        "is_boss": True, "gems": 3,
    },
}

# ----------------------------------------------------------------------------
# META-UPGRADES (SHOP DE GEMAS)
# Melhorias permanentes DENTRO DA PARTIDA ATUAL, compradas com gemas
# (o recurso mais raro/valioso, obtido matando bosses). Cada upgrade tem
# niveis, custo crescente em gemas, e afeta o jogo inteiro (nao uma
# torre especifica).
# ----------------------------------------------------------------------------
META_UPGRADE_DEFS = {
    "gold_gain": {
        "label": "Ganho de Ouro",
        "desc": "Aumenta todo ouro recebido ao abater inimigos.",
        "icon_color": (255, 210, 90),
        "base_cost": 1, "cost_step": 1,
        "effect_per_level": 0.12,  # +12% por nivel
        "max_level": 20,
    },
    "start_level": {
        "label": "Nivel Inicial das Torres",
        "desc": "Toda torre nova ja nasce em um nivel mais alto.",
        "icon_color": (140, 220, 255),
        "base_cost": 3, "cost_step": 2,
        "effect_per_level": 1,  # +1 nivel inicial por ponto
        "max_level": 8,
    },
    "tower_cost": {
        "label": "Desconto em Torres",
        "desc": "Reduz o preco de compra de novas torres.",
        "icon_color": (140, 255, 170),
        "base_cost": 2, "cost_step": 1,
        "effect_per_level": 0.06,  # -6% de custo por nivel
        "max_level": 10,
    },
    "starting_gold": {
        "label": "Ouro Inicial",
        "desc": "Comeca cada partida com mais ouro no bolso.",
        "icon_color": (255, 180, 60),
        "base_cost": 2, "cost_step": 1,
        "effect_per_level": 50,  # +50 de ouro inicial por ponto
        "max_level": 10,
    },
    "extra_lives": {
        "label": "Vidas Extras",
        "desc": "Aumenta o numero maximo de vidas.",
        "icon_color": (255, 120, 120),
        "base_cost": 2, "cost_step": 2,
        "effect_per_level": 2,  # +2 vidas por ponto
        "max_level": 10,
    },
    "upgrade_discount": {
        "label": "Desconto em Melhorias",
        "desc": "Reduz o custo das melhorias de dano/alcance/cadencia das torres.",
        "icon_color": (220, 140, 255),
        "base_cost": 3, "cost_step": 2,
        "effect_per_level": 0.08,  # -8% de custo por nivel
        "max_level": 8,
    },
}
META_UPGRADE_KEYS = list(META_UPGRADE_DEFS.keys())
