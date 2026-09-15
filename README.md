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

- Um **painel lateral fixo** (estilo Bloons TD) mostra todos os tipos de
  torre disponiveis para compra. **Arraste** uma torre do painel ate um
  slot vazio da grade para compra-la (custa ouro). Dois **cliques
  rapidos** no mesmo card tambem compram, colocando a torre automaticamente
  no primeiro slot vazio disponivel. O painel pode ser aberto/fechado pela
  abinha na borda dele ou pela tecla **T**; ele fica sobreposto na frente
  da grade e nunca muda o tamanho dela.
- Clique e **arraste** uma torre ja colocada sobre **outra torre do mesmo
  tipo** para dar **merge**. Se as duas tiverem o mesmo nivel, o resultado
  sobe um nivel. Se os niveis forem diferentes, o nivel mais alto persiste.
  Nao ha nivel maximo.
- Clique **rapido** (sem arrastar) em cima de uma torre ja colocada para
  selecionar ela: o painel lateral passa a mostrar a **arvore de
  evolucao** daquela torre (ver a secao abaixo). Use o botao "Voltar" no
  painel para sair desse modo.
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
| T                    | Abrir/fechar o painel lateral de torres                              |
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

## Caminhos de evolucao (estilo Bloons TD 6)

Cada um dos 5 tipos de torre tem **3 caminhos** de **6 tiers** cada --
90 evolucoes no total. A configuracao de uma torre e escrita como no
BTD6: `5-2-0` = tier 5 no primeiro caminho, tier 2 no segundo, nada no
terceiro.

### Regras de crosspath

- Uma torre pode abrir no maximo **dois** caminhos.
- Apenas **um** deles pode passar do tier 2; o outro trava ali.
- Configuracoes validas: `5-2-0`, `2-5-0`, `0-2-5`, `6-0-2`...
  Invalidas: `5-5-0`, `1-1-1`.
- No **merge**, cada caminho fica com o maior tier entre as duas torres.
  Se o resultado violar o crosspath (ex.: `5-0-0` + `0-5-0`), o merge e
  recusado e as torres apenas trocam de lugar.

### Identidade de cada caminho

| Torre | Caminho 1 | Caminho 2 | Caminho 3 |
|-------|-----------|-----------|-----------|
| Canhao | Demolidor (explosao) | Artilheiro (cadencia) | Engenheiro de Cerco (alcance/suporte) |
| Torre de Flechas | Atirador (volume de dano) | Cacador (alvos prioritarios) | Arqueiro Tatico (elementos) |
| Torre de Gelo | Congelador (controle) | Criomante (dano) | Permafrost (debuff/suporte) |
| Canhao Pesado | Megaexplosao (area) | Artilharia (cadencia) | Especialista em Colossos (anti-chefe) |
| Sniper | Atirador de Elite (alvo unico) | Sniper Automatico (cadencia) | Observador (alcance/marcacao) |

### Tier 6: as super torres

O tier 6 leva a identidade do caminho ao extremo e ganha uma
**habilidade com cooldown**. Voce **nao** clica para ativar: a IA
observa a pista (quantidade e concentracao de inimigos, presenca de
chefes, quem esta perto do fim do caminho) e escolhe a melhor hora. Um
aviso aparece no topo da tela quando uma habilidade dispara, e a torre
mostra um anel de recarga.

**Regra fundamental:** so pode existir **uma torre tier 6 de cada TIPO**
na partida. Escolhido o Canhao Apocaliptico, aquele tipo esta gasto --
nada de Deus da Artilharia ou Sentinela do Fim depois. Como sao 5 tipos,
o limite e de 5 super torres, uma de cada. O HUD mostra os 5 slots.

## Teste

Nao ha pytest no projeto, mas ha um script de validacao headless:

```bash
python smoke_test.py
```

Ele confere as regras de crosspath, a integridade das 90 evolucoes, o
limite de tier 6 por tipo e roda 90 segundos de partida simulada.

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
    ├── upgrades.py               # arvore de evolucao: 5 torres x 3 caminhos x 6 tiers
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
    │   ├── combat.py               # resolucao central de dano, explosoes e efeitos
    │   ├── abilities.py            # habilidades tier 6 + IA que decide quando usa-las
    │   ├── vfx.py                  # explosoes/campos/feixes (feedback visual)
    │   ├── waves.py                # WaveManager: geracao e progressao das ondas
    │   └── meta_upgrades.py        # MetaUpgrades: loja de gemas (progressao permanente)
    └── ui/
        ├── __init__.py
        ├── board.py                 # desenho do caminho e da grade
        ├── hud.py                    # HUD (ouro/vidas/onda), legenda, tela de game over
        ├── map_menu.py                # menu de selecao de mapa
        ├── tower_panel.py             # painel lateral fixo: compra de torres + arvore da torre selecionada
        └── menus.py                  # loja de gemas, tooltip de alcance
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
