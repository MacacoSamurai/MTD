#!/usr/bin/env python3
"""
Ponto de entrada do jogo.

Basta rodar `python main.py` (com pygame instalado) para jogar.
Toda a logica do jogo esta organizada dentro do pacote `towerdefense/`.
"""
from towerdefense import Game


if __name__ == "__main__":
    game = Game()
    game.run()
