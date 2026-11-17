# Painel de Volumetria — Origem PR (DTOP / GMP)

Dashboard HTML autocontido para acompanhamento da volumetria expedida da origem PR
(empresas **DTOP** e **GMP**), no período de **01/07/2026 a 16/11/2026**.

> **Acesso online:** https://guimepa.github.io/volumetria-dtop-gmp/
> Publicado via GitHub Pages; o `index.html` redireciona para o relatório. O site está
> marcado como `noindex` (não aparece em buscadores), mas o link é acessível a quem o tiver.


## Arquivos

| Arquivo | Descrição |
|---|---|
| `relatorio_volumetria_guimepa.html` | Painel interativo (autocontido, ~390 KB — abre direto no navegador) |
| `volumetria_guimepa_consolidado.xlsx` | Base consolidada: Resumo por UF, Resumo Mensal e Pedidos Enviados |
| `volumetria_html_guimepa.py` | Gerador do painel e da planilha a partir dos CSVs de origem |

## Conteúdo do painel

- **KPIs** de envios, volumes, peso, valor, ticket médio e peso/volume, com destaque verde
  para a melhor região em cada indicador.
- **Filtro global de transportadora**: Todas · Rodonaves · Outra Transportadora (aplica-se a todos os quadros).
- **Resumo Mensal** (do mês mais recente para o mais antigo).
- **Consolidado por UF / Região / Top 10 Cidades**, com ordenação por coluna, Top 5 e
  alternância entre tabela e gráfico.
- **Pedidos Enviados**: 2.439 pedidos com data de coleta, valor, CEP, UF, cidade, peso líquido,
  **peso cubado** (correlacionado pela base auxiliar, chave = nº do Pedido), volumes,
  transportadora, **SLA de entrega** e empresa — com busca por campo, ordenação, paginação
  (20/50/100) e **exportação CSV** exatamente como exibido.
- **Progressão de Volumes por Mês**: comparativo Rodonaves × demais transportadoras, com
  filtro próprio (transportadora e faixa de peso), independente do filtro global.
- **Evolução Mensal por Região**: métrica selecionável (envios, volumes, peso, valor) e
  visão tabela/gráfico.

## Como regenerar

1. Coloque na mesma pasta os dois CSVs de origem (não versionados por conterem dados de clientes):
   - `Volumetria DTOP GMP GERAL 01072026 17112026.csv`
   - `PESO CUBADO Volumetria DTOP GMP GERAL 01072026 17112026.csv`
2. Execute:

```bash
python volumetria_html_guimepa.py
```

O script regrava o HTML e o XLSX na mesma pasta.

### Regras de negócio aplicadas

- **Peso cubado**: coluna `AG — Peso Cubado Produto` da base auxiliar, correlacionada por
  `Pedido` (a coluna `NF` não correlaciona entre as bases).
- **SLA**: coluna `H — Performance entrega Transportadora`; valores com "ATRASO" → `Atrasado`,
  com "PRAZO" → `No prazo`.
- **Transportadoras**: apenas Rodonaves é identificada; as demais são agrupadas como
  "Outra transportadora".
- Registros sem UF válida são descartados.

## Observação

Os CSVs de origem **não** fazem parte do repositório (ver `.gitignore`), pois contêm dados
pessoais e comerciais de clientes (nomes, CPF/CNPJ, valores).
