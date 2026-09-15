# CLAUDE.md

Guia rapido para uma IA (ou humano) retomar este projeto sem precisar
reler todo o codigo do zero. Para regras de jogo do ponto de vista do
jogador, veja `README.md` — este arquivo foca em arquitetura e decisoes
tecnicas.

## O que e o jogo

Tower Defense infinito com **merge de torres**, em Python + **pygame**.
Sem dependencias externas alem de pygame (ver `requirements.txt`).
Rodar com:

```bash
pip install -r requirements.txt
python main.py
```

Ideia central: o jogador compra torres numa grade, ondas infinitas de
inimigos avancam por um caminho fixo, e torres do mesmo tipo podem ser
arrastadas uma sobre a outra para "merge" (sobem de nivel, sem limite).
A cada 10 ondas aparece um boss que solta gemas, usadas numa loja de
melhorias permanentes (`MetaUpgrades`) que persistem entre partidas
*dentro da mesma execucao do processo* — nao ha save em disco.

## Fluxo de estados (`Game.state`)

```
main_menu  --Jogar-->  map_select  --clique no mapa-->  playing
    ^                       ^                              |
    |ESC (fecha help)       |ESC / tecla M / R apos game over
```

- **`main_menu`**: tela de titulo (`ui/main_menu.py`). Botoes: Jogar,
  Como Jogar (overlay com resumo de regras), Sair.
- **`map_select`**: `ui/map_menu.py`. Um card por mapa, dados vindos de
  `maps.MAP_DEFS`/`MAP_ORDER`. Clicar num card chama `Game.start_map()`.
- **`playing`**: o jogo propriamente dito. `Game.reset()` monta o
  estado de uma partida nova (ouro, vidas, `WaveManager`, etc.).

Cada estado tem seu proprio bloco em `Game.draw()` e em `Game.run()`
(tratamento de eventos). **Se adicionar um estado novo, atualize os
tres lugares**: `draw()`, o `KEYDOWN` e o `MOUSEBUTTONDOWN` dentro de
`run()`, e normalmente tambem o inicio de `update()` (para não rodar
logica de partida fora do estado `"playing"`).

`self.gems`, `self.meta` (MetaUpgrades) e `self.total_bosses_killed`
**nao** sao resetados por `Game.reset()` — representam progresso entre
tentativas e sobrevivem a troca de mapa/partida (mas nao a fechar o
jogo, pois nao ha persistencia em disco).

## Organizacao dos modulos

```
main.py                     # so cria Game() e chama .run()
smoke_test.py               # validacao headless (ver secao "Teste" abaixo)
towerdefense/
├── config.py                # TODAS as constantes/tabelas de balanceamento
├── upgrades.py               # ARVORE de evolucao: 5 torres x 3 caminhos x 6 tiers
│                              # (dados + regras puras de crosspath, sem pygame)
├── fonts.py                  # cache de pygame.font.SysFont por (tamanho, bold)
├── paths.py                  # MapPath: converte celulas (col,row) do mapa em
│                              # posicoes de pixel + comprimento do percurso
├── maps.py                   # MAP_DEFS / MAP_ORDER / geradores de caminho
├── game.py                   # Game: estado, input, update, draw, loop principal
├── entities/
│   ├── enemy.py               # Enemy: anda pelo MapPath, tem HP/armadura/velocidade
│   ├── projectile.py          # Projectile: viaja ate o alvo, aplica dano/splash/slow
│   └── tower.py               # Tower: stats por nivel, merge, upgrades, desenho
├── systems/
│   ├── combat.py               # resolucao CENTRAL de dano/efeitos (todo dano do
│   │                            # jogo passa por aqui: tiro, explosao, habilidade)
│   ├── abilities.py            # habilidades tier 6 + IA que decide quando ativar
│   ├── vfx.py                  # explosoes/campos/feixes descartaveis (so desenho)
│   ├── waves.py                # WaveManager: fila de spawn, dificuldade crescente,
│   │                            # bosses periodicos, skip_wave() (empilha ondas)
│   └── meta_upgrades.py        # MetaUpgrades: niveis/custo/efeito da loja de gemas
└── ui/                         # SO desenho + geometria de clique; nao guarda estado
    ├── theme.py                 # helpers visuais reaproveitados (sombra suave,
    │                              # paineis com degrade/"elevacao", icones de
    │                              # moeda/coracao/gema, gradiente vertical, botao
    │                              # generico com hover) -- usado por quase todo
    │                              # o resto de ui/ pra manter o visual consistente
    ├── main_menu.py             # tela de titulo (ver secao de estados acima)
    ├── map_menu.py              # tela de selecao de mapa
    ├── board.py                 # grade + caminho
    ├── hud.py                   # HUD do topo, tela de game over
    ├── tower_panel.py           # painel lateral fixo (compra + upgrade de torre)
    └── menus.py                 # loja de gemas (meta_shop), tooltip de alcance
```

### Convencao importante: `ui/` e "burro" de proposito

Nenhum arquivo em `ui/` guarda estado proprio. Toda funcao recebe a
instancia de `Game` (ou os dados especificos que precisa) e le/escreve
diretamente nos atributos do `Game` (ex.: `game.gem_button_rect`,
`game.skip_button_rect`). Os modulos de UI expoem em geral dois tipos
de funcao:

- `*_rects()` — so calculam geometria (`pygame.Rect`). Sao chamadas
  tanto para desenhar quanto para testar colisao com o clique do mouse
  em `game.py`. **Nunca recalcule geometria de clique "no olho" dentro
  de `game.py`** — sempre reaproveite a funcao `*_rects()` correspondente,
  para desenho e clique nunca ficarem dessincronizados.
- `draw_*()` — desenham na `Surface` recebida.

Se for adicionar um menu/tela nova, siga esse padrao (veja
`ui/main_menu.py` como exemplo mais simples e `ui/map_menu.py` /
`ui/menus.py` para casos com mais estado).

## Pontos de atencao / pegadinhas conhecidas

- **Distinguir clique de arrasto em torres**: `handle_click_down` marca
  `mouse_down_pos`; `handle_click_up` compara a distancia percorrida
  com `CLICK_DRAG_THRESHOLD` (config.py). Abaixo do limiar conta como
  clique (abre menu de upgrade), acima conta como arrasto (merge/mover).
- **Ordem de desenho em `Game.draw()` importa**: projeteis sao
  desenhados depois da grade/torres (senão passam "por baixo" delas
  visualmente); a loja de gemas (`draw_meta_shop`) e desenhada por
  cima de tudo, inclusive do HUD.
- **`skip_wave()` empilha, nao substitui**: pular a onda atual nao
  descarta os inimigos restantes; a fila da proxima onda e intercalada
  com o que sobrou, entao mais inimigos aparecem juntos (ver comentario
  longo em `systems/waves.py`).
- **Arvore de upgrades (`upgrades.py`) x merge sao progressoes
  SEPARADAS**: `Tower.level` vem do merge e escala as stats de forma
  generica; `Tower.tiers` (3 inteiros 0..6) vem da arvore e e o que da
  identidade a torre (efeitos, padrao de tiro, aura, habilidade). Uma
  torre 5-2-0 nivel 4 e "nivel 4 com os mods dos 7 upgrades comprados".
  Os mods sao combinados por `upgrades.combine_mods` (o SUFIXO da chave
  define como: `_mult` multiplica, `_add` soma, `_time`/`_amp` pegam o
  maior, `slow_factor` pega o menor) e viram valores absolutos em
  `Tower.build_effects()`.
- **Adicionar um efeito novo na arvore**: escolha um nome de chave com
  um desses sufixos, use no `mods` de algum tier em `upgrades.py`, e leia
  `tower.mods[...]`/`tower.effects[...]` em `entities/tower.py`. Nao
  espalhe `if` por upgrade especifico -- a combinacao e mecanica.
- **`Game` e o "world"**: entities/ e systems/ NUNCA importam `Game`;
  recebem um objeto com `.enemies`, `.projectiles`, `.vfx`,
  `.pending_blasts`, `.towers` e `.map_path` (na pratica, o `Game`).
  Se adicionar uma lista nova que projeteis/habilidades escrevem, ela
  precisa nascer em `Game.reset()`.
- **Todo dano passa por `systems/combat.py`**: `resolve_hit`,
  `area_damage` e `explode`. Sem isso, projetil, explosao secundaria e
  habilidade divergiriam na primeira mudanca de balanceamento. A ordem
  das contas (esquiva -> critico -> bonus situacionais -> quebra de
  armadura -> dano -> status) e parte do balanceamento.
- **Regras de tier 6 moram em dois lugares, de proposito**: o crosspath
  (regra local da torre) em `upgrades.can_upgrade`; o limite de UM tier 6
  por TIPO de torre (regra da partida inteira) em `Game.tier6_owner` /
  `Game.path_purchase_state`. Desenho do painel e tratamento de clique
  chamam o MESMO `path_purchase_state`, entao nunca aparece um botao
  habilitado que recusa a compra.
- **Habilidades tier 6 sao automaticas**: `AbilityController` varre
  `world.towers` todo frame; quando o cooldown zera, a `evaluate` da
  habilidade decide se a situacao vale (concentracao de inimigos, chefe
  presente, vazamento iminente). Existe um mecanismo de PACIENCIA
  (`_impatient`): se a habilidade esta pronta ha tempo demais, ela
  dispara mesmo fora do cenario ideal -- sem ele, uma habilidade
  anti-chefe podia ficar calada por ondas inteiras. A avaliacao e
  throttled (`ABILITY_EVAL_INTERVAL`) porque `best_cluster` e O(n^2).
- **Efeitos globais de habilidade** (DOMINIO ETERNO, VISAO ABSOLUTA)
  ficam em `Enemy.global_amp`/`Enemy.global_slow`, atributos de CLASSE,
  recalculados do zero a cada frame pelo controller (assim nunca sobra
  efeito ligado) e zerados em `Game.reset()`.
- **Merge so ocorre com mesmo nivel**: arrastar uma torre sobre outra do
  mesmo tipo so funde (`level += 1`) quando as duas tem exatamente o
  mesmo `level`. Nesse caso, cada aspecto de melhoria comprado no menu
  CAMINHO da arvore (`tiers`) fica com o MAIOR tier entre as duas torres
  — nunca ha perda de investimento ao fundir. O merge tambem e proibido
  se o resultado violar o crosspath (ex.: 5-0-0 + 0-5-0 daria 5-5-0);
  nesse caso, como quando os niveis sao diferentes, as torres apenas
  trocam de lugar na grade. Ver `Game.handle_click_up` em `game.py`. O indicador visual de arrasto
  usa `COL_MERGE_GLOW` (fusao valida) vs `COL_SWAP_GLOW` (mesmo tipo,
  nivel diferente -> so troca) vs cinza (tipos incompativeis).
- **Cores/nomes de nivel de torre nao tem teto**: `tower_color()` e
  `tower_name()` em `entities/tower.py` usam tabelas fixas para os
  primeiros niveis e depois geram cor (rotacao de matiz) e nome
  ("Ascendido +N") proceduralmente, porque nao ha nivel maximo de merge.
- **Adicionar um mapa novo**: só mexer em `maps.py` (um `path_builder`
  + uma entrada em `MAP_DEFS` + o id em `MAP_ORDER`). Nenhum outro
  arquivo precisa saber quantos mapas existem.
- **Adicionar um tipo de torre/inimigo/melhoria de gemas novo**: tudo
  fica centralizado em `config.py` (`TOWER_TYPES`, `ENEMY_TYPES`,
  `META_UPGRADE_DEFS`) — o resto do codigo itera sobre essas tabelas,
  entao normalmente não é preciso tocar em `game.py` ou `ui/`.
- **Sem pytest e sem persistencia em disco**, mas existe
  `smoke_test.py` na raiz: script headless que valida crosspath,
  integridade das 90 evolucoes, limite de tier 6 por tipo, merge ilegal
  e roda 90 segundos de partida real (update + draw). Rodar
  `python smoke_test.py` depois de mexer em torres/upgrades/combate. Pro
  resto, validar na mao rodando o jogo (ou `SDL_VIDEODRIVER=dummy` +
  `pygame.image.save(g.screen, ...)` pra inspecionar telas sem display,
  como foi feito pra conferir o painel da arvore).
- **`HEIGHT` e derivado da grade, nao um numero solto**: `HEIGHT =
  TOP_HUD_HEIGHT + GRID_ROWS * CELL_SIZE + BOTTOM_HUD_HEIGHT` em
  `config.py`. Ja existiu um bug em que `HEIGHT` fixo (800) era 8px
  menor que essa soma, e a ultima fileira de slots ficava escondida
  atras da barra inferior. Se mexer em `GRID_ROWS`/`CELL_SIZE`/altura
  das barras, `HEIGHT` se ajusta sozinho -- nao hardcode de volta.
  `BOTTOM_HUD_HEIGHT` hoje vale 0 (nao ha mais barra/legenda no
  rodape do mapa, removida a pedido) - a constante ficou so pra quem
  precisar reativar uma faixa inferior no futuro.
- **Cada tipo de torre tem uma silhueta propria** (`tower_shape` em
  `TOWER_TYPES`, config.py: "circle", "triangle", "hexagon", "square"
  ou "diamond"), desenhada em `Tower.draw` (entities/tower.py) e
  espelhada nos icones de `ui/theme.draw_shape_icon` (cards do painel,
  tooltip). E um campo SEPARADO de `proj_shape` (formato do projetil,
  usado em entities/projectile.py) -- nao reusar um pelo outro. Ao
  criar um tipo de torre novo, defina os dois.
- **`towerdefense/ui/__init__.py` precisa importar TODO modulo novo de
  ui/**: ja aconteceu de `main_menu.py` existir e ser usado em
  `game.py` sem estar nesse `__init__.py` nem no import de `game.py`,
  o que quebrava o jogo assim que abria (estado inicial e
  `"main_menu"`). Ao criar um modulo de ui/ novo, adicione-o em ambos
  os lugares.
- **O painel "Como Jogar" tem altura DERIVADA do texto**
  (`main_menu.HELP_SECTIONS` + `_help_content_height`): com altura fixa,
  o conteudo vazava por baixo da borda assim que o texto crescia. Ao
  adicionar uma secao la, nada mais precisa ser ajustado.
- **Paineis/HUD usam `ui/theme.py` para consistencia visual**: sombra
  suave (`draw_shadow`), painel arredondado com leve degrade
  (`draw_panel`), gradiente vertical (`vertical_gradient`) e um botao
  generico com hover (`button`). Ao criar um popup/card novo, prefira
  reaproveitar esses helpers em vez de desenhar retangulos chapados na
  mao, para manter o mesmo acabamento em todo o jogo.

## Idioma e estilo

Comentarios, nomes de variaveis de dominio (ex.: `onda`, `gemas`) e
strings visiveis ao jogador estao em **portugues**. Manter esse padrao
em qualquer codigo novo para consistencia.
