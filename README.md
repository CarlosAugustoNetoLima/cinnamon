# Cinnamon Studio — site

Site institucional imersivo do condotel Cinnamon Studio (Orla de Palmas – TO).

## Como construir

Abra o Claude Code nesta pasta e rode:

```
/build-site
```

O comando executa as 5 fases em ordem, cada uma no modelo e no esforco certos. Para rodar uma fase isolada: `/build-site 3`.

## Estrutura

```
CLAUDE.md                        regras inegociaveis (marca, stack, o que nao inventar)
PROMPT-CINNAMON-STUDIO-SITE.md   especificacao completa do site
.claude/settings.json            modelo fable + esforco high por padrao
.claude/agents/                  um agente por fase, com modelo e esforco proprios
.claude/skills/build-site/       o comando /build-site
scripts/prepare-assets.sh        converte Assets/ -> img/ (WebP, 2 larguras)
scripts/prepare-tour.py          panoramas do tour 360 -> img/pano-* (AVIF + JPEG original + thumb)
js/tour360.js                    viewer 360 em WebGL, sem biblioteca (secao #tour)
img/                             assets prontos + manifest.json
Assets/                          originais — somente leitura, nunca abrir como imagem
_to_delete/                      arquivos obsoletos, pode apagar pelo Finder
```

## Rodar localmente

```
python3 -m http.server 8000
```

## Reprocessar imagens

```
./scripts/prepare-assets.sh all      # ou: torre | studio | planta
```

## Tour 360

Os panoramas da secao `#tour` sao equirretangulares 2:1. Para regerar a partir do HTML do fornecedor, ou de uma pasta com `<slug>.jpg` soltos (ate 4096 px de largura; acima disso o script reduz):

```
python3 scripts/prepare-tour.py caminho/para/ABREU3DFX_CINNAMON_STUDIO_360.html
python3 scripts/prepare-tour.py caminho/para/pasta-de-panoramas/
```

Cada ambiente e um `<button class="tour__room">` em `index.html` — incluir ou tirar um ambiente e incluir ou tirar o botao. Se a largura dos arquivos mudar, o sufixo (`-2048`) muda junto nos atributos `data-pano`, `data-pano-fallback` e no `<picture>` do palco.

## A torre em 3D (#fachada)

O site usa `img/fachada-real.glb` (atributo `data-glb` do palco em `index.html`): o modelo 3D do arquiteto (FBX do 3ds Max, 09/2026) convertido so com as faces vistas de fora. Os materiais vem da cena do Twinmotion do arquiteto (`CINNAMON-certo-10_000.tm`, um SQLite com objetos em protobuf — `scripts/fachada/modelo-real/gen_fachada_real.py` tem a tabela peca -> material) e as cores dos renders de referencia; o terreo e em vidro com interior simplificado (caixas no lugar dos moveis dos FBX de interior), e piscina, mobiliario e palmeiras ficam nas posicoes da cena. 17 pavimentos-tipo identicos (pe-direito 3,06 m), 30 studios por andar. A numeracao comercial das unidades ainda nao foi confirmada (marcador AJUSTAR no index.html).

```
# FBX.rar do arquiteto extraido em <pasta FBX> (CASCA-NOVA, TERREO, REVIT); Blender 4.5
blender -b --factory-startup --python scripts/fachada/modelo-real/visivel.py -- <pasta FBX> visivel.json 0.3
blender -b --factory-startup --python scripts/fachada/modelo-real/extrai.py  -- <pasta FBX> visivel.json <pasta partes>
python3 scripts/fachada/modelo-real/gen_fachada_real.py <pasta partes> img/fachada-real.glb
```

A maquete anterior, feita a partir dos renders de referencia, continua em `img/fachada.glb` como reserva (voltar = trocar o `data-glb`):

```
python3 scripts/fachada/gen_fachada.py      # regera img/fachada.glb (numpy + Pillow)
```

Os parametros da maquete (pavimentos, pe-direito, alturas, escala) ficam no topo de `scripts/fachada/gen_fachada.py`; os materiais das duas versoes estao la (`MATERIAIS`); as texturas sao procedurais (`scripts/fachada/texturas.py`), so o letreiro vem de `scripts/fachada/logo.png` (o SVG oficial rasterizado). O visualizador (`js/fachada3d.js`) usa Three.js r160 via CDN, carregado por `import()` so quando a secao se aproxima — e a unica excecao a stack travada no CLAUDE.md. O painel do studio mostra apenas dados oficiais (metragens, planta); nada de preco ou situacao de venda. Os posteres `img/fachada-poster-*.webp` sao capturas do proprio visualizador.

## Leads (Junix)

O CTA do site leva ao formulário externo (respondi.app). Em `/api/junix`, um webhook do respondi entrega cada cadastro concluído para a API de Leads da Junix. Variáveis de ambiente exigidas na Vercel (nunca no código):

```
RESPONDI_WEBHOOK_TOKEN   segredo exigido em ?token= no webhook
JUNIX_USERNAME           usuário da API Junix
JUNIX_PASSWORD           senha da API Junix
JUNIX_ID_PRODUTO         id do produto Cinnamon Studio na Junix
```

Opcionais: `JUNIX_BASE_URL` (padrão `https://junixapi.imobflow.com.br`), `RESPONDI_FORM_ID` (ignora webhooks de outro formulário) e `JUNIX_DRY_RUN=1` (loga o lead sem enviar). Testar a lógica offline, sem credenciais reais:

```
python3 scripts/test_junix.py
```
