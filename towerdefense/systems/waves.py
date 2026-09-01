"""Gerador de ondas: dificuldade infinita e crescente, com bosses
periodicos e a logica de "pular onda"."""

import random

from ..config import ENEMY_TYPES, BOSS_WAVE_INTERVAL
from ..entities.enemy import Enemy


class WaveManager:
    def __init__(self, map_path):
        self.map_path = map_path
        self.wave_num = 0
        self.spawn_queue = []  # fila de inimigos NORMAIS a spawnar (nunca contem boss)
        self.spawn_timer = 0.0
        self.spawn_interval = 0.5
        self.wave_active = False
        self.time_since_wave_end = 0.0
        self.auto_start_delay = 6.0
        # Bosses NAO ficam dentro de spawn_queue: cada boss pendente e
        # guardado aqui como [quantos inimigos normais ainda faltam
        # spawnar antes dele liberar, onda a que ele pertence]. Isso e
        # fixado no momento em que a onda-marco (multiplo de
        # BOSS_WAVE_INTERVAL) e construida e so decrementa conforme
        # inimigos normais realmente spawnam — pulos de onda FUTUROS
        # apenas adicionam mais inimigos normais DEPOIS do boss na fila,
        # nunca empurram o contador do boss pra mais longe. Sem isso, ao
        # pular varias ondas em sequencia o boss ficava "enterrado":
        # cada novo pulo intercalava (round-robin) a fila inteira de
        # novo, e a posicao relativa do boss dentro da fila ia dobrando
        # a cada pulo, ate ele so aparecer la no fim de uma fila gigante
        # empilhada — bem depois da SUA propria onda.
        self.pending_bosses = []

    def hp_mult(self):
        base = 1.0 + (self.wave_num - 1) * 0.18
        return base * self.map_path.hp_mult

    def speed_mult(self):
        return min(2.2, 1.0 + (self.wave_num - 1) * 0.015)

    def wave_has_boss(self, n):
        return n % BOSS_WAVE_INTERVAL == 0 and n >= ENEMY_TYPES["boss"]["min_wave"]

    def build_wave_queue(self, n):
        """Gera a lista de inimigos NORMAIS (kinds) para a onda n, sem
        mexer em estado nenhum. Usado tanto para a onda normal quanto
        para gerar uma onda extra empilhada ao pular. Nunca inclui boss
        (ver `pending_bosses`/`wave_has_boss`)."""
        available = [k for k, v in ENEMY_TYPES.items()
                     if v["min_wave"] <= n and not v.get("is_boss")]
        count = 6 + n * 2
        count = min(count, 60)
        queue = []
        for _ in range(count):
            weights = []
            for k in available:
                mw = ENEMY_TYPES[k]["min_wave"]
                w = 3.0 if n - mw > 5 else 1.2
                weights.append(w)
            kind = random.choices(available, weights=weights, k=1)[0]
            queue.append(kind)
        return queue

    def _schedule_boss_if_due(self, n, after_count):
        """Se a onda `n` e uma onda-marco de boss, agenda o boss pra
        liberar depois de `after_count` inimigos normais spawnarem (o
        total ja enfileirado ate agora, incluindo o restante de ondas
        anteriores + a propria onda nova) — ou seja, no final DELA, nao
        no final de quantas ondas mais o jogador vier a empilhar depois."""
        if self.wave_has_boss(n):
            self.pending_bosses.append([after_count, n])

    def start_next_wave(self):
        self.wave_num += 1
        n = self.wave_num
        self.spawn_queue = self.build_wave_queue(n)
        self._schedule_boss_if_due(n, len(self.spawn_queue))
        self.spawn_timer = 0.0
        self.spawn_interval = max(0.18, 0.55 - n * 0.01)
        self.wave_active = True
        self.time_since_wave_end = 0.0

    def skip_wave(self):
        """Pula direto para a proxima onda. Se uma onda ja estiver em
        andamento (ainda tem inimigos vivos/na fila), a nova onda e
        EMPILHADA por cima da atual: os inimigos que faltam da onda
        atual e os da proxima onda vem TODOS JUNTOS, mas espalhados
        apenas dentro do tempo normal de UMA onda (o dobro de inimigos
        no mesmo intervalo de tempo, entao o spawn fica mais apertado
        mas nao instantaneo). Retorna o numero da nova onda iniciada."""
        n = self.wave_num + 1
        self.wave_num = n
        extra_queue = self.build_wave_queue(n)
        # intercala a fila nova com o que restava da onda anterior, para
        # os inimigos nao chegarem todos "colados" em um so bloco
        merged = []
        old_queue = self.spawn_queue
        i = j = 0
        while i < len(old_queue) or j < len(extra_queue):
            if i < len(old_queue):
                merged.append(old_queue[i]); i += 1
            if j < len(extra_queue):
                merged.append(extra_queue[j]); j += 1

        # duracao normal de UMA onda (a onda nova, isolada): quantidade
        # de inimigos dela vezes o intervalo normal de spawn dela.
        normal_interval = max(0.18, 0.55 - n * 0.01)
        target_duration = len(extra_queue) * normal_interval if extra_queue else normal_interval

        self.spawn_queue = merged
        # reparte esse mesmo tempo entre TODOS os inimigos (antigos + novos),
        # entao os dois "lotes" chegam juntos, mas dentro do tempo de uma onda so
        self.spawn_interval = max(0.05, target_duration / len(merged)) if merged else normal_interval
        self.wave_active = True
        self.time_since_wave_end = 0.0
        # se essa onda-marco tem boss, ele libera assim que os inimigos
        # normais agendados ATE AGORA (leftover + a propria onda nova)
        # acabarem de spawnar — fixo, independente de quantas ondas
        # ainda venham a ser empilhadas por cima depois.
        self._schedule_boss_if_due(n, len(merged))
        return n

    def _release_due_bosses(self, enemies_list):
        still_pending = []
        for entry in self.pending_bosses:
            countdown, boss_wave = entry
            if countdown <= 0:
                e = Enemy("boss", boss_wave, self.hp_mult(), self.speed_mult(), self.map_path)
                enemies_list.append(e)
            else:
                still_pending.append(entry)
        self.pending_bosses = still_pending

    def update(self, dt, enemies_list):
        if self.wave_active:
            if self.spawn_queue:
                self.spawn_timer -= dt
                if self.spawn_timer <= 0:
                    kind = self.spawn_queue.pop(0)
                    e = Enemy(kind, self.wave_num, self.hp_mult(), self.speed_mult(), self.map_path)
                    enemies_list.append(e)
                    self.spawn_timer = self.spawn_interval
                    # cada inimigo normal que sai da fila aproxima os
                    # bosses pendentes de liberarem
                    for entry in self.pending_bosses:
                        entry[0] -= 1
                    self._release_due_bosses(enemies_list)
            else:
                self._release_due_bosses(enemies_list)
                if not self.pending_bosses and not enemies_list:
                    self.wave_active = False
                    self.time_since_wave_end = 0.0
        else:
            self.time_since_wave_end += dt
