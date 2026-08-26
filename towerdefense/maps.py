"""
Definicoes de mapas.

Cada mapa e um dicionario simples em MAP_DEFS. Para adicionar um mapa
novo basta criar uma entrada nova nesse dict com:

  - "name": nome exibido no menu
  - "desc": descricao curta exibida no menu
  - "difficulty": rotulo de dificuldade ("Facil", "Medio", "Dificil", ...)
  - "difficulty_stars": 1 a 5, usado so para desenhar as estrelinhas do menu
  - "accent_color": cor tematica do card do mapa no menu
  - "path_builder": funcao que recebe (GRID_COLS, GRID_ROWS) e devolve a
    lista de celulas (col, row) do caminho, na ordem que os inimigos
    percorrem. Pode ser qualquer forma (zigue-zague, espiral, cruz...),
    desde que cada passo ande exatamente 1 celula na horizontal/vertical.
  - "hp_mult" / "gold_mult" (opcionais): multiplicadores extras de
    dificuldade aplicados so nesse mapa (alem da progressao normal por
    onda). Default 1.0 quando omitidos.

O resto do jogo nunca precisa saber quantos mapas existem: ele so
consulta MAP_DEFS e MAP_ORDER.
"""


# ----------------------------------------------------------------------
# GERADORES DE CAMINHO
# Cada um recebe (cols, rows) e devolve uma lista de celulas (col, row).
# ----------------------------------------------------------------------
def _path_serpentina(cols, rows):
    """Zigue-zague classico em 'S', cobrindo boa parte da grade."""
    cells = []
    col = 0
    row = 1
    cells.append((col, row))
    direction_down = True
    while col < cols - 1:
        target_row = rows - 2 if direction_down else 1
        while row != target_row:
            row += 1 if direction_down else -1
            cells.append((col, row))
        step = min(3, cols - 1 - col)
        if step <= 0:
            break
        for _ in range(step):
            col += 1
            cells.append((col, row))
        direction_down = not direction_down
    return cells


def _path_reta_dupla(cols, rows):
    """Caminho mais curto e direto: dois trechos retos com uma unica
    curva no meio. Mapa 'facil', da menos tempo de reacao mas exige
    menos torres pra cobrir o percurso todo."""
    cells = []
    row = rows // 2 - 1
    for col in range(0, cols // 2 + 1):
        cells.append((col, row))
    col = cols // 2
    target_row = rows - 2
    while row != target_row:
        row += 1
        cells.append((col, row))
    for c in range(col + 1, cols):
        cells.append((c, row))
    return cells


def _path_espiral(cols, rows):
    """Caminho em espiral fechando para o centro da grade: bem mais
    longo que a serpentina, favorece torres de alcance curto/medio
    espalhadas perto do centro. Mapa 'dificil'."""
    cells = []
    top, bottom = 0, rows - 1
    left, right = 0, cols - 1
    col, row = 0, 0
    cells.append((col, row))

    def move_to(target_col, target_row):
        nonlocal col, row
        while col != target_col:
            col += 1 if target_col > col else -1
            cells.append((col, row))
        while row != target_row:
            row += 1 if target_row > row else -1
            cells.append((col, row))

    while left < right and top < bottom:
        move_to(right, top)
        top += 1
        move_to(right, bottom)
        right -= 1
        move_to(left, bottom)
        bottom -= 1
        move_to(left, top)
        left += 1
        if left < right:
            left += 1
            move_to(left, top)
    return cells


# ----------------------------------------------------------------------
# REGISTRO DE MAPAS
# A ORDEM de MAP_ORDER e a ordem de exibicao no menu. Para adicionar um
# mapa novo: escreva (ou reaproveite) um path_builder acima, adicione
# uma entrada em MAP_DEFS e o id em MAP_ORDER. So isso.
# ----------------------------------------------------------------------
MAP_DEFS = {
    "planicie": {
        "name": "Planicie",
        "desc": "Caminho curto e direto. Ideal para aprender o jogo.",
        "difficulty": "Facil",
        "difficulty_stars": 1,
        "accent_color": (110, 220, 140),
        "path_builder": _path_reta_dupla,
    },
    "serpentina": {
        "name": "Serpentina",
        "desc": "O zigue-zague classico, equilibrado entre espaco e desafio.",
        "difficulty": "Medio",
        "difficulty_stars": 3,
        "accent_color": (110, 190, 255),
        "path_builder": _path_serpentina,
    },
    "espiral": {
        "name": "Espiral",
        "desc": "Caminho longo em espiral. Poucos slots livres perto do centro.",
        "difficulty": "Dificil",
        "difficulty_stars": 5,
        "accent_color": (230, 90, 90),
        "path_builder": _path_espiral,
        "hp_mult": 1.15,
    },
}

MAP_ORDER = ["planicie", "serpentina", "espiral"]
DEFAULT_MAP_ID = "serpentina"
