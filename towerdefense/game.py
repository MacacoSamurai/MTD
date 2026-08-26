"""Classe principal do jogo: estado, loop de eventos, update e desenho.

Esta classe orquestra os outros modulos (entidades, sistemas, paths, ui)
mas tenta nao reimplementar logica que ja vive neles.
"""

import sys
import pygame

from .config import (
    WIDTH, HEIGHT, FPS, COL_BG, COL_MERGE_GLOW,
    STARTING_GOLD, STARTING_LIVES, TOWER_BASE_COST,
    SKIP_WAVE_BASE_BONUS, SKIP_WAVE_BONUS_PER_WAVE,
    GRID_ORIGIN_X, GRID_ORIGIN_Y, GRID_COLS, GRID_ROWS, CELL_SIZE,
    CLICK_DRAG_THRESHOLD, COL_GOLD, COL_GEM, TOP_HUD_HEIGHT,
)
from .paths import MapPath
from .maps import DEFAULT_MAP_ID
from .entities import Tower
from .systems import WaveManager, MetaUpgrades
from .fonts import get_font
from .ui import hud, menus, board, map_menu


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Tower Defense Infinito - Merge das Torres")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        # gemas e melhorias permanentes NAO sao zeradas pelo reset() normal:
        # elas representam progresso de longo prazo entre tentativas,
        # como e comum em jogos com "prestige"/meta-progressao.
        self.gems = 0
        self.meta = MetaUpgrades()
        self.total_bosses_killed = 0
        self.meta_shop_open = False
        self.gem_button_rect = None
        self.mouse_pos = (0, 0)
        # estado geral do jogo: comeca no menu de selecao de mapa.
        # "map_select" -> escolhendo mapa | "playing" -> partida em curso
        self.state = "map_select"
        self.selected_map_id = DEFAULT_MAP_ID
        self.map_path = MapPath(self.selected_map_id)
        self.reset()

    def start_map(self, map_id):
        """Chamado ao clicar num card do menu de mapas: define o mapa
        escolhido, (re)constroi o caminho e comeca a partida."""
        self.selected_map_id = map_id
        self.map_path = MapPath(map_id)
        self.reset()
        self.state = "playing"

    def reset(self):
        self.gold = STARTING_GOLD + self.meta.bonus_starting_gold()
        self.lives = STARTING_LIVES + self.meta.bonus_lives()
        self.enemies = []
        self.projectiles = []
        self.towers = {}  # (col, row) -> Tower
        self.wave_mgr = WaveManager(self.map_path)
        self.paused = False
        self.game_over = False
        self.dragging_tower = None
        self.drag_origin = None
        self.floating_texts = []  # (x, y, text, color, life)
        self.tower_cost = TOWER_BASE_COST  # sera recalculado abaixo
        self.total_kills = 0
        self.hovered_cell = None
        self.shop_open_cell = None  # celula com menu de compra aberto
        self.skip_button_rect = None  # calculado no draw_hud, usado no clique
        self.upgrade_open_cell = None  # celula com menu de melhorias aberto
        self.mouse_down_pos = None  # posicao do ultimo mousedown (p/ distinguir clique de drag)
        self.recalc_tower_cost()

    # ------------------------------------------------------------------
    def add_floating_text(self, x, y, text, color):
        self.floating_texts.append([x, y, text, color, 1.0])

    def update_floating_texts(self, dt):
        for ft in self.floating_texts:
            ft[1] -= 30 * dt
            ft[4] -= dt
        self.floating_texts = [ft for ft in self.floating_texts if ft[4] > 0]

    # ------------------------------------------------------------------
    def cell_from_pixel(self, x, y):
        if x < GRID_ORIGIN_X or y < GRID_ORIGIN_Y:
            return None
        col = (x - GRID_ORIGIN_X) // CELL_SIZE
        row = (y - GRID_ORIGIN_Y) // CELL_SIZE
        if 0 <= col < GRID_COLS and 0 <= row < GRID_ROWS:
            return int(col), int(row)
        return None

    # ------------------------------------------------------------------
    def recalc_tower_cost(self):
        """Recalcula o custo de compra de torre novo, considerando a onda
        atual e os descontos permanentes comprados com gemas."""
        raw = TOWER_BASE_COST + (self.wave_mgr.wave_num - 1) * 4
        self.tower_cost = max(10, int(round(raw * self.meta.tower_cost_mult())))

    # ------------------------------------------------------------------
    def skip_current_wave(self):
        """Pula para a proxima onda antes da hora. Da um bonus de ouro
        mas a proxima onda passa a vir junto com o que restar da atual
        (mais inimigos na tela ao mesmo tempo = mais dificil)."""
        if self.game_over:
            return
        bonus = SKIP_WAVE_BASE_BONUS + self.wave_mgr.wave_num * SKIP_WAVE_BONUS_PER_WAVE
        self.gold += bonus
        self.wave_mgr.skip_wave()
        self.recalc_tower_cost()
        cx = WIDTH // 2
        cy = TOP_HUD_HEIGHT + 40
        self.add_floating_text(cx, cy, f"Onda pulada! +{bonus}g", COL_GOLD)

    # ------------------------------------------------------------------
    # ENTRADA (mouse/teclado)
    # ------------------------------------------------------------------
    def try_click_upgrade_menu(self, pos):
        """Processa um clique quando o menu de upgrade esta aberto.
        Retorna True se o clique foi consumido pelo menu (dentro do
        painel), False se foi fora (o chamador deve fechar o menu)."""
        cell = self.upgrade_open_cell
        if cell not in self.towers:
            return False
        rects, close_rect, panel_rect = menus.upgrade_menu_rects(self.towers, cell)
        if close_rect.collidepoint(pos):
            self.upgrade_open_cell = None
            return True
        tower = self.towers[cell]
        for rect, aspect in rects:
            if rect.collidepoint(pos):
                cost = int(round(tower.upgrade_cost(aspect) * self.meta.upgrade_cost_mult()))
                cost = max(1, cost)
                if self.gold >= cost:
                    self.gold -= cost
                    tower.buy_upgrade(aspect)
                    tx, ty = tower.grid_pos()
                    from .config import UPGRADE_LABELS
                    self.add_floating_text(tx, ty - 24, f"{UPGRADE_LABELS[aspect]} ++", COL_MERGE_GLOW)
                return True
        if panel_rect.collidepoint(pos):
            return True  # clique dentro do painel mas fora de botoes: nao fecha
        return False

    def handle_click_down(self, pos):
        if self.game_over:
            return

        # se o menu de upgrade esta aberto, checa clique nos botoes dele
        if self.upgrade_open_cell is not None:
            handled = self.try_click_upgrade_menu(pos)
            if handled:
                return
            self.upgrade_open_cell = None

        # se o menu de compra esta aberto, primeiro checa clique nos botoes
        if self.shop_open_cell is not None:
            for rect, ttype in menus.shop_slot_rects(self.shop_open_cell):
                if rect.collidepoint(pos):
                    cell = self.shop_open_cell
                    if self.gold >= self.tower_cost and cell not in self.towers:
                        self.gold -= self.tower_cost
                        start_level = 1 + int(self.meta.start_tower_level_bonus())
                        t = Tower(cell[0], cell[1], ttype=ttype, level=start_level)
                        self.towers[cell] = t
                        self.add_floating_text(*t.grid_pos(), f"-{self.tower_cost}g", COL_GOLD)
                    self.shop_open_cell = None
                    return
            # clicou fora dos botoes: fecha o menu (e processa clique normal)
            self.shop_open_cell = None

        cell = self.cell_from_pixel(*pos)
        if cell is None:
            return
        if cell in self.towers:
            # comeca um "drag potencial": so vira arrasto de verdade se o
            # mouse se mover o suficiente antes de soltar (ver handle_click_up)
            self.shop_open_cell = None
            self.dragging_tower = self.towers[cell]
            self.dragging_tower.being_dragged = True
            self.drag_origin = cell
            self.mouse_down_pos = pos
        elif cell not in self.map_path.cell_set:
            # abre menu de escolha de tipo de torre para essa celula
            self.upgrade_open_cell = None
            self.shop_open_cell = cell

    def handle_click_up(self, pos):
        if self.dragging_tower is None:
            return
        cell = self.cell_from_pixel(*pos)
        origin = self.drag_origin
        tower = self.dragging_tower
        tower.being_dragged = False

        # se o mouse mal se moveu desde o clique inicial, trata como um
        # CLIQUE (nao arrasto): abre o menu de melhorias daquela torre
        if self.mouse_down_pos is not None:
            dx = pos[0] - self.mouse_down_pos[0]
            dy = pos[1] - self.mouse_down_pos[1]
            if dx * dx + dy * dy <= CLICK_DRAG_THRESHOLD ** 2:
                self.dragging_tower = None
                self.drag_origin = None
                self.mouse_down_pos = None
                self.upgrade_open_cell = origin
                return
        self.mouse_down_pos = None

        if cell is None or cell == origin or cell in self.map_path.cell_set:
            self.dragging_tower = None
            self.drag_origin = None
            return

        if cell in self.towers:
            target_tower = self.towers[cell]
            if target_tower is tower:
                pass
            elif target_tower.ttype == tower.ttype:
                # MERGE! (mesmo tipo). Se os niveis forem iguais, sobe um
                # nivel (comportamento classico de merge). Se forem
                # diferentes, o nivel da torre MAIS FORTE persiste (nao
                # se perde nivel ao juntar uma fraca com uma forte).
                if target_tower.level == tower.level:
                    new_level = target_tower.level + 1
                else:
                    new_level = max(target_tower.level, tower.level)
                target_tower.level = new_level
                target_tower.recalc_stats()
                del self.towers[origin]
                cx, cy = target_tower.grid_pos()
                self.add_floating_text(cx, cy - 20, f"MERGE! Nv.{new_level}", COL_MERGE_GLOW)
            else:
                # tipos diferentes: nao faz nada, volta pro lugar
                pass
        else:
            # mover para celula vazia
            del self.towers[origin]
            tower.col, tower.row = cell
            self.towers[cell] = tower

        self.dragging_tower = None
        self.drag_origin = None

    # ------------------------------------------------------------------
    def handle_meta_shop_click(self, pos):
        from .config import META_UPGRADE_DEFS
        rects, close_rect, panel_rect = menus.meta_shop_rects()
        if close_rect.collidepoint(pos):
            self.meta_shop_open = False
            return
        for rect, key in rects:
            if rect.collidepoint(pos):
                cost = self.meta.cost_for_next(key)
                if cost is not None and self.gems >= cost:
                    self.gems -= cost
                    self.meta.buy(key)
                    # aplica imediatamente efeitos que afetam o estado atual
                    if key == "extra_lives":
                        self.lives += META_UPGRADE_DEFS["extra_lives"]["effect_per_level"]
                    if key == "tower_cost":
                        self.recalc_tower_cost()
                    label = META_UPGRADE_DEFS[key]["label"]
                    cx = WIDTH // 2
                    self.add_floating_text(cx, TOP_HUD_HEIGHT + 40, f"{label} melhorado!", COL_GEM)
                return
        if not panel_rect.collidepoint(pos):
            self.meta_shop_open = False

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------
    def update(self, dt):
        self.mouse_pos = pygame.mouse.get_pos()
        if self.state == "map_select":
            return
        self.hovered_cell = self.cell_from_pixel(*self.mouse_pos)

        if self.game_over or self.paused:
            self.update_floating_texts(dt)
            return

        # ondas
        self.wave_mgr.update(dt, self.enemies)
        if (not self.wave_mgr.wave_active and not self.enemies and
                self.wave_mgr.time_since_wave_end >= self.wave_mgr.auto_start_delay):
            self.wave_mgr.start_next_wave()
            self.recalc_tower_cost()

        # torres
        for t in self.towers.values():
            t.update(dt, self.enemies, self.projectiles)

        # projeteis
        for p in self.projectiles:
            p.update(dt, self.enemies)
        self.projectiles = [p for p in self.projectiles if p.alive]

        # inimigos: primeiro avanca os que ainda estao vivos (para detectar
        # quem chega ao fim do caminho), depois processa TODOS os que
        # morreram neste frame (seja por dano de projetil ou por chegar
        # ao fim), concedendo ouro/vida perdida uma unica vez cada.
        for e in self.enemies:
            if e.alive:
                e.update(dt)

        for e in self.enemies:
            if e.alive or e._processed_death:
                continue
            e._processed_death = True
            if e.reached_end:
                self.lives -= 1
                if self.lives <= 0:
                    self.lives = 0
                    self.game_over = True
            else:
                # morreu por dano de torre
                gold_gain = int(round(e.gold * self.meta.gold_mult() * self.map_path.gold_mult))
                self.gold += gold_gain
                self.total_kills += 1
                self.add_floating_text(e.x, e.y, f"+{gold_gain}g", COL_GOLD)
                if e.is_boss:
                    self.total_bosses_killed += 1
                    if e.gems > 0:
                        self.gems += e.gems
                        self.add_floating_text(e.x, e.y - 22, f"+{e.gems} gema{'s' if e.gems != 1 else ''}", COL_GEM)

        self.enemies = [e for e in self.enemies if e.alive]

        self.update_floating_texts(dt)

    # ------------------------------------------------------------------
    # DESENHO
    # ------------------------------------------------------------------
    def draw(self):
        if self.state == "map_select":
            map_menu.draw_map_menu(self, self.screen)
            pygame.display.flip()
            return

        self.screen.fill(COL_BG)
        offset = (0, 0)
        board.draw_path(self.screen, offset)
        board.draw_grid(self, self.screen)
        board.draw_path(self.screen, offset, self.map_path)

        for e in self.enemies:
            e.draw(self.screen, offset)

        # torres (nao-arrastadas primeiro)
        for cell, t in self.towers.items():
            if t is not self.dragging_tower:
                t.draw(self.screen, None, False)

        # projeteis: desenhados DEPOIS da grade e das torres para nao
        # passarem "por baixo" delas visualmente (bug MTD-corretiva)
        for p in self.projectiles:
            p.draw(self.screen, offset)

        menus.draw_tower_range_hover(self, self.screen, offset)

        # torre sendo arrastada por cima de tudo
        if self.dragging_tower is not None:
            self.dragging_tower.draw(self.screen, self.mouse_pos, True)
            cell = self.hovered_cell
            if cell is not None:
                x = GRID_ORIGIN_X + cell[0] * CELL_SIZE
                y = GRID_ORIGIN_Y + cell[1] * CELL_SIZE
                rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)
                valid_merge = (cell in self.towers and
                               self.towers[cell].ttype == self.dragging_tower.ttype and
                               self.towers[cell] is not self.dragging_tower)
                col = COL_MERGE_GLOW if valid_merge else (120, 120, 130)
                pygame.draw.rect(self.screen, col, rect.inflate(-4, -4), 3, border_radius=8)

        menus.draw_shop_menu(self, self.screen)
        menus.draw_upgrade_menu(self, self.screen)

        # floating texts
        font_ft = get_font(16, bold=True)
        for x, y, text, color, life in self.floating_texts:
            alpha = max(0, min(255, int(255 * life)))
            surf = font_ft.render(text, True, color)
            surf.set_alpha(alpha)
            self.screen.blit(surf, (x - surf.get_width() / 2, y))

        hud.draw_hud(self, self.screen)
        hud.draw_legend(self.screen)

        # loja de gemas: por cima de absolutamente tudo, inclusive HUD
        menus.draw_meta_shop(self, self.screen)

        if self.game_over:
            hud.draw_game_over(self, self.screen)

        pygame.display.flip()

    # ------------------------------------------------------------------
    # LOOP PRINCIPAL
    # ------------------------------------------------------------------
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)  # evita saltos grandes

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif self.state == "map_select":
                        pass  # nenhum atalho de teclado no menu de mapas
                    elif event.key == pygame.K_p and not self.game_over:
                        self.paused = not self.paused
                    elif event.key == pygame.K_SPACE and not self.game_over:
                        if not self.wave_mgr.wave_active:
                            self.wave_mgr.start_next_wave()
                            self.recalc_tower_cost()
                    elif event.key == pygame.K_n and not self.game_over:
                        self.skip_current_wave()
                    elif event.key == pygame.K_g:
                        self.meta_shop_open = not self.meta_shop_open
                        # fecha outros menus pra nao sobrepor
                        self.shop_open_cell = None
                        self.upgrade_open_cell = None
                    elif event.key == pygame.K_r and self.game_over:
                        self.state = "map_select"
                    elif event.key == pygame.K_m:
                        # volta ao menu de mapas a qualquer momento
                        self.state = "map_select"
                        self.meta_shop_open = False
                        self.shop_open_cell = None
                        self.upgrade_open_cell = None
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        if self.state == "map_select":
                            for rect, map_id in map_menu.map_card_rects():
                                if rect.collidepoint(event.pos):
                                    self.start_map(map_id)
                                    break
                        elif self.meta_shop_open:
                            self.handle_meta_shop_click(event.pos)
                        elif self.gem_button_rect is not None and self.gem_button_rect.collidepoint(event.pos):
                            self.meta_shop_open = True
                            self.shop_open_cell = None
                            self.upgrade_open_cell = None
                        elif self.skip_button_rect is not None and self.skip_button_rect.collidepoint(event.pos):
                            self.skip_current_wave()
                        else:
                            self.handle_click_down(event.pos)
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1 and self.state != "map_select":
                        self.handle_click_up(event.pos)

            self.update(dt)
            self.draw()

        pygame.quit()
        sys.exit()
