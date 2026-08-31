# Tower Defense Infinito com Merge

Jogo de tower defense com fusao (merge) de torres, ondas infinitas e
progressao permanente via loja de gemas.

## Fluxo de telas

1. **Menu principal** - tela de titulo com os botoes **Jogar**, **Como
   Jogar** (abre um resumo das regras e controles) e **Sair**.
2. **Selecao de mapa** - escolha um dos mapas disponiveis para comecar a
   partida. ESC volta ao menu principal.
3. **Partida** - o jogo em si (grade, torres, ondas). Pressione **M** a
   qualquer momento para voltar a selecao de mapa.

## Como jogar

- Clique num slot vazio da grade para abrir o menu e **escolher o tipo**
  de torre a comprar (custa ouro).
- Clique e **arraste** uma torre sobre **outra torre do mesmo tipo** para
  dar **merge**. Se as duas tiverem o mesmo nivel, o resultado sobe um
  nivel. Se os niveis forem diferentes, o nivel mais alto persiste. Nao
  ha nivel maximo.
- Clique **rapido** (sem arrastar) em cima de uma torre para abrir o
  **menu de melhorias**: gaste ouro para melhorar Dano, Alcance ou
  Cadencia daquela torre especificamente.
- Ondas infinitas de inimigos avancam pelo caminho, ficando mais dificeis
  a cada onda. A cada 10 ondas aparece um **boss**, que solta **gemas**
  ao morrer.
- Pressione **G** para abrir a **loja de gemas**: melhorias permanentes
  que afetam o jogo inteiro e persistem entre partidas.
- Perca todas as vidas e o jogo acaba. Sobreviva o maximo de ondas!

## Controles

| Tecla / acao         | Efeito                                                              |
|----------------------|----------------------------------------------------------------------|
| Mouse esquerdo       | Comprar / arrastar / soltar torres / pular onda / abrir loja de gemas |
| ESPACO               | Iniciar a proxima onda manualmente                                   |
| N                    | Pular a onda atual (ganha ouro extra, antecipa a proxima onda)        |
| G                    | Abrir/fechar a loja de gemas                                          |
| P                    | Pausar/despausar                                                     |
| R                    | Reiniciar apos game over (gemas e melhorias permanentes persistem)    |
| ESC                  | Fecha o "Como Jogar" / volta ao menu principal / sai do jogo (conforme a tela) |
| Fechar janela        | Sair                                                                 |

## Tipos de torre

- **Canhao**: equilibrado, dano e alcance medianos.
- **Torre de Flechas**: cadencia muito alta, dano baixo por tiro.
- **Torre de Gelo**: sempre desacelera o alvo atingido.
- **Canhao Pesado**: tiro lento e caro, dano enorme em area.
- **Sniper**: alcance enorme, dano alto, ignora armadura.

## Instalacao e execucao

```bash
pip install -r requirements.txt
python main.py
```

## Estrutura do projeto

```
tower_defense_project/
├── main.py                    # ponto de entrada (python main.py)
├── requirements.txt
├── README.md
└── towerdefense/
    ├── __init__.py             # expoe a classe Game
    ├── config.py                # constantes: janela, cores, tipos de torre/inimigo, upgrades
    ├── fonts.py                  # cache de fontes do pygame
    ├── paths.py                  # geracao do caminho dos inimigos e geometria
    ├── game.py                   # classe Game: estado, input, update, loop principal
    ├── entities/
    │   ├── __init__.py
    │   ├── enemy.py               # classe Enemy + tipos de inimigo
    │   ├── projectile.py          # classe Projectile
    │   └── tower.py               # classe Tower, cores/nomes de nivel
    ├── systems/
    │   ├── __init__.py
    │   ├── waves.py                # WaveManager: geracao e progressao das ondas
    │   └── meta_upgrades.py        # MetaUpgrades: loja de gemas (progressao permanente)
    └── ui/
        ├── __init__.py
        ├── main_menu.py               # tela de titulo (Jogar / Como Jogar / Sair)
        ├── map_menu.py                # tela de selecao de mapa
        ├── board.py                   # desenho do caminho e da grade
        ├── hud.py                     # HUD (ouro/vidas/onda), legenda, tela de game over
        └── menus.py                   # menu de compra, menu de upgrade, loja de gemas, tooltip
```

### Por que essa divisao?

- **config.py** concentra todo numero/tabela "magico" do jogo, para
  balancear sem precisar caçar valores espalhados pelo codigo.
- **entities/** contem so o comportamento de cada "coisa" no jogo
  (inimigo, projetil, torre) - sem saber nada sobre menus ou HUD.
- **systems/** contem regras que orquestram entidades ao longo do tempo
  (progressao de ondas, upgrades permanentes) mas nao desenham nada.
- **ui/** so desenha e calcula geometria de cliques; nao guarda estado
  proprio, sempre le/escreve no objeto `Game` que recebe por parametro.
- **game.py** e o unico lugar que conhece "tudo": e a cola que liga
  entrada do usuario, atualizacao de estado e desenho.
