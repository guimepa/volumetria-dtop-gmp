# -*- coding: utf-8 -*-
"""
VOLUMETRIA GERAL ORIGEM PR GUIMEPA
Gera relatório HTML interativo a partir da base DTOP/GMP (CSV).
"""
import pandas as pd
import numpy as np
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

caminho_base = r"G:\Drives compartilhados\LojaVirtual\TRANSPORTADORAS SITE\13. DADOS DE TRANSPORTE POR REGIÃO\2026\Volumetria Geral Origem PR DTOP e GMP"
arquivo_csv = f"{caminho_base}\\Volumetria DTOP GMP GERAL 01072026 17112026.csv"

print("Carregando base...")
df = pd.read_csv(arquivo_csv, sep=';', encoding='utf-8-sig', dtype=str, low_memory=False)
df.columns = [c.strip() for c in df.columns]

# ---------------- normalização ----------------
def num(s):
    if pd.isna(s):
        return 0.0
    s = str(s).strip()
    if s == '':
        return 0.0
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except Exception:
        return 0.0

df['Emissao'] = pd.to_datetime(df['Emissão'], dayfirst=True, errors='coerce')
df['Coleta'] = pd.to_datetime(df['Data de Coleta'], dayfirst=True, errors='coerce')
df['Mes'] = df['Coleta'].dt.to_period('M').astype(str)
df.loc[df['Coleta'].isna(), 'Mes'] = df.loc[df['Coleta'].isna(), 'Emissao'].dt.to_period('M').astype(str)

df['Valor'] = df['Valor Total'].map(num)
df['Peso'] = df['Peso Liquido'].map(num)
df['Vol'] = df['Quantidade Volumne'].map(num).astype(int)

for col, novo in [('UF Ent.', 'UF'), ('Cidade Entrega', 'Cidade'), ('Empresa', 'Empresa'),
                  ('Transportadora', 'Transportadora'), ('Canal', 'Canal')]:
    df[novo] = df[col].fillna('-').astype(str).str.strip()

df['Cep'] = df['Cep entrega'].fillna('-').astype(str).str.strip()

# Rodonaves x Outra Transportadora
df['TranspGrupo'] = np.where(df['Transportadora'].str.upper().str.contains('RODONAVES'), 1, 0)

# Peso cubado — vem da base auxiliar "PESO CUBADO ..." (coluna AG = Peso Cubado Produto),
# correlacionada pelo Pedido (coluna R). NF (coluna Q) não correlaciona entre as bases.
arquivo_cub = f"{caminho_base}\\PESO CUBADO Volumetria DTOP GMP GERAL 01072026 17112026.csv"
col_perf = df.columns[7]  # coluna H = "Performance entrega  Transportadora"

# remove linhas sem UF válida
df = df[df['UF'].str.len() == 2].copy()

# ---- SLA de entrega (coluna H) ----
perf = df[col_perf].fillna('').astype(str).str.upper()
df['SLA'] = np.where(perf.str.contains('ATRASO'), 'Atrasado',
                     np.where(perf.str.contains('PRAZO'), 'No prazo', 'Não informado'))

# ---- correlaciona o peso cubado pelo Pedido ----
cub = pd.read_csv(arquivo_cub, sep=';', encoding='utf-8-sig', dtype=str, low_memory=False)
cub.columns = [c.strip() for c in cub.columns]
cub['PedidoKey'] = cub['Pedido'].fillna('').astype(str).str.strip()
cub['Cubado'] = cub['Peso Cubado Produto'].map(num)
cub = cub.groupby('PedidoKey')['Cubado'].sum(min_count=1).reset_index()
df['PedidoKey'] = df['Pedido'].fillna('').astype(str).str.strip()
df = df.merge(cub, on='PedidoKey', how='left')
print(f"Peso cubado correlacionado: {df['Cubado'].notna().sum()}/{len(df)} pedidos")

# período
coleta_min = df['Coleta'].min()
coleta_max = df['Coleta'].max()
periodo_txt = f"{coleta_min.strftime('%d/%m/%Y')} a {coleta_max.strftime('%d/%m/%Y')}" if pd.notna(coleta_min) else "—"
data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")

print(f"Registros: {len(df)} | Período: {periodo_txt}")

# ---------------- registros para o JS ----------------
pedidos = []
for _, r in df.iterrows():
    coleta = r['Coleta'].strftime('%d/%m/%Y') if pd.notna(r['Coleta']) else (r['Emissao'].strftime('%d/%m/%Y') if pd.notna(r['Emissao']) else '-')
    cub = None if pd.isna(r['Cubado']) else round(float(r['Cubado']), 3)
    pedidos.append([
        r['Mes'], r['UF'], r['Cidade'], r['Empresa'], int(r['TranspGrupo']),
        int(r['Vol']), round(float(r['Peso']), 3), round(float(r['Valor']), 2),
        r['Cep'], coleta, r['Transportadora'], r['Canal'], cub, r['SLA']
    ])
pedidos_json = json.dumps(pedidos, ensure_ascii=False, separators=(',', ':'))

# ---------------- Excel ----------------
resumo_uf = df.groupby('UF').agg(Envios=('Vol', 'count'), Volumes=('Vol', 'sum'),
                                 Peso_KG=('Peso', 'sum'), Valor=('Valor', 'sum')).reset_index()
resumo_uf['Peso_Ton'] = (resumo_uf['Peso_KG'] / 1000).round(3)
resumo_uf['Peso_Vol'] = np.where(resumo_uf['Volumes'] > 0, (resumo_uf['Peso_KG'] / resumo_uf['Volumes']).round(3), 0)
resumo_uf['Ticket_Medio'] = (resumo_uf['Valor'] / resumo_uf['Envios']).round(2)
resumo_uf = resumo_uf.sort_values('Peso_KG', ascending=False)

resumo_mes = df.groupby('Mes').agg(Envios=('Vol', 'count'), Volumes=('Vol', 'sum'),
                                   Peso_KG=('Peso', 'sum'), Valor=('Valor', 'sum')).reset_index()
resumo_mes['Peso_Ton'] = (resumo_mes['Peso_KG'] / 1000).round(3)
resumo_mes['Peso_Vol'] = np.where(resumo_mes['Volumes'] > 0, (resumo_mes['Peso_KG'] / resumo_mes['Volumes']).round(3), 0)

detalhado = pd.DataFrame({
    'Data Coleta': df['Coleta'].dt.strftime('%d/%m/%Y'),
    'Emissão': df['Emissao'].dt.strftime('%d/%m/%Y'),
    'Empresa': df['Empresa'],
    'Transportadora': df['Transportadora'],
    'Grupo Transp.': np.where(df['TranspGrupo'] == 1, 'Rodonaves', 'Outra Transportadora'),
    'Canal': df['Canal'],
    'CEP Destino': df['Cep'],
    'UF': df['UF'],
    'Cidade': df['Cidade'],
    'Volumes': df['Vol'],
    'Peso Líquido (kg)': df['Peso'].round(3),
    'Peso Cubado (kg)': df['Cubado'].round(3),
    'SLA de Entrega': df['SLA'],
    'Valor Total (R$)': df['Valor'].round(2),
}).sort_values(['Data Coleta', 'UF'])

arq_xlsx = f"{caminho_base}\\volumetria_guimepa_consolidado.xlsx"
with pd.ExcelWriter(arq_xlsx, engine='openpyxl') as w:
    resumo_uf.to_excel(w, sheet_name='Resumo por UF', index=False)
    resumo_mes.sort_values('Mes', ascending=False).to_excel(w, sheet_name='Resumo Mensal', index=False)
    detalhado.to_excel(w, sheet_name='Pedidos Enviados', index=False)
print(f"Excel: {arq_xlsx}")

# ---------------- HTML ----------------
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Roboto:wght@300;400;500;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Roboto,Tahoma,Geneva,Verdana,sans-serif;background:#f1f5f9;color:#1e293b;line-height:1.5;font-size:14px}
h1,h2,h3{font-family:'Segoe UI',Roboto,sans-serif;overflow-wrap:break-word}
.container{max-width:1400px;margin:0 auto;padding:24px;min-width:0}
.header{background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 50%,#1e40af 100%);color:#fff;padding:40px;border-radius:16px;margin-bottom:24px;position:relative;overflow:hidden}
.header::after{content:'';position:absolute;top:-40%;right:-5%;width:350px;height:350px;background:rgba(59,130,246,.15);border-radius:50%}
.header h1{font-size:26px;font-weight:700;margin-bottom:8px;letter-spacing:.3px}
.header .sub{font-size:14px;opacity:.85}
.header .periodo{display:inline-block;background:rgba(255,255,255,.15);padding:6px 16px;border-radius:20px;margin-top:12px;font-size:13px;font-weight:500}

.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:16px;margin-bottom:24px;align-items:stretch}
.kpi-card{background:#fff;border-radius:12px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.08);position:relative;overflow:hidden;display:flex;flex-direction:column;min-height:150px;min-width:0}
.kpi-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px}
.kpi-card .icon{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:16px;margin-bottom:8px;flex-shrink:0}
.kpi-card .label{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;font-weight:600;overflow:hidden;text-overflow:ellipsis}
.kpi-card .valor{font-size:22px;font-weight:700;margin:8px 0 2px;font-variant-numeric:tabular-nums;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.kpi-card .detalhe{font-size:12px;color:#94a3b8;margin-bottom:0}
.kpi-blue::before{background:linear-gradient(90deg,#2563eb,#3b82f6)} .kpi-blue .icon{background:#eff6ff;color:#2563eb} .kpi-blue .valor{color:#1e40af}
.kpi-emerald::before{background:linear-gradient(90deg,#059669,#10b981)} .kpi-emerald .icon{background:#ecfdf5;color:#059669} .kpi-emerald .valor{color:#065f46}
.kpi-amber::before{background:linear-gradient(90deg,#d97706,#f59e0b)} .kpi-amber .icon{background:#fffbeb;color:#d97706} .kpi-amber .valor{color:#92400e}
.kpi-violet::before{background:linear-gradient(90deg,#7c3aed,#8b5cf6)} .kpi-violet .icon{background:#f5f3ff;color:#7c3aed} .kpi-violet .valor{color:#5b21b6}
.kpi-rose::before{background:linear-gradient(90deg,#e11d48,#f43f5e)} .kpi-rose .icon{background:#fff1f2;color:#e11d48} .kpi-rose .valor{color:#9f1239}
.kpi-cyan::before{background:linear-gradient(90deg,#0891b2,#06b6d4)} .kpi-cyan .icon{background:#ecfeff;color:#0891b2} .kpi-cyan .valor{color:#155e75}
.kpi-expand-detail{display:block;margin-top:12px;padding:10px;border-top:1px solid #e2e8f0;background:#f8fafc;border-radius:0 0 10px 10px}
.kpi-expand-detail .det-row{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:4px 2px;font-size:12px;min-width:0;border-bottom:1px dashed #e8edf3}
.kpi-expand-detail .det-row:last-child{border-bottom:none}
.kpi-expand-detail .det-row span:first-child{color:#475569;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.kpi-expand-detail .det-row span:last-child{font-weight:700;white-space:nowrap;font-variant-numeric:tabular-nums}
.kpi-expand-detail .det-row.det-best{background:#dcfce7;border:1px solid #86efac;border-radius:6px;padding:5px 8px;margin:3px 0;border-bottom:1px solid #86efac}
.kpi-expand-detail .det-row.det-best span:first-child{color:#065f46;font-weight:700}
.kpi-expand-detail .det-row.det-best span:first-child::before{content:'★ ';color:#059669}
.kpi-expand-detail .det-row.det-best span:last-child{color:#047857}

/* Filtro global */
.filtro-global{background:#fff;border-radius:12px;padding:18px 20px;box-shadow:0 1px 3px rgba(0,0,0,.08);margin-bottom:24px;border-left:4px solid #1e40af;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.filtro-global .fg-label{font-size:12px;font-weight:700;color:#1e3a5f;text-transform:uppercase;letter-spacing:.5px;white-space:nowrap}
.filtro-global .fg-label small{display:block;font-size:10px;font-weight:500;color:#94a3b8;text-transform:none;letter-spacing:0}
.seg{display:inline-flex;background:#f1f5f9;border-radius:10px;padding:4px;gap:4px;flex-wrap:wrap}
.seg button{border:none;background:transparent;padding:9px 18px;border-radius:8px;font-size:13px;font-weight:600;color:#475569;cursor:pointer;font-family:inherit;transition:.15s;white-space:nowrap}
.seg button:hover{background:#e2e8f0}
.seg button.active{background:#1e40af;color:#fff;box-shadow:0 2px 6px rgba(30,64,175,.35)}
.seg button .cnt{font-size:11px;opacity:.8;margin-left:6px;font-weight:500}

.section{background:#fff;border-radius:12px;padding:24px;box-shadow:0 1px 3px rgba(0,0,0,.08);margin-bottom:24px;min-width:0;overflow:hidden}
.section h2{font-size:18px;font-weight:700;color:#1e3a5f;margin-bottom:4px;display:flex;align-items:center;gap:8px}
.section h2::before{content:'';width:4px;height:20px;background:#2563eb;border-radius:2px;display:inline-block;flex-shrink:0}
.section .desc{font-size:13px;color:#64748b;margin-bottom:16px}

.filter-bar{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:16px;padding:14px;background:#f8fafc;border-radius:10px;border:1px solid #e2e8f0;align-items:flex-end}
.filter-group{display:flex;flex-direction:column;gap:3px}
.filter-group label{font-size:10px;font-weight:600;color:#475569;text-transform:uppercase;letter-spacing:.3px}
.filter-group select,.filter-group input{padding:7px 10px;border:1px solid #cbd5e1;border-radius:8px;font-size:12px;font-family:inherit;background:#fff;min-width:120px}
.filter-group select:focus,.filter-group input:focus{outline:none;border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,.15)}
.btn-filter{padding:7px 16px;background:#2563eb;color:#fff;border:none;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit}
.btn-filter:hover{background:#1d4ed8}
.btn-clear{padding:7px 14px;background:#e2e8f0;color:#475569;border:none;border-radius:8px;font-size:12px;font-weight:500;cursor:pointer;font-family:inherit}
.btn-clear:hover{background:#cbd5e1}
.btn-top5{padding:7px 16px;background:#059669;color:#fff;border:none;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit}
.btn-top5:hover{background:#047857}
.btn-top5.active{background:#dc2626}

table{width:100%;border-collapse:collapse;font-size:12px}
thead th{background:#f8fafc;color:#475569;font-weight:600;text-align:center;padding:8px 10px;border-bottom:2px solid #e2e8f0;white-space:nowrap;position:sticky;top:0;z-index:1;font-size:11px;text-transform:uppercase;letter-spacing:.3px}
thead th:first-child{text-align:left}
tbody td{padding:7px 10px;border-bottom:1px solid #f1f5f9;text-align:center;font-variant-numeric:tabular-nums}
tbody td:first-child{text-align:left}
tbody tr:hover{background:#f8fafc}
tfoot td{padding:8px 10px;border-top:2px solid #2563eb;font-weight:700;background:#eff6ff;text-align:center}
tfoot td:first-child{text-align:left}
th.sortable{cursor:pointer;user-select:none}
th.sortable:hover{color:#1e40af}
.sort-ind{color:#94a3b8;font-size:9px;margin-left:4px}
th.sorted-asc .sort-ind,th.sorted-desc .sort-ind{color:#1e40af;font-weight:700}
table.th-contrast thead th{background:#1e3a5f;color:#fff;border-bottom:2px solid #0f172a}
table.th-contrast thead th .sort-ind{color:#93c5fd}
table.th-contrast thead th.sorted-asc .sort-ind,table.th-contrast thead th.sorted-desc .sort-ind{color:#fde047}

.tag{display:inline-block;padding:2px 7px;border-radius:10px;font-size:10px;font-weight:600;white-space:nowrap;flex:0 0 auto}
.tag-alto{background:#fef2f2;color:#dc2626}
.tag-medio{background:#fffbeb;color:#d97706}
.tag-baixo{background:#f0fdf4;color:#16a34a}
.tag-reg{background:#e0e7ff;color:#3730a3}
.pv-cell{display:flex;align-items:center;justify-content:center;gap:6px;white-space:nowrap}
.pv-val{min-width:58px;text-align:right;font-variant-numeric:tabular-nums}
.center-all th,.center-all td{text-align:center !important}
.barra-bg{background:#e2e8f0;border-radius:3px;height:14px;width:100px;overflow:hidden;flex-shrink:0;display:inline-block;vertical-align:middle}
.barra-fill{height:100%;border-radius:3px}
.table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;min-width:0}
.footer{text-align:center;padding:24px;color:#94a3b8;font-size:12px;margin-top:16px}

.regiao-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px}
.regiao-card{background:#fff;border-radius:12px;padding:18px 20px;box-shadow:0 1px 3px rgba(0,0,0,.08);border-top:3px solid #2563eb;min-width:0;overflow:hidden}
.regiao-card h3{font-size:14px;font-weight:700;color:#1e3a5f;margin-bottom:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.regiao-card .rg-row{display:flex;justify-content:space-between;align-items:baseline;gap:8px;padding:3px 0;font-size:12px;min-width:0}
.regiao-card .rg-row span:first-child{color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.regiao-card .rg-row strong{font-weight:700;color:#0f172a;white-space:nowrap;font-variant-numeric:tabular-nums}
.regiao-norte{border-top-color:#1e3a5f} .regiao-nordeste{border-top-color:#2563eb} .regiao-centro-oeste{border-top-color:#06b6d4} .regiao-sudeste{border-top-color:#10b981} .regiao-sul{border-top-color:#f59e0b}

.pivot-table{width:100%;border-collapse:collapse;font-size:11px}
.pivot-table th{background:#f8fafc;padding:6px 8px;border-bottom:1px solid #e2e8f0;font-weight:600;text-align:center;font-size:10px;white-space:nowrap}
.pivot-table th:first-child{text-align:left;min-width:90px}
.pivot-table td{padding:5px 8px;text-align:center;border-bottom:1px solid #f1f5f9;font-variant-numeric:tabular-nums}
.pivot-table td:first-child{text-align:left;font-weight:600}
.pivot-table .ca{background:#dcfce7}
.pivot-table .cb{background:#fef2f2}
.pivot-table .pt{font-weight:700;background:#eff6ff;border-top:2px solid #2563eb}
.pivot-table .au{color:#16a34a;font-weight:700}
.pivot-table .ad{color:#dc2626;font-weight:700}

.transp-chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.chip{padding:7px 14px;background:#eef2ff;color:#3730a3;border:1px solid #c7d2fe;border-radius:20px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
.chip:hover{background:#e0e7ff}
.chip.active{background:#1e40af;color:#fff;border-color:#1e40af}
.transp-panel{background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:18px;min-width:0}
.transp-head{display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap}
.transp-head strong{font-size:16px;color:#1e3a5f;overflow:hidden;text-overflow:ellipsis}
.transp-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:12px}
.transp-stat{background:#fff;border-radius:8px;padding:10px 12px;box-shadow:0 1px 2px rgba(0,0,0,.06);min-width:0}
.transp-stat span{display:block;font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.4px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.transp-stat strong{font-size:16px;color:#0f172a;font-variant-numeric:tabular-nums;white-space:nowrap}
.transp-ufs{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:12px;color:#475569;margin-bottom:10px}
.transp-insight{font-size:12px;color:#334155;background:#eff6ff;border-left:3px solid #2563eb;border-radius:0 8px 8px 0;padding:10px 12px;line-height:1.6}

#graficoPlotly,#evolChart{width:100%;height:420px;min-width:0}

@media(max-width:768px){
  .container{padding:12px}
  .header{padding:24px}
  .header h1{font-size:20px}
  .kpi-grid{grid-template-columns:repeat(2,1fr);gap:10px}
  .regiao-grid{grid-template-columns:1fr;gap:10px}
  .kpi-card .valor{font-size:18px}
  table{font-size:10px}
  thead th,tbody td,tfoot td{padding:5px 6px}
  .filter-bar{flex-direction:column;align-items:stretch}
  #graficoPlotly,#evolChart{height:360px}
}
"""

html = []
html.append('<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n<meta charset="UTF-8">')
html.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
html.append('<meta name="robots" content="noindex, nofollow">')
html.append('<title>VOLUMETRIA GERAL ORIGEM PR GUIMEPA</title>')
html.append('<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>')
html.append('<style>' + CSS + '</style>')
html.append('</head>\n<body>\n<div class="container">')

html.append(f'''
<div class="header">
  <h1>VOLUMETRIA GERAL ORIGEM PR GUIMEPA</h1>
  <div class="sub">DTOP e GMP — Análise de Volumetria e Expedição</div>
  <div class="periodo">Período: {periodo_txt} &nbsp;|&nbsp; Gerado em {data_geracao}</div>
</div>
''')

html.append('<div id="kpis"></div>')
html.append('''
<div class="filtro-global">
  <div class="fg-label">Filtro de transportadora<small>Aplica-se aos quadros abaixo — a Progressão de Volumes tem filtro próprio</small></div>
  <div class="seg" id="segTransp">
    <button data-g="todas" class="active" onclick="setGrupo('todas')">Todas<span class="cnt" id="cTodas"></span></button>
    <button data-g="rod" onclick="setGrupo('rod')">Rodonaves<span class="cnt" id="cRod"></span></button>
    <button data-g="outra" onclick="setGrupo('outra')">Outra Transportadora<span class="cnt" id="cOutra"></span></button>
  </div>
</div>
''')

html.append('<div id="resumoMensal"></div>')
html.append('<div id="consolidado"></div>')
html.append('<div id="pedidos"></div>')
html.append('<div id="progressao"></div>')
html.append('<div id="evolucao"></div>')

html.append(f'''
<div class="footer">
  Relatório gerado em {data_geracao} &nbsp;|&nbsp; Base: {periodo_txt} &nbsp;|&nbsp; VOLUMETRIA GERAL ORIGEM PR GUIMEPA
</div>
</div>
''')

JS = r'''
const PED = __PEDIDOS__;
const REGIOES = {
  'Norte':['AC','AM','AP','PA','RO','RR','TO'],
  'Nordeste':['AL','BA','CE','MA','PB','PE','PI','RN','SE'],
  'Centro-Oeste':['DF','GO','MS','MT'],
  'Sudeste':['ES','MG','RJ','SP'],
  'Sul':['PR','RS','SC']
};
const UF_REG = {};
for (const [reg, ufs] of Object.entries(REGIOES)) for (const uf of ufs) UF_REG[uf] = reg;

const ST = {grupo:'todas', view:'uf', sort:{col:null,dir:1}, chart:false, top5:false,
            evol:{reg:'Sudeste', met:'volumes', vis:'tabela'},
            prog:{grupo:'ambos', faixa:'todas'},
            ped:{sortCol:0, dir:-1, campo:'todos', busca:'', pageSize:50, page:1}};

function nf(v,d){ return Number(v||0).toLocaleString('pt-BR',{minimumFractionDigits:d||0,maximumFractionDigits:d||0}); }
function money(v){ return 'R$ ' + nf(v,2); }
function moneyAb(v){
  v = Number(v||0);
  if (v >= 1e6) return 'R$ ' + nf(v/1e6,2) + ' M';
  if (v >= 1e3) return 'R$ ' + nf(v/1e3,1) + ' mil';
  return money(v);
}
function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function title(s){ return String(s).toLowerCase().replace(/\b\w/g, c=>c.toUpperCase()); }
function tagPv(pv){ return pv < 2 ? '<span class="tag tag-baixo">Leve</span>' : (pv < 5 ? '<span class="tag tag-medio">Médio</span>' : '<span class="tag tag-alto">Pesado</span>'); }
function regiao(uf){ return UF_REG[uf] || 'Outro'; }
function mesLabel(m){ const [y,mm]=m.split('-'); const n=['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']; return n[parseInt(mm,10)-1] + '/' + y; }

function grupoRows(){
  if (ST.grupo === 'rod') return PED.filter(r => r[4] === 1);
  if (ST.grupo === 'outra') return PED.filter(r => r[4] === 0);
  return PED;
}

function agrega(rows, keyFn){
  const m = new Map();
  for (const r of rows){
    const k = keyFn(r);
    if (!m.has(k)) m.set(k, {nome:k, envios:0, vol:0, peso:0, valor:0});
    const o = m.get(k);
    o.envios++; o.vol += r[5]; o.peso += r[6]; o.valor += r[7];
  }
  const arr = [...m.values()];
  for (const o of arr){
    o.ton = o.peso/1000;
    o.ticket = o.envios ? o.valor/o.envios : 0;
    o.pv = o.vol ? o.peso/o.vol : 0;
  }
  return arr;
}

/* ---------------- KPIs ---------------- */
function renderKPIs(){
  const rows = grupoRows();
  const tot = rows.length;
  const vol = rows.reduce((a,r)=>a+r[5],0);
  const peso = rows.reduce((a,r)=>a+r[6],0);
  const valor = rows.reduce((a,r)=>a+r[7],0);
  const ticket = tot ? valor/tot : 0;
  const pv = vol ? peso/vol : 0;

  const byReg = agrega(rows, r => regiao(r[1]));
  byReg.sort((a,b)=>b.vol-a.vol);
  const campoChave = {envios:'envios', vol:'vol', ton:'ton', valor:'valor', ticket:'ticket', pv:'pv'};

  const defs = [
    ['blue','&#128230;','Total de Envios', nf(tot), 'pedidos/notas', 'envios'],
    ['emerald','&#128230;','Total de Volumes', nf(vol), 'caixas expedidas', 'vol'],
    ['amber','&#9878;','Peso Total', nf(peso/1000,2)+' ton', nf(peso,2)+' kg', 'ton'],
    ['violet','&#128176;','Valor Total', moneyAb(valor), 'transportado', 'valor'],
    ['rose','&#128176;','Ticket Médio', money(ticket), 'por envio', 'ticket'],
    ['cyan','&#9878;','Peso Médio / Volume', nf(pv,3)+' kg', 'média geral', 'pv']
  ];
  let h = '<div class="kpi-grid">';
  for (const [cor, ico, rot, val, det, chave] of defs){
    h += '<div class="kpi-card kpi-'+cor+'"><div class="icon">'+ico+'</div><div class="label">'+rot+'</div><div class="valor">'+val+'</div><div class="detalhe">'+det+'</div>';
    h += '<div class="kpi-expand-detail">';
    const kk = campoChave[chave];
    let best = -Infinity;
    for (const o of byReg) best = Math.max(best, o[kk] || 0);
    for (const o of byReg){
      let cell = '';
      if (chave==='envios') cell = nf(o.envios);
      else if (chave==='vol') cell = nf(o.vol);
      else if (chave==='ton') cell = nf(o.ton,2)+' ton';
      else if (chave==='valor') cell = moneyAb(o.valor);
      else if (chave==='ticket') cell = money(o.ticket);
      else cell = nf(o.pv,3)+' kg';
      const isBest = byReg.length > 1 && (o[kk] || 0) === best;
      h += '<div class="det-row'+(isBest?' det-best':'')+'"><span>'+esc(o.nome)+'</span><span>'+cell+'</span></div>';
    }
    h += '</div></div>';
  }
  h += '</div>';
  document.getElementById('kpis').innerHTML = h;
}

/* ---------------- Resumo mensal ---------------- */
function renderResumoMensal(){
  const rows = grupoRows();
  const byMes = agrega(rows, r => r[0]);
  byMes.sort((a,b)=> b.nome.localeCompare(a.nome)); // mais recente primeiro
  const totPeso = byMes.reduce((a,o)=>a+o.peso,0);
  let h = '<div class="section"><h2>Resumo Mensal Geral</h2><div class="desc">Totais agregados por mês de referência — do mais recente para o mais antigo.</div>';
  h += '<div class="table-wrap"><table class="th-contrast"><thead><tr><th>Mês</th><th>Envios</th><th>Volumes</th><th>Peso (ton)</th><th>Valor Total</th><th>Peso/Vol</th><th>% do Peso</th></tr></thead><tbody>';
  let sEnv=0,sVol=0,sPeso=0,sValor=0;
  for (const o of byMes){
    sEnv+=o.envios; sVol+=o.vol; sPeso+=o.peso; sValor+=o.valor;
    const pct = totPeso ? o.peso/totPeso*100 : 0;
    h += '<tr><td><strong>'+esc(o.nome)+'</strong></td><td>'+nf(o.envios)+'</td><td>'+nf(o.vol)+'</td><td>'+nf(o.ton,3)+'</td><td>'+money(o.valor)+'</td><td><div class="pv-cell"><span class="pv-val">'+nf(o.pv,3)+'</span>'+tagPv(o.pv)+'</div></td><td>'+nf(pct,2)+'%</td></tr>';
  }
  h += '</tbody><tfoot><tr><td>TOTAL</td><td>'+nf(sEnv)+'</td><td>'+nf(sVol)+'</td><td>'+nf(sPeso/1000,3)+'</td><td>'+money(sValor)+'</td><td>'+nf(sVol?sPeso/sVol:0,3)+'</td><td>100%</td></tr></tfoot></table></div></div>';
  document.getElementById('resumoMensal').innerHTML = h;
}

/* ---------------- Consolidado ---------------- */
function dadosConsolidado(){
  const rows = grupoRows();
  if (ST.view === 'regiao'){
    const arr = agrega(rows, r => regiao(r[1]));
    return {arr, nomeF:'data-reg', label:'Região'};
  }
  if (ST.view === 'cidades'){
    const arr = agrega(rows, r => r[2]);
    arr.sort((a,b)=>b.peso-a.peso);
    return {arr: arr.slice(0,10), nomeF:'data-cidade', label:'Cidade'};
  }
  const arr = agrega(rows, r => r[1]);
  return {arr, nomeF:'data-uf', label:'UF'};
}

function renderConsolidado(){
  const {arr, nomeF, label} = dadosConsolidado();
  const totEnv = arr.reduce((a,o)=>a+o.envios,0);
  const totVol = arr.reduce((a,o)=>a+o.vol,0);
  const totPeso = arr.reduce((a,o)=>a+o.peso,0);
  const totValor = arr.reduce((a,o)=>a+o.valor,0);
  const maxPeso = Math.max(...arr.map(o=>o.peso), 1);

  const col = ST.sort.col;
  let lista = arr.slice();
  if (col !== null && col !== undefined){
    const dir = ST.sort.dir;
    lista.sort((a,b)=>{
      const map = {0:'nome',1:'envios',2:'valor',3:'peso',4:'pv',5:'pctvol',6:'pctpeso'};
      const k = map[col];
      let va, vb;
      if (k === 'nome'){ va = a.nome.toLowerCase(); vb = b.nome.toLowerCase(); return va<vb?-dir:(va>vb?dir:0); }
      if (k === 'pctvol'){ va = totVol?a.vol/totVol:0; vb = totVol?b.vol/totVol:0; }
      else if (k === 'pctpeso'){ va = totPeso?a.peso/totPeso:0; vb = totPeso?b.peso/totPeso:0; }
      else { va = a[k]; vb = b[k]; }
      return dir*(va-vb);
    });
  }

  if (ST.top5){
    lista = lista.slice().sort((a,b)=>b.peso-a.peso).slice(0,5);
  }

  let h = '<div class="section"><h2>Consolidado por '+(ST.view==='uf'?'UF de Entrega':(ST.view==='regiao'?'Região':'Top 10 Cidades de Entrega'))+'</h2>';
  h += '<div class="desc">Volumetria agregada. Clique nos títulos das colunas para ordenar (crescente/decrescente).</div>';
  h += '<div class="filter-bar">';
  h += '<button class="btn-clear'+(ST.view==='uf'?' active':'')+'" onclick="setView(\'uf\')">Por UF</button>';
  h += '<button class="btn-clear'+(ST.view==='regiao'?' active':'')+'" onclick="setView(\'regiao\')">Por Região</button>';
  h += '<button class="btn-clear'+(ST.view==='cidades'?' active':'')+'" onclick="setView(\'cidades\')">Top 10 Cidades</button>';
  h += '<button class="btn-top5'+(ST.top5?' active':'')+'" onclick="toggleTop5()">'+(ST.top5?'Mostrar Todos':'Top 5 '+label+'s')+'</button>';
  h += '<button class="btn-filter" onclick="toggleChart()">'+(ST.chart?'Visualizar como tabela':'Visualizar como gráfico')+'</button>';
  h += '</div>';

  if (ST.chart){
    h += '<div class="filter-bar">';
    h += '<div class="filter-group"><label>Barras</label><select id="selBarra" onchange="desenharGrafico()"><option value="vol">Volumes</option><option value="ton">Peso (ton)</option><option value="valor">Valor Total</option><option value="envios">Envios</option></select></div>';
    h += '<div class="filter-group"><label>Linha</label><select id="selLinha" onchange="desenharGrafico()"><option value="ton">Peso (ton)</option><option value="valor">Valor Total</option><option value="ticket">Ticket Médio</option><option value="pv">Peso/Vol</option></select></div>';
    h += '</div><div id="graficoPlotly" style="height:430px"></div>';
  } else {
    h += '<div class="table-wrap"><table id="tabelaCons" class="center-all th-contrast"><thead><tr>';
    const cols = ['#'+label,'Envios','Valor Total','Peso Total (kg)','Peso/Vol','% Volume','% Peso'];
    cols.forEach((c,i)=>{ h += '<th class="sortable" onclick="sortCons('+i+')">'+c+'<span class="sort-ind">▲▼</span></th>'; });
    h += '</tr></thead><tbody>';

    if (!lista.length) h += '<tr><td colspan="7" style="text-align:center;color:#94a3b8;padding:20px">Sem dados para o filtro selecionado.</td></tr>';

    for (const o of lista){
      const pctVol = totVol ? o.vol/totVol*100 : 0;
      const pctPeso = totPeso ? o.peso/totPeso*100 : 0;
      const nome = (ST.view==='cidades') ? title(o.nome) : o.nome;
      h += '<tr '+nomeF+'="'+esc(o.nome)+'" data-vol="'+o.vol+'" data-ton="'+o.ton+'" data-valor="'+o.valor+'" data-ticket="'+o.ticket+'" data-pv="'+o.pv+'">';
      h += '<td><strong>'+esc(nome)+'</strong></td>';
      h += '<td>'+nf(o.envios)+'</td>';
      h += '<td>'+money(o.valor)+'</td>';
      h += '<td>'+nf(o.peso,2)+'</td>';
      h += '<td><div class="pv-cell"><span class="pv-val">'+nf(o.pv,3)+'</span>'+tagPv(o.pv)+'</div></td>';
      h += '<td>'+nf(pctVol,2)+'%</td><td>'+nf(pctPeso,2)+'%</td>';
      h += '</tr>';
    }
    h += '</tbody>';
    if (lista.length){
      h += '<tfoot><tr><td>TOTAL</td><td>'+nf(totEnv)+'</td><td>'+money(totValor)+'</td><td>'+nf(totPeso,2)+'</td><td>'+nf(totVol?totPeso/totVol:0,3)+'</td><td>100%</td><td>100%</td></tr></tfoot>';
    }
    h += '</table></div>';
  }
  h += '</div>';
  document.getElementById('consolidado').innerHTML = h;
  if (ST.chart) desenharGrafico();
}

function setView(v){ ST.view = v; ST.top5 = false; ST.sort = {col:null,dir:1}; renderConsolidado(); }
function sortCons(i){
  if (ST.sort.col === i) ST.sort.dir *= -1;
  else { ST.sort.col = i; ST.sort.dir = 1; }
  renderConsolidado();
}
function toggleTop5(){ ST.top5 = !ST.top5; renderConsolidado(); }
function toggleChart(){ ST.chart = !ST.chart; renderConsolidado(); }

function desenharGrafico(){
  const el = document.getElementById('graficoPlotly');
  if (!el) return;
  const d = dadosConsolidado();
  let arr = d.arr.slice();
  if (ST.top5) arr = arr.slice().sort((a,b)=>b.peso-a.peso).slice(0,5);
  const mb = document.getElementById('selBarra').value;
  const ml = document.getElementById('selLinha').value;
  const nomes = {envios:'Envios', vol:'Volumes', ton:'Peso (ton)', valor:'Valor Total', ticket:'Ticket Médio', pv:'Peso/Vol'};
  const labels = arr.map(o=> ST.view==='cidades' ? title(o.nome) : o.nome);
  const suf = ST.view==='uf'?' por UF':(ST.view==='regiao'?' por Região':' por Cidade');
  Plotly.newPlot('graficoPlotly', [
    {type:'bar', x:labels, y:arr.map(o=>o[mb]||0), name:nomes[mb], marker:{color:'#2563eb'}, yaxis:'y'},
    {type:'line', x:labels, y:arr.map(o=>o[ml]||0), name:nomes[ml], yaxis:'y2', mode:'lines+markers', line:{color:'#dc2626',width:3}}
  ], {
    title: nomes[mb]+' e '+nomes[ml]+suf,
    xaxis:{title:'', tickangle:45},
    yaxis:{title:nomes[mb], titlefont:{color:'#2563eb'}},
    yaxis2:{title:nomes[ml], titlefont:{color:'#dc2626'}, overlaying:'y', side:'right'},
    legend:{orientation:'h', y:1.12},
    margin:{l:50,r:50,t:70,b:110},
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)'
  }, {displayModeBar:false});
}

/* ---------------- Evolução mensal ---------------- */
function renderEvolucao(){
  const rows = grupoRows();
  const met = ST.evol.met;
  const reg = ST.evol.reg;
  const metIdx = {envios:null, vol:5, peso:6, valor:7}[met];
  const nomesMet = {envios:'Envios', vol:'Volumes', peso:'Peso (ton)', valor:'Valor Total'};

  const meses = [...new Set(rows.map(r=>r[0]))].sort().reverse();
  const ufSet = new Map(); // uf -> {mes: valor}
  for (const r of rows){
    if (regiao(r[1]) !== reg) continue;
    const uf = r[1];
    if (!ufSet.has(uf)) ufSet.set(uf, {});
    const o = ufSet.get(uf);
    let v = 1;
    if (met === 'vol') v = r[5];
    else if (met === 'peso') v = r[6]/1000;
    else if (met === 'valor') v = r[7];
    o[r[0]] = (o[r[0]]||0) + v;
  }
  const ufs = [...ufSet.keys()].sort((a,b)=>{
    const ta = Object.values(ufSet.get(a)).reduce((x,y)=>x+y,0);
    const tb = Object.values(ufSet.get(b)).reduce((x,y)=>x+y,0);
    return tb-ta;
  });

  let h = '<div class="section"><h2>Evolução Mensal por Região</h2>';
  h += '<div class="desc">Acompanhe a evolução mensal por métrica. ▲ acima da média · ▼ abaixo da média.</div>';
  h += '<div class="filter-bar">';
  h += '<div class="filter-group"><label>Região</label><select id="evReg" onchange="setEvol()">';
  for (const rg of Object.keys(REGIOES)) h += '<option'+(rg===reg?' selected':'')+'>'+rg+'</option>';
  h += '</select></div>';
  h += '<div class="filter-group"><label>Métrica</label><select id="evMet" onchange="setEvol()">';
  for (const [k,v] of Object.entries(nomesMet)) h += '<option value="'+k+'"'+(k===met?' selected':'')+'>'+v+'</option>';
  h += '</select></div>';
  h += '<div class="filter-group"><label>Visão</label><select id="evVis" onchange="setEvol()">';
  h += '<option value="tabela"'+(ST.evol.vis==='tabela'?' selected':'')+'>Tabela</option><option value="grafico"'+(ST.evol.vis==='grafico'?' selected':'')+'>Gráfico</option>';
  h += '</select></div></div>';

  if (!ufs.length){
    h += '<p style="color:#94a3b8;font-size:13px;text-align:center;padding:20px">Sem dados para a região selecionada.</p></div>';
    document.getElementById('evolucao').innerHTML = h;
    return;
  }

  const fmtV = (v)=>{ if(met==='valor') return money(v); if(met==='peso') return nf(v,2); return nf(v); };

  if (ST.evol.vis === 'grafico'){
    h += '<div id="evolChart" style="height:420px"></div></div>';
    document.getElementById('evolucao').innerHTML = h;
    const traces = ufs.map(uf => ({
      x: meses.map(mesLabel), y: meses.map(m=>ufSet.get(uf)[m]||0),
      name: uf, mode:'lines+markers', type:'scatter'
    }));
    Plotly.newPlot('evolChart', traces, {
      title: nomesMet[met]+' por mês — '+reg,
      xaxis:{title:'Mês'}, yaxis:{title:nomesMet[met]},
      legend:{orientation:'h', y:1.12}, margin:{l:50,r:20,t:70,b:70},
      paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)'
    }, {displayModeBar:false});
    return;
  }

  // tabela
  h += '<div class="table-wrap"><table class="pivot-table th-contrast"><thead><tr><th>Mês</th>';
  for (const uf of ufs) h += '<th>'+uf+'</th>';
  h += '<th>Total</th></tr></thead><tbody>';
  for (const mes of meses){
    h += '<tr><td>'+esc(mes)+'</td>';
    let rowTot = 0;
    for (const uf of ufs){
      const v = ufSet.get(uf)[mes] || 0;
      rowTot += v;
      const serie = meses.map(m=>ufSet.get(uf)[m]||0);
      const media = serie.reduce((a,b)=>a+b,0)/serie.length;
      let cls='', arrow='';
      if (v>0 && v>media){ cls='ca'; arrow=' <span class="au">▲</span>'; }
      else if (v>0){ cls='cb'; arrow=' <span class="ad">▼</span>'; }
      h += '<td class="'+cls+'">'+(v>0?fmtV(v):'-')+arrow+'</td>';
    }
    h += '<td class="pt">'+fmtV(rowTot)+'</td></tr>';
  }
  h += '<tr class="pt"><td>TOTAL</td>';
  let grand = 0;
  for (const uf of ufs){
    const t = meses.reduce((a,m)=>a+(ufSet.get(uf)[m]||0),0);
    grand += t;
    h += '<td>'+fmtV(t)+'</td>';
  }
  h += '<td>'+fmtV(grand)+'</td></tr>';
  h += '</tbody></table></div></div>';
  h += '<div style="margin-top:8px;display:flex;gap:16px;font-size:11px;color:#64748b"><span><span class="au">▲</span> acima da média</span><span><span class="ad">▼</span> abaixo da média</span></div>';
  document.getElementById('evolucao').innerHTML = h;
}
function setEvol(){
  ST.evol.reg = document.getElementById('evReg').value;
  ST.evol.met = document.getElementById('evMet').value;
  ST.evol.vis = document.getElementById('evVis').value;
  renderEvolucao();
}

/* ---------------- Progressão de volumes ---------------- */
function faixaOk(peso, faixa){
  if (faixa==='todas') return true;
  if (faixa==='ate1') return peso <= 1;
  if (faixa==='1a3') return peso > 1 && peso <= 3;
  if (faixa==='3a10') return peso > 3 && peso <= 10;
  if (faixa==='10a30') return peso > 10 && peso <= 30;
  if (faixa==='ac30') return peso > 30;
  return true;
}

function renderProgressao(){
  // Filtro próprio e independente do filtro global de transportadora
  const base = PED.filter(r => faixaOk(r[6], ST.prog.faixa));
  const meses = [...new Set(base.map(r=>r[0]))].sort();
  const labels = meses.map(mesLabel);

  function serie(grp){
    const out = [];
    for (const m of meses){
      let s = 0;
      for (const r of base) if (r[0]===m && (grp===null || r[4]===grp)) s += r[5];
      out.push(s);
    }
    return out;
  }
  function qtd(grp){ return base.filter(r => grp===null || r[4]===grp).length; }

  const traces = [];
  if (ST.prog.grupo==='ambos' || ST.prog.grupo==='rod'){
    traces.push({type:'scatter', mode:'lines+markers', name:'Rodonaves', x:labels, y:serie(1),
      line:{color:'#dc2626', width:3}, marker:{size:9, color:'#dc2626'}});
  }
  if (ST.prog.grupo==='ambos' || ST.prog.grupo==='outra'){
    traces.push({type:'scatter', mode:'lines+markers', name:'Outras transportadoras', x:labels, y:serie(0),
      line:{color:'#2563eb', width:3}, marker:{size:9, color:'#2563eb'}});
  }

  let h = '<div class="section"><h2>Progressão de Volumes por Mês</h2>';
  h += '<div class="desc">Volumes expedidos como fato e o mês como dimensão de tempo. Este quadro tem <strong>filtro próprio</strong> (transportadora e faixa de peso), independente do filtro global.</div>';
  h += '<div class="filter-bar">';
  h += '<div class="filter-group"><label>Transportadora</label><select id="progGrupo" onchange="setProg()">';
  h += '<option value="ambos"'+(ST.prog.grupo==='ambos'?' selected':'')+'>Ambos (comparativo)</option>';
  h += '<option value="rod"'+(ST.prog.grupo==='rod'?' selected':'')+'>Somente Rodonaves</option>';
  h += '<option value="outra"'+(ST.prog.grupo==='outra'?' selected':'')+'>Somente outras transportadoras</option>';
  h += '</select></div>';
  h += '<div class="filter-group"><label>Faixa de peso (por pedido)</label><select id="progFaixa" onchange="setProg()">';
  const faixas = [['todas','Todas as faixas'],['ate1','Até 1 kg'],['1a3','1 a 3 kg'],['3a10','3 a 10 kg'],['10a30','10 a 30 kg'],['ac30','Acima de 30 kg']];
  for (const [k,l] of faixas) h += '<option value="'+k+'"'+(ST.prog.faixa===k?' selected':'')+'>'+l+'</option>';
  h += '</select></div>';
  h += '</div>';
  h += '<div class="transp-grid" style="margin-bottom:14px">';
  if (ST.prog.grupo==='ambos' || ST.prog.grupo==='rod') h += '<div class="transp-stat"><span>Pedidos · Rodonaves</span><strong>'+nf(qtd(1))+'</strong></div>';
  if (ST.prog.grupo==='ambos' || ST.prog.grupo==='outra') h += '<div class="transp-stat"><span>Pedidos · Outras</span><strong>'+nf(qtd(0))+'</strong></div>';
  h += '</div>';
  h += '<div id="progChart" style="height:400px"></div></div>';
  document.getElementById('progressao').innerHTML = h;

  Plotly.newPlot('progChart', traces, {
    xaxis:{title:'Mês'},
    yaxis:{title:'Volumes'},
    legend:{orientation:'h', y:1.15},
    margin:{l:55,r:20,t:60,b:60},
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
    hovermode:'x unified'
  }, {displayModeBar:false});
}
function setProg(){
  ST.prog.grupo = document.getElementById('progGrupo').value;
  ST.prog.faixa = document.getElementById('progFaixa').value;
  renderProgressao();
}

/* ---------------- Pedidos enviados ---------------- */
const PED_CAMPOS = [
  ['todos','Todos os campos'],['uf','UF'],['cidade','Cidade'],['transportadora','Transportadora'],
  ['empresa','Empresa'],['cep','CEP'],['coleta','Data de coleta'],['sla','SLA de entrega']
];

function nomeTransp(r){ return r[4]===1 ? 'Rodonaves' : 'Outra transportadora'; }

function valorCampoPed(r, campo){
  if (campo==='uf') return r[1];
  if (campo==='cidade') return r[2];
  if (campo==='transportadora') return nomeTransp(r);
  if (campo==='empresa') return r[3];
  if (campo==='cep') return r[8];
  if (campo==='coleta') return r[9];
  if (campo==='sla') return r[13];
  return r[1]+' '+r[2]+' '+r[3]+' '+r[8]+' '+nomeTransp(r)+' '+r[13];
}

const PED_COLS = ['Data Coleta','Valor Total','CEP Destino','UF','Cidade','Peso Líq. (kg)','Peso Cubado (kg)','Volumes','Transportadora','SLA de Entrega','Empresa'];
let PED_VIEW = [];

function celulasPed(r){
  return [
    r[9],                                  // Data Coleta
    money(r[7]),                           // Valor Total
    r[8],                                  // CEP Destino
    r[1],                                  // UF
    title(r[2]),                           // Cidade
    nf(r[6],3),                            // Peso Líq. (kg)
    (r[12]===null?'—':nf(r[12],3)),        // Peso Cubado (kg)
    nf(r[5]),                              // Volumes
    nomeTransp(r),                         // Transportadora
    r[13],                                 // SLA de Entrega
    r[3]                                   // Empresa
  ];
}

function csvCel(v){
  let s = String(v===null || v===undefined ? '' : v);
  if (/[;"\r\n]/.test(s)) s = '"' + s.replace(/"/g,'""') + '"';
  return s;
}

function baixarCSV(){
  const rows = PED_VIEW || [];
  const linhas = [PED_COLS.map(csvCel).join(';')];
  for (const r of rows) linhas.push(celulasPed(r).map(csvCel).join(';'));
  const blob = new Blob(['\ufeff' + linhas.join('\r\n')], {type:'text/csv;charset=utf-8;'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'pedidos_enviados.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(function(){ URL.revokeObjectURL(url); }, 1500);
}

function renderPedidos(){
  let rows = grupoRows().slice();
  const campo = ST.ped.campo || 'todos';
  const b = (ST.ped.busca || '').trim().toLowerCase();
  if (b) rows = rows.filter(r => String(valorCampoPed(r, campo)).toLowerCase().includes(b));

  const sc = ST.ped.sortCol;
  if (sc !== null && sc !== undefined){
    const mapa = {0:'coleta',1:'valor',2:'cep',3:'uf',4:'cidade',5:'peso',6:'cub',7:'vol',8:'transp',9:'sla',10:'emp'};
    const k = mapa[sc];
    const getter = (r)=>{
      if (k==='coleta'){ const p = String(r[9]).split('/'); return p.length===3 ? (p[2]+p[1]+p[0]) : '00000000'; }
      if (k==='valor') return r[7];
      if (k==='cep') return String(r[8]);
      if (k==='uf') return String(r[1]);
      if (k==='cidade') return String(r[2]);
      if (k==='peso') return r[6];
      if (k==='cub') return r[12]===null ? -1 : r[12];
      if (k==='vol') return r[5];
      if (k==='transp') return nomeTransp(r);
      if (k==='sla') return r[13]==='No prazo' ? 2 : (r[13]==='Atrasado' ? 1 : 0);
      return String(r[3]);
    };
    const dir = ST.ped.dir;
    rows.sort((a,b2)=>{
      const va = getter(a), vb = getter(b2);
      if (typeof va === 'string') return dir * (va < vb ? -1 : (va > vb ? 1 : 0));
      return dir * (va - vb);
    });
  }

  PED_VIEW = rows;

  const total = rows.length;
  const porPag = ST.ped.pageSize || 50;
  const paginas = Math.max(1, Math.ceil(total / porPag));
  if (ST.ped.page > paginas) ST.ped.page = paginas;
  if (ST.ped.page < 1) ST.ped.page = 1;
  const ini = (ST.ped.page - 1) * porPag;
  const pageRows = rows.slice(ini, ini + porPag);

  const nPrazo = rows.filter(r=>r[13]==='No prazo').length;
  const nAtraso = rows.filter(r=>r[13]==='Atrasado').length;
  const pctPrazo = rows.length ? nPrazo/rows.length*100 : 0;

  let h = '<div class="section"><h2>Pedidos Enviados</h2>';
  h += '<div class="filter-bar">';
  h += '<div class="filter-group"><label>Filtrar por</label><select id="pedCampo" onchange="setCampoPed()">';
  for (const [v,l] of PED_CAMPOS) h += '<option value="'+v+'"'+(campo===v?' selected':'')+'>'+l+'</option>';
  h += '</select></div>';
  h += '<div class="filter-group" style="flex:1"><label>Buscar</label>';
  h += '<input id="buscaPed" type="text" placeholder="Digite para filtrar..." value="'+esc(ST.ped.busca)+'" oninput="setBusca(this.value)" style="min-width:260px"></div>';
  h += '<button class="btn-filter" onclick="baixarCSV()">Baixar CSV</button>';
  h += '<div style="font-size:12px;color:#64748b;padding-bottom:8px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">'+nf(total)+' pedido(s)<span class="tag tag-baixo">No prazo: '+nf(nPrazo)+' ('+nf(pctPrazo,1)+'%)</span><span class="tag tag-alto">Atrasado: '+nf(nAtraso)+'</span></div>';
  h += '</div>';
  h += '<div class="table-wrap" style="max-height:640px;overflow-y:auto"><table id="tabelaPedidos" class="th-contrast"><thead><tr>';
  PED_COLS.forEach((c,i)=>{
    const cls = 'sortable' + (sc===i ? (ST.ped.dir===1 ? ' sorted-asc' : ' sorted-desc') : '');
    const ind = sc===i ? (ST.ped.dir===1 ? '▲' : '▼') : '▲▼';
    h += '<th class="'+cls+'" onclick="sortPed('+i+')">'+c+'<span class="sort-ind">'+ind+'</span></th>';
  });
  h += '</tr></thead><tbody>';
  for (const r of pageRows){
    const c = celulasPed(r);
    h += '<tr>';
    c.forEach((v,idx)=>{
      if (idx === 8) h += '<td>'+(r[4]===1?'<span class="tag tag-reg">Rodonaves</span>':'Outra transportadora')+'</td>';
      else if (idx === 9) h += '<td>'+(r[13]==='No prazo'?'<span class="tag tag-baixo">No prazo</span>':(r[13]==='Atrasado'?'<span class="tag tag-alto">Atrasado</span>':'<span class="tag tag-medio">—</span>'))+'</td>';
      else h += '<td>'+esc(v)+'</td>';
    });
    h += '</tr>';
  }
  if (!pageRows.length) h += '<tr><td colspan="11" style="text-align:center;color:#94a3b8;padding:20px">Nenhum pedido encontrado.</td></tr>';
  h += '</tbody></table></div>';

  h += '<div class="filter-bar" style="margin-top:12px;margin-bottom:0;justify-content:space-between;align-items:center">';
  h += '<div class="filter-group"><label>Por página</label><select id="pedPageSize" onchange="setPageSize()">';
  for (const n of [20,50,100]) h += '<option value="'+n+'"'+(porPag===n?' selected':'')+'>'+n+'</option>';
  h += '</select></div>';
  h += '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">';
  h += '<span style="font-size:12px;color:#64748b">'+nf(total?ini+1:0)+'–'+nf(ini+pageRows.length)+' de '+nf(total)+'</span>';
  h += '<button class="btn-clear" onclick="mudarPagina(-1)"'+(ST.ped.page<=1?' style="opacity:.45"':'')+'>‹ Anterior</button>';
  h += '<span style="font-size:12px;color:#475569;font-weight:700">Página '+nf(ST.ped.page)+' de '+nf(paginas)+'</span>';
  h += '<button class="btn-clear" onclick="mudarPagina(1)"'+(ST.ped.page>=paginas?' style="opacity:.45"':'')+'>Próxima ›</button>';
  h += '</div></div></div>';
  document.getElementById('pedidos').innerHTML = h;
}

function mudarPagina(d){
  ST.ped.page = (ST.ped.page || 1) + d;
  renderPedidos();
}

function setPageSize(){
  ST.ped.pageSize = parseInt(document.getElementById('pedPageSize').value, 10) || 50;
  ST.ped.page = 1;
  renderPedidos();
}

function sortPed(i){
  if (ST.ped.sortCol === i) ST.ped.dir *= -1;
  else { ST.ped.sortCol = i; ST.ped.dir = (i === 0 ? -1 : 1); }
  renderPedidos();
}

function setCampoPed(){
  ST.ped.campo = document.getElementById('pedCampo').value;
  ST.ped.page = 1;
  renderPedidos();
}

function setBusca(v){
  ST.ped.busca = v;
  ST.ped.page = 1;
  const el = document.getElementById('buscaPed');
  const pos = el ? el.selectionStart : 0;
  renderPedidos();
  const novo = document.getElementById('buscaPed');
  if (novo){ novo.focus(); novo.setSelectionRange(pos,pos); }
}

/* ---------------- Filtro global ---------------- */
function setGrupo(g){
  ST.grupo = g;
  ST.ped.page = 1;
  for (const b of document.querySelectorAll('#segTransp button')){
    b.classList.toggle('active', b.getAttribute('data-g') === g);
  }
  renderAll();
}

function renderAll(){
  renderKPIs();
  renderResumoMensal();
  renderConsolidado();
  renderEvolucao();
  renderPedidos();
}

function iniciar(){
  document.getElementById('cTodas').textContent = '(' + nf(PED.length) + ')';
  document.getElementById('cRod').textContent = '(' + nf(PED.filter(r=>r[4]===1).length) + ')';
  document.getElementById('cOutra').textContent = '(' + nf(PED.filter(r=>r[4]===0).length) + ')';
  renderAll();
  renderProgressao();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
else iniciar();
'''

html.append('<script>' + JS.replace('__PEDIDOS__', pedidos_json) + '</script>')
html.append('</body>\n</html>')

arq_html = f"{caminho_base}\\relatorio_volumetria_guimepa.html"
with open(arq_html, 'w', encoding='utf-8') as f:
    f.write('\n'.join(html))
print(f"HTML: {arq_html}")
print("CONCLUIDO")
