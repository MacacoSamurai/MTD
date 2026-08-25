"""Cache simples de fontes do pygame, para nao recriar a mesma fonte
(tamanho + negrito) toda vez que algo e desenhado."""

import pygame

_font_cache = {}


def get_font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont("arial", size, bold=bold)
    return _font_cache[key]
