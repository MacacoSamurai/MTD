"""Gerador de ondas: dificuldade infinita e crescente, com bosses
periodicos e a logica de "pular onda"."""

import random

from ..config import ENEMY_TYPES, BOSS_WAVE_INTERVAL
from ..entities.enemy import Enemy


class WaveManager:
    def __init__(self, map_path):
        self.map_path = map_path
        self.wave_num = 0
        self.spawn_queue = []  # lista de kinds a spawnar
        self.spawn_timer = 0.0
        self.spawn_interval = 0.5
        self.wave_active = False
        self.time_since_wave_end = 0.0
        self.auto_start_delay = 6.0

    def hp_mult(self):
        base = 1.0 + (self.wave_num - 1) * 0.18
        return base * self.map_path.hp_mult

    def speed_mult(self):
        return min(2.2, 1.0 + (self.wave_num - 1) * 0.015)

    def build_wave_queue(self, n):
        """Gera a lista de inimigos (kinds) para a onda n, sem mexer em
        estado nenhum. Usado tanto para a onda normal quanto para gerar
        uma onda extra empilhada ao pular."""
        # o boss nunca entra no sorteio normal: ele so aparece garantido
        # nas ondas multiplas de BOSS_WAVE_INTERVAL (ver abaixo)
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
        if n % BOSS_WAVE_INTERVAL == 0 and n >= ENEMY_TYPES["boss"]["min_wave"]:
            queue.append("boss")
        return queue

    def start_next_wave(self):
        self.wave_num += 1
        n = self.wave_num
        self.spawn_queue = self.build_wave_queue(n)
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
        return n

    def update(self, dt, enemies_list):
        if self.wave_active:
            if self.spawn_queue:
                self.spawn_timer -= dt
                if self.spawn_timer <= 0:
                    kind = self.spawn_queue.pop(0)
                    e = Enemy(kind, self.wave_num, self.hp_mult(), self.speed_mult(), self.map_path)
                    enemies_list.append(e)
                    self.spawn_timer = self.spawn_interval
            else:
                if not enemies_list:
                    self.wave_active = False
                    self.time_since_wave_end = 0.0
        else:
            self.time_since_wave_end += dt
