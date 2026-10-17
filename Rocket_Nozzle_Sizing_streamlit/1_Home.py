import streamlit as st
st.session_state.update(st.session_state)
for k, v in st.session_state.items():
    st.session_state[k] = v

from PIL import Image
import os
path = os.path.dirname(__file__)
my_file = path+'/pages/images/mechub_logo.png'
img = Image.open(my_file)

st.set_page_config(
    page_title='Rocket Nozzle Sizing',
    page_icon=img,
    layout="wide"
                   )

st.sidebar.image(img)
st.sidebar.markdown("[![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/@MecHub?sub_confirmation=1) [![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/GitMecHub)")

hide_menu = '''
        <style>
        #MainMenu {visibility: hidden; }
        footer {visibility: hidden;}
        </style>
        '''
st.markdown(hide_menu, unsafe_allow_html=True)

from rocketcea.cea_obj import add_new_fuel, add_new_oxidizer, add_new_propellant

from rocketcea.cea_obj_w_units import CEA_Obj

import numpy as np

import pandas as pd

import math

import io

import tempfile

import plotly.graph_objects as go


from stl import mesh

from plotly.subplots import make_subplots

import hashlib

import threading

import importlib.util

## Verifica se Gmsh está instalado. Ele é importado ao gerar a malha (biblioteca pesada)
gmsh_ok = importlib.util.find_spec('gmsh') is not None
gmsh_erro = '' if gmsh_ok else "No module named 'gmsh'"

st.title("Rocket Nozzle Sizing v1.2.0", anchor=False)

#SETUP

if 'active_page' not in st.session_state:
    st.session_state.active_page = '1_Home'
    st.session_state.p_3 = 101325.0
    st.session_state.p_1 = 3000000.0
    st.session_state.f = 1750.0
    st.session_state.method = 1
    st.session_state.spike_detail = 0
    st.session_state.f_name = 'Paraffin'
    st.session_state.o_name = 'N2O'
    st.session_state.of = 7.6
    st.session_state.nozzle_type = 'Conical'
    st.session_state.conv_on = False
    st.session_state.d_c = 0.0

## Pasta temporária (por sessão) para os arquivos CAD
if 'cad_dir' not in st.session_state:
    st.session_state['cad_dir'] = tempfile.mkdtemp()
cad_dir = st.session_state['cad_dir']

## Valores padrão do setup da malha
st.session_state.setdefault('mesh_L', 5.0)
st.session_state.setdefault('mesh_H', 1.5)
st.session_state.setdefault('mesh_wall', 'Wall functions')
st.session_state.setdefault('mesh_density', 'Medium')
st.session_state.setdefault('mesh_color', 'None')


###

# FUNCTIONS

###

# Last not null/empty list value
def last_valid(lst):
    return next((x for x in reversed(lst) if x and not math.isnan(x)), None) # or 'null'
#


# Plot do contorno da tubeira (Plotly)
def plotContour(curvas, pontos, title_):
    # curvas: lista de (nome, x, y, cor)
    # pontos: lista de (x, y, cor) -> pontos de início/fim de cada curva

    fig = go.Figure()

    for nome, x, y, cor in curvas:
        fig.add_trace(go.Scatter(
            x=x, y=y,
            mode='lines',
            name=nome,
            line=dict(color=cor, width=3),
            hovertemplate='x: %{x:.3f} mm<br>y: %{y:.3f} mm',
        ))

    fig.add_trace(go.Scatter(
        x=[p[0] for p in pontos], y=[p[1] for p in pontos],
        mode='markers',
        name='Start/End Points',
        marker=dict(color=[p[2] for p in pontos], size=10, line=dict(color='white', width=1.5)),
        hovertemplate='x: %{x:.3f} mm<br>y: %{y:.3f} mm',
    ))

    ## Eixo de simetria
    fig.add_hline(y=0, line_dash='dashdot', line_color='gray', line_width=1.5)

    fig.update_layout(
        title=dict(text=title_),
        xaxis=dict(title=dict(text='x (mm)'), showgrid=True),
        yaxis=dict(title=dict(text='y (mm)'), showgrid=True, scaleanchor='x', scaleratio=1),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(l=0, r=0, t=80, b=0),
        height=480,
    )
    st.plotly_chart(fig)
#


#   Display CAD
def displayCAD(partes, title_):
    # partes: lista de (nome, arquivo .stl)
    traces = []
    for nome, file_ in partes:
        # Carregar o arquivo STL
        stl_mesh = mesh.Mesh.from_file(file_)

        # Extrair todos os vértices da malha (cada face tem 3 vértices de 3 coordenadas [x, y, z])
        # stl_mesh.vectors tem o formato (N_triangulos, 3, 3)
        vertices = stl_mesh.vectors.reshape(-1, 3)

        # Identificar vértices únicos e reorganizar os índices das faces
        unique_vertices, indices = np.unique(vertices, axis=0, return_inverse=True)

        # Separar coordenadas x, y, z dos vértices únicos
        x, y, z = unique_vertices.T

        # As faces são formadas por trios sequenciais de índices
        faces = indices.reshape(-1, 3)

        traces.append(go.Mesh3d(
            x=x, y=y, z=z,
            i=faces[:, 0], j=faces[:, 1], k=faces[:, 2],
            color='lightblue',
            name=nome,
            opacity=1,
            flatshading=False,  # sombreamento suave (melhor para superfícies de revolução)
            lighting=dict(ambient=0.45, diffuse=0.8, specular=0.15, roughness=0.6),
            lightposition=dict(x=1000, y=2000, z=3000),
            hoverinfo='name',
        ))

    fig = go.Figure(traces)

    eixo = dict(showbackground=False)
    fig.update_layout(
        title=dict(text=title_),
        scene=dict(aspectmode="data", bgcolor="rgba(0,0,0,0)", xaxis=eixo, yaxis=eixo, zaxis=eixo),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        margin=dict(l=0, r=0, t=80, b=0),
        height=480,
    )
    st.plotly_chart(fig)
#


# Convergente do spike
def spikeConvergent(x1s, y1s, x2s, y2s, R_c=0, theta_conv=45):
    S = np.array([x1s[0], y1s[0]])                          # início da Curve 1 (garganta, lado do plug)
    P2 = np.array([x2s[0], y2s[0]])                         # início da Curve 2 (carenagem)
    L = np.array([x2s[-1], y2s[-1]])                        # lábio
    w = float(np.linalg.norm(L - S))                        # largura da garganta
    r_haste = 0.25 * L[1]                                   # raio do eixo central
    phi_s = math.atan2(y1s[1] - y1s[0], x1s[1] - x1s[0])     # ângulo do início da Curve 1
    phi_c = math.radians(theta_conv)                        # cone do plug (45°)

    ## Arco de concordância (raio 0,5 x largura da garganta): do cone (45°) até o início da Curve 1
    r_a = 0.5 * w
    C = S + r_a * np.array([math.sin(phi_s), -math.cos(phi_s)])                       # centro (curva para a direita)
    b_f = math.atan2(S[1] - C[1], S[0] - C[0])
    b = np.linspace(b_f - (phi_s - phi_c), b_f, 20)
    arco = np.c_[C[0] + r_a * np.cos(b), C[1] + r_a * np.sin(b)]
    A = arco[0]

    ## Cone de 45° do plug até o raio do eixo central e trecho reto curto antes dele
    B = np.array([A[0] - (A[1] - r_haste) / math.tan(phi_c), r_haste])
    x_c = B[0] - 0.25 * (P2[1] - r_haste)                   # início do convergente
    plug = [np.array([[x_c, r_haste], B]), np.array([B, A]), arco]
    carenagem = [np.array([[x_c, P2[1]], P2])]              # carenagem reta (azul)

    ## Extensão até a câmara (Curve 0)
    plug_0, carenagem_0, D_min = None, None, 2 * P2[1]
    if R_c > 0:
        if R_c > P2[1] + 0.05 * w:
            x_1 = x_c - (R_c - P2[1]) / math.tan(phi_c)      # fim do trecho reto da câmara
            x_0 = x_1 - 0.25 * (R_c - r_haste)               # entrada (câmara)
            carenagem_0 = [np.array([[x_0, R_c], [x_1, R_c]]), np.array([[x_1, R_c], [x_c, P2[1]]])]
            plug_0 = [np.array([[x_0, r_haste], [x_c, r_haste]])]
    return carenagem, plug, carenagem_0, plug_0, r_haste, D_min
#

def cowlOuter(vertices, espessura):
    V = np.asarray(vertices, dtype=float)
    t = np.diff(V, axis=0)
    t = t / np.linalg.norm(t, axis=1)[:, None]
    n = np.c_[-t[:, 1], t[:, 0]]    # normal para fora do escoamento
    P = V[:-1] + espessura * n  # um ponto de cada reta deslocada
    ext = [P[0]]
    for i in range(1, len(t)):
        M = np.array([t[i - 1], -t[i]]).T
        if abs(np.linalg.det(M)) < 1e-9:# trechos alinhados
            ext.append(P[i]); continue
        s = np.linalg.solve(M, P[i] - P[i - 1])
        ext.append(P[i - 1] + s[0] * t[i - 1])
    x_L = V[-1, 0]
    ext.append(P[-1] + (x_L - P[-1, 0]) / t[-1, 0] * t[-1])  # último trecho até o plano do lábio
    ext = np.array(ext)
    if abs(t[0, 0]) > 1e-9 and abs(t[0, 1]) > 1e-9:          # primeiro trecho inclinado: corta no plano da entrada
        ext[0] = P[0] + (V[0, 0] - P[0, 0]) / t[0, 0] * t[0]
    for i in range(1, len(ext)):                             # corta onde a parede externa chega ao plano do lábio (face do lábio)
        if ext[i, 0] >= x_L - 1e-9:
            f = (x_L - ext[i - 1, 0]) / (ext[i, 0] - ext[i - 1, 0])
            ext = np.vstack([ext[:i], ext[i - 1] + f * (ext[i] - ext[i - 1])])
            break
    return ext[::-1]
#


# Razão de progressão geométrica para que a primeira célula tenha altura h1 (L = h1 * (r**n - 1) / (r - 1))
def solveProgression(L, h1, n):
    if h1 * n >= L:
        return 1.0
    lo, hi = 1.0 + 1e-12, 10.0
    for _ in range(200):
        r = 0.5 * (lo + hi)
        if h1 * (r ** n - 1) / (r - 1) > L:
            hi = r
        else:
            lo = r
    return 0.5 * (lo + hi)
#


# Número de células para ir de h1 até cobrir L com razão de crescimento máxima r_max
def cellsProgression(L, h1, r_max):
    if h1 >= L:
        return 1
    return int(math.ceil(math.log(1 + L * (r_max - 1) / h1) / math.log(r_max)))
#


# Número de Mach a partir da razão de áreas (isentrópico), por bisseção
def machFromArea(razao, gamma, supersonico):
    razao = np.atleast_1d(np.asarray(razao, dtype=float))
    sup = np.broadcast_to(np.asarray(supersonico), razao.shape)
    f = lambda M: (1 / M) * ((2 / (gamma + 1)) * (1 + (gamma - 1) / 2 * M ** 2)) ** ((gamma + 1) / (2 * (gamma - 1)))
    lo = np.where(sup, 1.0, 1e-6)
    hi = np.where(sup, 50.0, 1.0)
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        maior = f(mid) > razao
        # subsônico: A/At diminui com M | supersônico: A/At aumenta com M
        lo = np.where(sup, np.where(maior, lo, mid), np.where(maior, mid, lo))
        hi = np.where(sup, np.where(maior, mid, hi), np.where(maior, hi, mid))
    return 0.5 * (lo + hi)
#


# y+ estimado ao longo da parede (escoamento isentrópico + correlação de placa plana, mu ~ T^0.7)
def wallYplus(curvas, gamma, R_gas, T_0, P_0, mu_t, h1):
    pts = np.vstack(curvas)
    pts = pts[np.r_[True, np.linalg.norm(np.diff(pts, axis=0), axis=1) > 1e-9]]   # remove pontos repetidos nas junções
    x, R = pts[:, 0], pts[:, 1]
    R_t = R.min()
    x_t = x[np.argmin(R)]
    M = machFromArea((R / R_t) ** 2, gamma, x > x_t)
    T = T_0 / (1 + (gamma - 1) / 2 * M ** 2)
    p = P_0 * (T / T_0) ** (gamma / (gamma - 1))
    rho = p / (R_gas * T)
    U = M * (gamma * R_gas * T) ** 0.5
    mu = mu_t * (T / (T_0 * 2 / (gamma + 1))) ** 0.7
    Re = rho * U * 2 * R / mu
    Cf = 0.058 * Re ** -0.2                         # placa plana turbulenta (mesma correlação do relatório)
    u_tau = U * (Cf / 2) ** 0.5
    inclinacao = np.gradient(R, x)
    h_normal = h1 / np.sqrt(1 + inclinacao ** 2)    # altura vertical da célula -> normal à parede
    return x, h_normal * rho * u_tau / mu
#


# Altura (vertical) da primeira célula para o tratamento de parede escolhido
def firstCellHeight(curvas, gamma, R_gas, T_0, P_0, mu_t, parede_resolvida):
    x, y_un = wallYplus(curvas, gamma, R_gas, T_0, P_0, mu_t, 1.0)   # y+ por metro de altura da célula
    pts = np.vstack(curvas)
    x_t = pts[np.argmin(pts[:, 1]), 0]
    if parede_resolvida:
        return 0.5 / y_un.max()                     # y+ <= 0,5 em toda a parede (margem como no relatório)
    h1 = 35 / y_un[x >= x_t].min()                  # y+ >= 35 da garganta até a saída
    return min(h1, 300 / y_un.max())                # sem passar de y+ = 300
#


# y+ estimado nas paredes do spike: entrada (subsônica, razão de áreas local) e spike (Mach do projeto)
# Comprimento de referência: diâmetro hidráulico local do anel (2 x folga entre as paredes; no spike, 2 x largura da garganta)
# carenagem: parede interna da carenagem (Curve 0 se houver + Curve 2); bojo: corpo central (Curve 0 do corpo) ou None
def spikeYplus(spike_pts, mach_spike, carenagem, bojo, gamma, R_gas, T_0, P_0, mu_t, h1):
    L, S = carenagem[-1], spike_pts[0]
    w = float(np.linalg.norm(L - S))
    A_t = math.pi * (L[1] + S[1]) * w                        # área da garganta (anel cônico)

    ## Reamostra as paredes da entrada pelo comprimento de arco (pontos igualmente espaçados)
    def reamostrar(P, n=80):
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
        si = np.linspace(0, s[-1], n)
        return np.c_[np.interp(si, s, P[:, 0]), np.interp(si, s, P[:, 1])]
    car = reamostrar(carenagem)
    boj = reamostrar(bojo) if bojo is not None else S[None, :]

    ## Área local: folga até a outra parede x raio médio (anel)
    def entrada(P, Q):
        D = np.linalg.norm(P[:, None, :] - Q[None, :, :], axis=2)
        j, g = D.argmin(axis=1), D.min(axis=1)
        razao = np.maximum(math.pi * (P[:, 1] + Q[j, 1]) * g / A_t, 1.0)
        return machFromArea(razao, gamma, False), 2 * g
    M_c, Dh_c = entrada(car, boj)
    if bojo is None:                                         # sem convergente: só a Curve 2 antes da garganta
        boj, M_b, Dh_b = np.empty((0, 2)), np.empty(0), np.empty(0)
    else:
        M_b, Dh_b = entrada(boj, car)

    ## Carenagem | NaN (quebra) | corpo central + spike
    x = np.r_[car[:, 0], np.nan, boj[:, 0], spike_pts[1:, 0]]
    M = np.r_[M_c, np.nan, M_b, mach_spike[1:]]
    Dh = np.r_[Dh_c, np.nan, Dh_b, np.full(len(spike_pts) - 1, 2 * w)]
    supersonico = np.r_[np.zeros(len(car) + 1 + len(boj), dtype=bool), np.ones(len(spike_pts) - 1, dtype=bool)]

    T = T_0 / (1 + (gamma - 1) / 2 * M ** 2)
    p = P_0 * (T / T_0) ** (gamma / (gamma - 1))
    rho = p / (R_gas * T)
    U = M * (gamma * R_gas * T) ** 0.5
    mu = mu_t * (T / (T_0 * 2 / (gamma + 1))) ** 0.7
    Re = rho * U * Dh / mu
    Cf = 0.058 * Re ** -0.2                         # placa plana turbulenta (mesma correlação do relatório)
    u_tau = U * (Cf / 2) ** 0.5
    return x, h1 * rho * u_tau / mu, supersonico            # h1 já é normal à parede (camada-limite do gmsh)
#


# Malha 2D axissimétrica estruturada (quads) da tubeira + região de saída (gmsh)
def generateMesh(curvas, L_out, H_out, dx, h1, r_max, r_max_out, file_base):
    # curvas: lista de arrays (N, 2) com os pontos (x, y) de cada curva da parede, em metros, na ordem do escoamento
    # L_out, H_out: comprimento e altura (a partir do eixo) da região de saída (m)
    # dx: tamanho axial das células na tubeira (m)
    # h1: altura da primeira célula na parede (m); r_max: razão máxima de crescimento das células
    # r_max_out: razão máxima de crescimento axial na região de saída
    #
    # Blocos: faixa de camada-limite de espessura constante (delta) colada à parede + núcleo até o eixo,
    # e na saída: continuação da faixa (camada de cisalhamento), núcleo e bloco superior (até H_out).

    try:
        with st.spinner('Loading gmsh...'): # gmsh importado só aqui (biblioteca pesada)
            import gmsh
    except Exception as e:
        raise RuntimeError(f"Gmsh could not be loaded: {e}. On Linux (e.g. Streamlit Cloud) it needs the system libraries listed in packages.txt "
                           "(libglu1-mesa, libxcursor1, libxinerama1, libxft2).")

    gmsh.initialize(interruptible=False)
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("nozzle")
    geo = gmsh.model.geo

    juncoes = [c[0] for c in curvas] + [curvas[-1][-1]] # pontos de junção na parede
    R_t = min(float(np.min(c[:, 1])) for c in curvas)   # raio da garganta
    R_max = max(float(np.max(c[:, 1])) for c in curvas)
    x_e, R_e = juncoes[-1]  # saída da tubeira

    # Camada-limite: n_bl células de h1 até delta (mesma distribuição em todas as colunas -> camadas paralelas à parede)
    delta = 0.25 * R_t
    n_bl = cellsProgression(delta, h1, r_max)
    r_bl = solveProgression(delta, h1, n_bl)
    h_ult = h1 * r_bl ** (n_bl - 1)                           # altura da última célula da camada-limite

    # Núcleo: começa com h_ult * r_max e vai até o eixo
    n_core = max(cellsProgression(R_max - delta, h_ult * r_max, r_max), int(math.ceil((R_t - delta) / dx)))

    # Pontos: parede (J), limite da camada-limite (K) e eixo (Q)
    p_J = [geo.addPoint(x, y, 0) for x, y in juncoes]
    p_K = [geo.addPoint(x, y - delta, 0) for x, y in juncoes]
    p_Q = [geo.addPoint(x, 0, 0) for x, y in juncoes]

    lados_bl = [geo.addLine(p_J[i], p_K[i]) for i in range(len(juncoes))]    # da parede para dentro
    lados_core = [geo.addLine(p_K[i], p_Q[i]) for i in range(len(juncoes))]  # da camada-limite ao eixo

    paredes, internas, eixos, sup_bl, sup_core, n_axial = [], [], [], [], [], []
    for i, c in enumerate(curvas):
        pts_w = [geo.addPoint(x, y, 0) for x, y in c[1:-1]]
        pts_k = [geo.addPoint(x, y - delta, 0) for x, y in c[1:-1]]
        paredes.append(geo.addSpline([p_J[i]] + pts_w + [p_J[i + 1]]))
        internas.append(geo.addSpline([p_K[i]] + pts_k + [p_K[i + 1]]))
        eixos.append(geo.addLine(p_Q[i], p_Q[i + 1]))
        n_axial.append(max(1, int(round((juncoes[i + 1][0] - juncoes[i][0]) / dx))))
        loop = geo.addCurveLoop([internas[i], -lados_bl[i + 1], -paredes[i], lados_bl[i]])
        sup_bl.append(geo.addPlaneSurface([loop]))
        loop = geo.addCurveLoop([eixos[i], -lados_core[i + 1], -internas[i], lados_core[i]])
        sup_core.append(geo.addPlaneSurface([loop]))

    # Região de saída
    x_f = x_e + L_out
    p_E0 = geo.addPoint(x_f, 0, 0)
    p_E1 = geo.addPoint(x_f, R_e - delta, 0)
    p_E2 = geo.addPoint(x_f, R_e, 0)
    p_E3 = geo.addPoint(x_f, H_out, 0)
    p_T = geo.addPoint(x_e, H_out, 0)

    eixo_saida = geo.addLine(p_Q[-1], p_E0)
    interna_saida = geo.addLine(p_K[-1], p_E1)
    cisalhamento = geo.addLine(p_J[-1], p_E2)
    topo = geo.addLine(p_T, p_E3)
    saida_core = geo.addLine(p_E1, p_E0)
    saida_bl = geo.addLine(p_E2, p_E1)
    saida_sup = geo.addLine(p_E2, p_E3)
    lateral = geo.addLine(p_J[-1], p_T)                       # plano de saída acima do lábio

    loop = geo.addCurveLoop([eixo_saida, -saida_core, -interna_saida, lados_core[-1]])
    s_core = geo.addPlaneSurface([loop])
    loop = geo.addCurveLoop([interna_saida, -saida_bl, -cisalhamento, lados_bl[-1]])
    s_bl = geo.addPlaneSurface([loop])
    loop = geo.addCurveLoop([cisalhamento, saida_sup, -topo, -lateral])
    s_sup = geo.addPlaneSurface([loop])

    geo.synchronize()
    malha = gmsh.model.mesh

    # Distribuições transfinitas
    for c in lados_bl + [saida_bl]:
        malha.setTransfiniteCurve(c, n_bl + 1, "Progression", r_bl)
    for i, c in enumerate(lados_core):
        malha.setTransfiniteCurve(c, n_core + 1, "Progression", solveProgression(juncoes[i][1] - delta, h_ult * r_max, n_core))
    malha.setTransfiniteCurve(saida_core, n_core + 1, "Progression", solveProgression(R_e - delta, h_ult * r_max, n_core))

    n_sup = cellsProgression(H_out - R_e, h1, r_max)          # bloco superior começa com h1 (camada de cisalhamento)
    r_sup = solveProgression(H_out - R_e, h1, n_sup)
    for c in [saida_sup, lateral]:
        malha.setTransfiniteCurve(c, n_sup + 1, "Progression", r_sup)

    for i in range(len(curvas)):
        for c in [paredes[i], internas[i], eixos[i]]:
            malha.setTransfiniteCurve(c, n_axial[i] + 1)
    n_out = cellsProgression(L_out, dx, r_max_out)
    r_out = solveProgression(L_out, dx, n_out)
    for c in [eixo_saida, interna_saida, cisalhamento, topo]:
        malha.setTransfiniteCurve(c, n_out + 1, "Progression", r_out)

    superficies = sup_bl + sup_core + [s_core, s_bl, s_sup]
    for s in superficies:
        malha.setTransfiniteSurface(s)
        malha.setRecombine(2, s)

    # Grupos físicos (nomes das condições de contorno)
    gmsh.model.addPhysicalGroup(1, [lados_bl[0], lados_core[0]], name="inlet")
    gmsh.model.addPhysicalGroup(1, paredes, name="wall")
    gmsh.model.addPhysicalGroup(1, eixos + [eixo_saida], name="axis")
    gmsh.model.addPhysicalGroup(1, [saida_core, saida_bl, saida_sup], name="outlet")
    gmsh.model.addPhysicalGroup(1, [topo, lateral], name="farfield")
    gmsh.model.addPhysicalGroup(2, superficies, name="fluid")

    malha.generate(2)

    # Nós e quadriláteros
    tags, coords, _ = malha.getNodes()
    nos = coords.reshape(-1, 3)[:, :2]
    indice = np.zeros(int(tags.max()) + 1, dtype=np.int64)
    indice[tags.astype(np.int64)] = np.arange(len(tags))
    quad_tags, quad_nos = malha.getElementsByType(3)
    quads = indice[quad_nos.astype(np.int64)].reshape(-1, 4)
    rho = malha.getElementQualities(quad_tags, "minSJ")      # Scaled Jacobian (Rho)

    # Arestas de contorno por grupo físico
    contornos = {}
    for dim, tag in gmsh.model.getPhysicalGroups(1):
        nome = gmsh.model.getPhysicalName(dim, tag)
        segs = []
        for ent in gmsh.model.getEntitiesForPhysicalGroup(dim, tag):
            _, enos = malha.getElementsByType(1, ent)
            segs.append(indice[enos.astype(np.int64)].reshape(-1, 2))
        contornos[nome] = np.vstack(segs)

    # Exportar (em metros)
    arquivos = {}
    for ext in ["msh", "su2", "unv", "cgns"]:
        gmsh.write(file_base + "." + ext)
        with open(file_base + "." + ext, "rb") as arq:
            arquivos[ext] = arq.read()

    gmsh.finalize()

    return {"nos": nos, "quads": quads, "rho": rho, "contornos": contornos, "arquivos": arquivos,
            "h1": h1, "delta": delta, "n_bl": n_bl, "r_bl": r_bl, "n_core": n_core, "n_sup": n_sup,
            "r_sup": r_sup, "n_out": n_out, "r_out": r_out, "dx": dx, "L_out": L_out, "H_out": H_out}
#


# Malha 2D axissimétrica híbrida do spike: camada-limite estruturada (quads) nas paredes + triângulos (gmsh)
def generateSpikeMesh(spike_pts, carenagem, carenagem_ext, plug, L_out, H_out, dx, dx_ch, h1, r_max, file_base):
    # spike_pts: array (N, 2) do contorno do spike (Curve 1), em metros, da garganta até a ponta
    # carenagem: trechos da parede interna da carenagem (Curve 0 se houver + convergente + Curve 2), da entrada até o lábio (m)
    # carenagem_ext: vértices da parede externa da carenagem, do topo da face do lábio até a entrada (m)
    # plug: trechos do corpo central (Curve 0 se houver + convergente), da entrada até o início do spike (m)
    # (cada trecho é um array (n, 2): 2 pontos = reta, mais pontos = spline)
    # L_out: comprimento da região de saída após a ponta do spike; H_out: altura do domínio a partir do eixo (m)
    # dx: tamanho das células no spike e na pluma (m); dx_ch: tamanho das células no canal e na garganta (m)
    # h1: altura da primeira célula na parede (m); r_max: razão de crescimento da camada-limite

    try:
        with st.spinner('Loading gmsh...'):  # gmsh importado só aqui (biblioteca pesada)
            import gmsh
        import gmsh   # importado só aqui (biblioteca pesada)
    except Exception as e:
        raise RuntimeError(f"Gmsh could not be loaded: {e}. On Linux (e.g. Streamlit Cloud) it needs the system libraries listed in packages.txt "
                           "(libglu1-mesa, libxcursor1, libxinerama1, libxft2).")

    L = np.asarray(carenagem[-1][-1], dtype=float)           # lábio da carenagem

    # Ponta que encosta no eixo forma uma cúspide (células degeneradas): trunca onde o raio < 1% do raio do lábio (base plana)
    spike_pts = np.asarray(spike_pts, dtype=float)
    if spike_pts[-1, 1] < 0.01 * L[1]:
        k = int(np.argmax(spike_pts[:, 1] < 0.01 * L[1]))
        spike_pts = spike_pts[:max(k, 3)]

    S = spike_pts[0]                                         # início do spike (garganta, lado interno)
    E = spike_pts[-1]                                        # fim do spike
    w = float(np.linalg.norm(L - S))                         # largura da garganta
    I_o = np.asarray(carenagem[0][0], dtype=float)           # entrada: lado da carenagem
    I_i = np.asarray(plug[0][0], dtype=float)                # entrada: lado do corpo central
    razao_entrada = (I_o[1] + I_i[1]) * float(np.linalg.norm(I_o - I_i)) / ((L[1] + S[1]) * w)   # área da entrada / área da garganta (anéis cônicos)
    L_top = np.asarray(carenagem_ext[0], dtype=float)        # topo da face do lábio
    C_top = np.asarray(carenagem_ext[-1], dtype=float)       # fim da parede externa (na entrada)
    H_out = max(H_out, 1.3 * float(np.max(carenagem_ext[:, 1])))   # domínio acima da carenagem

    x_out = E[0] + L_out

    ## Camada-limite estruturada (quads): cresce de h1 até a última camada chegar a ~dx_ch / 2,5, sem passar de 30% da garganta
    n_bl = 3
    while h1 * r_max ** n_bl < dx_ch / 2.5 and h1 * (r_max ** (n_bl + 1) - 1) / (r_max - 1) <= 0.3 * w:
        n_bl += 1
    delta = h1 * (r_max ** n_bl - 1) / (r_max - 1)
    h_ult = h1 * r_max ** (n_bl - 1)                         # altura da última camada
    dx_w = min(dx_ch, 2.5 * h_ult)                           # triângulos junto à camada-limite (mesma área do último quad)
    ## Geração (se o gmsh não conseguir montar a camada-limite, tenta de novo com uma camada a menos)
    for fator in (1.0, 0.9, 0.8):
        gmsh.initialize(interruptible=False)
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("spike")
        geo = gmsh.model.geo

        p = lambda P: geo.addPoint(float(P[0]), float(P[1]), 0)
        pL, pS, pE = p(L), p(S), p(E)
        pI_o, pI_i, pLt, pCt = p(I_o), p(I_i), p(L_top), p(C_top)
        pLat = p((C_top[0], H_out))
        pTop = p((x_out, H_out))
        pOut = p((x_out, 0))
        tem_base = E[1] > 1e-9                                   # spike truncado: base plana até o eixo
        pAx = p((E[0], 0)) if tem_base else pE

        ## Contorno (sentido único)
        ## Trechos: reta (2 pontos) ou spline, ligando os pontos já criados nas extremidades
        ## Cantos convexos para o escoamento (contorno no sentido horário: curva para a esquerda > 40°) recebem leque na camada-limite
        cantos_convexos = []
        def trechos(pecas, p_ini, p_fim, inverter=False, leques=True):
            if inverter:
                pecas = [q[::-1] for q in pecas[::-1]]
            tags = [p_ini] + [p(q[-1]) for q in pecas[:-1]] + [p_fim]
            for i in range(1, len(pecas)):
                t1, t2 = pecas[i - 1][-1] - pecas[i - 1][-2], pecas[i][1] - pecas[i][0]
                giro = math.degrees(math.atan2(t1[0] * t2[1] - t1[1] * t2[0], t1[0] * t2[0] + t1[1] * t2[1]))
                if giro > 40 and leques:
                    cantos_convexos.append(tags[i])
            return [geo.addLine(tags[i], tags[i + 1]) if len(q) == 2 else geo.addSpline([tags[i]] + [p(P) for P in q[1:-1]] + [tags[i + 1]])
                    for i, q in enumerate(pecas)]

        entrada = geo.addLine(pI_i, pI_o)   # entrada: anel entre o corpo central e a carenagem
        parede_ext = trechos(carenagem, pI_o, pL)   # carenagem (lado de dentro) até o lábio
        labio = geo.addLine(pL, pLt)    # face do lábio
        externa = trechos([carenagem_ext[i:i + 2] for i in range(len(carenagem_ext) - 1)], pLt, pCt, leques=False)   # carenagem (lado de fora) até a entrada
        lateral = geo.addLine(pCt, pLat)    # plano da entrada acima da carenagem (ambiente)
        topo = geo.addLine(pLat, pTop)
        saida = geo.addLine(pTop, pOut)
        eixo = geo.addLine(pOut, pAx)
        base = geo.addLine(pAx, pE) if tem_base else None
        internos = [p(P) for P in spike_pts[-2:0:-1]]
        spike = geo.addSpline([pE] + internos + [pS])   # do fim para o início (sentido do contorno)
        parede_int = trechos(plug, pS, pI_i, inverter=True) # corpo central (da garganta para trás)

        curvas = [entrada] + parede_ext + [labio] + externa + [lateral, topo, saida, eixo] + ([base] if tem_base else []) + [spike] + parede_int
        loop = geo.addCurveLoop(curvas)
        sup = geo.addPlaneSurface([loop])
        geo.synchronize()

        paredes = parede_ext + [labio] + externa + [spike] + parede_int + ([base] if tem_base else [])

        campo = gmsh.model.mesh.field
        bl = campo.add("BoundaryLayer")
        ### Lateral com camada-limite só quando a parede externa chega inclinada (sem convergente): evita célula ruim no canto
        t_ext = carenagem_ext[-1] - carenagem_ext[-2]
        bl_lateral = abs(t_ext[1]) > 0.2 * abs(t_ext[0])
        campo.setNumbers(bl, "CurvesList", paredes + ([lateral] if bl_lateral else []))
        campo.setNumber(bl, "Size", h1)
        campo.setNumber(bl, "Ratio", r_max)
        campo.setNumber(bl, "Thickness", (delta - 0.5 * h1 * r_max ** (n_bl - 1)) * fator)   # meio da última camada: mesmo nº de camadas em todos os nós
        campo.setNumber(bl, "Quads", 1)
        campo.setNumbers(bl, "PointsList", [pI_i, pI_o, pLat if bl_lateral else pCt] + ([pAx] if tem_base else []))
        t_lt = carenagem_ext[1] - carenagem_ext[0]               # topo do lábio: leque se a parede externa girar mais de 60° em relação à face do lábio
        leque_topo = math.degrees(math.atan2(-t_lt[0], t_lt[1])) > 60
        campo.setNumbers(bl, "FanPointsList", [pL] + ([pLt] if leque_topo else []) + cantos_convexos)   # leque de células nos cantos vivos
        campo.setAsBoundaryLayer(bl)

        ## Tamanhos: dx_w junto às paredes e na garganta, 2 dx na pluma, crescendo até 8 dx no far field
        ## (crescimento suave: o tamanho aumenta no máximo ~10% da distância percorrida -> growth rate baixo nos triângulos)
        inclinacao = 0.1
        dist_ch = campo.add("Distance")
        campo.setNumbers(dist_ch, "CurvesList", parede_ext + parede_int)
        campo.setNumbers(dist_ch, "PointsList", [pL, pS])
        campo.setNumber(dist_ch, "Sampling", 200)
        th_ch = campo.add("Threshold")
        campo.setNumber(th_ch, "InField", dist_ch)
        campo.setNumber(th_ch, "SizeMin", dx_w)
        campo.setNumber(th_ch, "SizeMax", 8 * dx)
        campo.setNumber(th_ch, "DistMin", 1.5 * w)
        campo.setNumber(th_ch, "DistMax", 1.5 * w + (8 * dx - dx_w) / inclinacao)

        dist = campo.add("Distance")
        campo.setNumbers(dist, "CurvesList", [spike, labio, lateral] + externa + ([base] if tem_base else []))
        campo.setNumber(dist, "Sampling", 400)
        th = campo.add("Threshold")
        campo.setNumber(th, "InField", dist)
        campo.setNumber(th, "SizeMin", dx_w)
        campo.setNumber(th, "SizeMax", 8 * dx)
        campo.setNumber(th, "DistMin", delta)
        campo.setNumber(th, "DistMax", delta + (8 * dx - dx_w) / inclinacao)

        pluma = campo.add("Box")                                  # pluma (jato) até a saída
        campo.setNumber(pluma, "VIn", 2 * dx)
        campo.setNumber(pluma, "VOut", 8 * dx)
        campo.setNumber(pluma, "XMin", L[0])
        campo.setNumber(pluma, "XMax", x_out)
        campo.setNumber(pluma, "YMin", 0)
        campo.setNumber(pluma, "YMax", 1.3 * L[1])
        campo.setNumber(pluma, "Thickness", 6 * dx / inclinacao)

        minimo = campo.add("Min")
        campo.setNumbers(minimo, "FieldsList", [th_ch, th, pluma])
        campo.setAsBackgroundMesh(minimo)
        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
        gmsh.option.setNumber("Mesh.Algorithm", 6)               # Frontal-Delaunay
        gmsh.option.setNumber("Mesh.MeshSizeMin", h1)
        gmsh.option.setNumber("Mesh.BoundaryLayerFanElements", 3)   # leque do lábio: 3 elementos

        # Grupos físicos (nomes das condições de contorno)
        gmsh.model.addPhysicalGroup(1, [entrada], name="inlet")
        gmsh.model.addPhysicalGroup(1, paredes, name="wall")
        gmsh.model.addPhysicalGroup(1, [eixo], name="axis")
        gmsh.model.addPhysicalGroup(1, [saida], name="outlet")
        gmsh.model.addPhysicalGroup(1, [topo], name="farfield")
        gmsh.model.addPhysicalGroup(1, [lateral], name="lateral")
        gmsh.model.addPhysicalGroup(2, [sup], name="fluid")

        malha = gmsh.model.mesh
        try:
            malha.generate(2)
            break
        except Exception:
            gmsh.finalize()
            if fator == 0.8:
                raise
    n_bl = int(math.floor(math.log(1 + (delta - 0.5 * h_ult) * fator * (r_max - 1) / h1) / math.log(r_max))) + 1   # camadas geradas
    delta = h1 * (r_max ** n_bl - 1) / (r_max - 1)

    # Nós, quadriláteros (camada-limite) e triângulos
    tags, coords, _ = malha.getNodes()
    nos = coords.reshape(-1, 3)[:, :2]
    indice = np.zeros(int(tags.max()) + 1, dtype=np.int64)
    indice[tags.astype(np.int64)] = np.arange(len(tags))
    quad_tags, quad_nos = malha.getElementsByType(3)
    quads = indice[quad_nos.astype(np.int64)].reshape(-1, 4)
    tri_tags, tri_nos = malha.getElementsByType(2)
    tris = indice[tri_nos.astype(np.int64)].reshape(-1, 3)
    rho = malha.getElementQualities(quad_tags, "minSJ")      # Scaled Jacobian (Rho) dos quads
    sicn = malha.getElementQualities(tri_tags, "minSICN")    # SICN dos triângulos
    gamma_q = malha.getElementQualities(tri_tags, "gamma")   # Gamma (inscrito/circunscrito) dos triângulos

    # Arestas de contorno por grupo físico
    contornos = {}
    for dim, tag in gmsh.model.getPhysicalGroups(1):
        nome = gmsh.model.getPhysicalName(dim, tag)
        segs = []
        for ent in gmsh.model.getEntitiesForPhysicalGroup(dim, tag):
            _, enos = malha.getElementsByType(1, ent)
            segs.append(indice[enos.astype(np.int64)].reshape(-1, 2))
        contornos[nome] = np.vstack(segs)

    # Exportar (em metros)
    arquivos = {}
    for ext in ["msh", "su2", "unv", "cgns"]:
        gmsh.write(file_base + "." + ext)
        with open(file_base + "." + ext, "rb") as arq:
            arquivos[ext] = arq.read()

    gmsh.finalize()

    return {"nos": nos, "quads": quads, "tris": tris, "rho": rho, "sicn": sicn, "gamma": gamma_q,
            "contornos": contornos, "arquivos": arquivos, "spike": spike_pts,
            "h1": h1, "delta": delta, "n_bl": n_bl, "r_bl": r_max, "dx": dx, "dx_ch": dx_w,
            "w": w, "R_in": I_o[1], "r_in": I_i[1], "razao_entrada": razao_entrada,
            "L_out": L_out, "H_out": H_out}
#


# Métricas de qualidade da malha 2D (quads e, na malha híbrida do spike, triângulos)
def meshQuality(nos, quads, tris=None):
    # Células na ordem: quads, depois triângulos (ângulo ideal: 90° nos quads, 60° nos triângulos)
    grupos = [(c, ang_eq) for c, ang_eq in [(quads, 90.0), (tris, 60.0)] if c is not None and len(c)]
    areas, centros, sinais, skews, aspects = [], [], [], [], []
    for cel, ang_eq in grupos:
        P = nos[cel]                                     # (M, n, 2)
        P0 = P[:, :1, :]                                 # coordenadas locais (evita perda de precisão em células muito finas)
        x, y = (P - P0)[..., 0], (P - P0)[..., 1]
        xs, ys = np.roll(x, -1, axis=1), np.roll(y, -1, axis=1)
        area_s = 0.5 * np.sum(x * ys - xs * y, axis=1)   # área com sinal (orientação)
        cx = np.sum((x + xs) * (x * ys - xs * y), axis=1) / (6 * area_s)
        cy = np.sum((y + ys) * (x * ys - xs * y), axis=1) / (6 * area_s)
        centros.append(np.stack([cx, cy], axis=1) + P0[:, 0, :])   # centroide de área
        areas.append(np.abs(area_s))
        sinais.append(np.sign(area_s))

        # Ângulos internos -> skewness equiângulo e razão de aspecto
        e = np.roll(P, -1, axis=1) - P                   # arestas i -> i+1
        L = np.linalg.norm(e, axis=2)
        a = -np.roll(e, 1, axis=1)
        cosang = np.sum(a * e, axis=2) / (np.linalg.norm(a, axis=2) * L)
        ang = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
        skews.append(np.maximum((ang.max(axis=1) - ang_eq) / (180 - ang_eq), (ang_eq - ang.min(axis=1)) / ang_eq))
        aspects.append(L.max(axis=1) / L.min(axis=1))

    area, C, sinal = np.concatenate(areas), np.vstack(centros), np.concatenate(sinais)
    skew_eq, aspect = np.concatenate(skews), np.concatenate(aspects)

    # Faces (arestas) -> dono / vizinho
    M = len(area)
    a_n = np.concatenate([cel.reshape(-1) for cel, _ in grupos])
    b_n = np.concatenate([np.roll(cel, -1, axis=1).reshape(-1) for cel, _ in grupos])
    celula = np.repeat(np.arange(M), np.concatenate([np.full(len(cel), cel.shape[1]) for cel, _ in grupos]))
    chave = np.sort(np.stack([a_n, b_n], axis=1), axis=1)
    ordem = np.lexsort((chave[:, 1], chave[:, 0]))
    ch = chave[ordem]
    igual = np.all(ch[1:] == ch[:-1], axis=1)
    i1 = ordem[:-1][igual]                           # meia-face do dono
    i2 = ordem[1:][igual]                            # meia-face do vizinho
    o, v = celula[i1], celula[i2]

    pa, pb = nos[a_n[i1]], nos[b_n[i1]]
    fc = 0.5 * (pa + pb)                             # centro da face
    t = pb - pa
    n = np.stack([t[:, 1], -t[:, 0]], axis=1) * sinal[o][:, None]   # normal para fora do dono
    d = C[v] - C[o]
    nmag, dmag = np.linalg.norm(n, axis=1), np.linalg.norm(d, axis=1)
    cos_nd = np.sum(n * d, axis=1) / (nmag * dmag)
    nao_ort = np.degrees(np.arccos(np.clip(cos_nd, -1, 1)))         # não-ortogonalidade (OpenFOAM)

    # Skewness (OpenFOAM): distância do centro da face à interseção da linha entre centros, / |d|
    nh = n / nmag[:, None]
    d_own = np.abs(np.sum((fc - C[o]) * nh, axis=1))
    d_nei = np.abs(np.sum((C[v] - fc) * nh, axis=1))
    ip = C[o] + d * (d_own / (d_own + d_nei))[:, None]
    skew_of = np.linalg.norm(fc - ip, axis=1) / dmag

    # Orthogonal quality (ANSYS): mínimo por célula de cos(A, f) e cos(A, c)
    oq = np.ones(M)
    f_o = fc - C[o]
    cos_fo = np.sum(n * f_o, axis=1) / (nmag * np.linalg.norm(f_o, axis=1))
    f_v = fc - C[v]
    cos_fv = np.sum(-n * f_v, axis=1) / (nmag * np.linalg.norm(f_v, axis=1))
    np.minimum.at(oq, o, np.minimum(cos_fo, cos_nd))
    np.minimum.at(oq, v, np.minimum(cos_fv, cos_nd))
    unicas = np.ones(len(ch), dtype=bool)            # faces de contorno: só cos(A, f)
    unicas[1:][igual] = False
    unicas[:-1][igual] = False
    ib = ordem[unicas]
    cb = celula[ib]
    pa_b, pb_b = nos[a_n[ib]], nos[b_n[ib]]
    tb = pb_b - pa_b
    nb = np.stack([tb[:, 1], -tb[:, 0]], axis=1) * sinal[cb][:, None]
    fb = 0.5 * (pa_b + pb_b) - C[cb]
    cos_b = np.sum(nb * fb, axis=1) / (np.linalg.norm(nb, axis=1) * np.linalg.norm(fb, axis=1))
    np.minimum.at(oq, cb, cos_b)

    # Growth rate (maior razão de área com um vizinho)
    gr_face = np.maximum(area[o] / area[v], area[v] / area[o])
    gr = np.ones(M)
    np.maximum.at(gr, o, gr_face)
    np.maximum.at(gr, v, gr_face)

    # Arestas únicas (para o visualizador)
    arestas = np.vstack([chave[ordem][np.r_[True, ~igual]]])

    return {"area": area, "centro": C, "skew_eq": skew_eq, "aspect": aspect, "ortho": oq,
            "nao_ort": nao_ort, "skew_of": skew_of, "growth": gr, "tamanho": np.sqrt(area),
            "arestas": arestas, "positivas": bool(np.all(sinal == sinal[0]) and np.all(area > 0))}
#


# Visualizador da malha (Plotly): arestas + contornos por condição de contorno (+ cor por métrica, opcional)
def plotMesh(malha_res, qualidade, metrica=None):
    nos = malha_res["nos"] * 1000                    # mm
    fig = go.Figure()

    ## Arestas das células (um único traço, com quebras)
    ar = qualidade["arestas"]
    xs = np.full(len(ar) * 3, np.nan)
    ys = np.full(len(ar) * 3, np.nan)
    xs[0::3], xs[1::3] = nos[ar[:, 0], 0], nos[ar[:, 1], 0]
    ys[0::3], ys[1::3] = nos[ar[:, 0], 1], nos[ar[:, 1], 1]
    fig.add_trace(go.Scattergl(x=xs, y=ys, mode='lines', name='Mesh', hoverinfo='skip',
                               line=dict(color='rgba(173, 216, 230, 0.55)', width=0.7)))

    ## Cor por métrica (centroides das células)
    if metrica is not None:
        nome, valores = metrica
        C = qualidade["centro"] * 1000
        fig.add_trace(go.Scattergl(x=C[:, 0], y=C[:, 1], mode='markers', name=nome, showlegend=False,
                                   marker=dict(size=4, color=valores, colorscale='Turbo', showscale=True,
                                               colorbar=dict(title=dict(text=nome), thickness=12)),
                                   hovertemplate=nome + ': %{marker.color:.3g}<br>x: %{x:.3f} mm<br>y: %{y:.3f} mm<extra></extra>'))

    ## Contornos (condições de contorno)
    cores = {"inlet": "#d62728", "outlet": "#2ca02c", "wall": "#ffffff", "axis": "#9aa5b1", "farfield": "#ff7f0e", "lateral": "#9467bd"}
    for nome, segs in malha_res["contornos"].items():
        bx = np.full(len(segs) * 3, np.nan)
        by = np.full(len(segs) * 3, np.nan)
        bx[0::3], bx[1::3] = nos[segs[:, 0], 0], nos[segs[:, 1], 0]
        by[0::3], by[1::3] = nos[segs[:, 0], 1], nos[segs[:, 1], 1]
        fig.add_trace(go.Scattergl(x=bx, y=by, mode='lines', name=nome, hoverinfo='name',
                                   line=dict(color=cores.get(nome, '#cccccc'), width=3,
                                             dash='dashdot' if nome == 'axis' else 'solid')))

    fig.update_layout(
        xaxis=dict(title=dict(text='x (mm)'), showgrid=False, zeroline=False),
        yaxis=dict(title=dict(text='y (mm)'), showgrid=False, zeroline=False, scaleanchor='x', scaleratio=1),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=60, b=0),
        height=620,
        dragmode='zoom',
    )
    return fig
#


# Histogramas das métricas de qualidade (escala log), com os limites dos critérios
def plotMeshQuality(malha_res, qualidade):
    dados = [
        ('Rho = Scaled Jacobian' + (' (quads)' if 'tris' in malha_res else ''), malha_res["rho"], 0.3),
        ('Equiangle skewness (ANSYS)', qualidade["skew_eq"], 0.95),
        ('Orthogonal quality (ANSYS)', qualidade["ortho"], 0.1),
        ('Non-orthogonality (°)', qualidade["nao_ort"], 70),
        ('Skewness (OpenFOAM)', qualidade["skew_of"], 4),
        ('Growth rate (area ratio)', qualidade["growth"], 2),
        ('Aspect ratio', qualidade["aspect"], None),
        ('Cell size (mm)', qualidade["tamanho"] * 1000, None),
    ]
    if 'tris' in malha_res:                          # malha híbrida (spike): qualidade dos triângulos
        dados += [('SICN (triangles)', malha_res["sicn"], 0.1), ('Gamma (triangles)', malha_res["gamma"], 0.1)]
    linhas = int(math.ceil(len(dados) / 4))
    fig = make_subplots(rows=linhas, cols=4, subplot_titles=[d[0] for d in dados], horizontal_spacing=0.06, vertical_spacing=0.16 if linhas == 2 else 0.1)
    for k, (nome, valores, limite) in enumerate(dados):
        lin, col = k // 4 + 1, k % 4 + 1
        fig.add_trace(go.Histogram(x=valores, nbinsx=50, marker_color='#1f77b4', showlegend=False,
                                   hovertemplate='%{x}<br>cells: %{y}<extra></extra>'), row=lin, col=col)
        if limite is not None:
            fig.add_vline(x=limite, line_dash='dash', line_color='#d62728', line_width=1.5, row=lin, col=col)
        fig.update_yaxes(type='log', row=lin, col=col)
    fig.update_layout(height=260 * linhas, margin=dict(l=0, r=0, t=40, b=0),
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', bargap=0.05)
    fig.update_annotations(font_size=12)
    return fig
#


# y+ estimado ao longo da parede
def plotYplus(x, yplus, parede_resolvida):
    fig = go.Figure()
    if parede_resolvida:
        fig.add_hline(y=1, line_dash='dash', line_color='#d62728', line_width=1.5)
    else:
        fig.add_hrect(y0=30, y1=300, fillcolor='#2ca02c', opacity=0.12, line_width=0)
    fig.add_trace(go.Scatter(x=x * 1000, y=yplus, mode='lines', line=dict(color='lightblue', width=3), name='y+',
                             hovertemplate='x: %{x:.2f} mm<br>y+: %{y:.3g}<extra></extra>'))
    fig.update_layout(title=dict(text='Estimated y+ along the wall'),
                      xaxis=dict(title=dict(text='x (mm)')), yaxis=dict(title=dict(text='y+'), type='log'),
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      margin=dict(l=0, r=0, t=60, b=0), height=360, showlegend=False)
    return fig
#


# Trava para o gmsh (estado global: uma malha por vez, mesmo com vários usuários)
@st.cache_resource
def gmshLock():
    return threading.Lock()
#


###

# add_propellant.txt file:

###

custom_options = []
custom_options_f = []
custom_options_o = []

try:
    data = []
    with open("add_propellant.txt", "r", encoding="utf-8") as file:
        # Pula as primeiras 5 linhas (ajuste se necessário)
        for _ in range(5):
            next(file)

        section = []

        for line in file:
            line = line.strip()
            if not line:  # Se a linha estiver vazia, processa a seção atual
                if section:
                    data.append(section)
                    add_prop_ = "\n" + "\n".join(section)
                    try:
                        add_prop_name = add_prop_.split('@')[1].split(';')[0]
                    except IndexError:
                        add_prop_name = "unknown"
                    add_prop = add_prop_.split('@')[0]

                    # Decide qual função chamar com base no conteúdo de add_prop
                    if "fuel " in add_prop and "oxid " in add_prop:
                        add_new_propellant(add_prop_name, add_prop)
                        custom_options.append(add_prop_name)
                    elif "fuel " in add_prop:
                        add_new_fuel(add_prop_name, add_prop)
                        custom_options_f.append(add_prop_name)
                    elif "oxid " in add_prop:
                        add_new_oxidizer(add_prop_name, add_prop)
                        custom_options_o.append(add_prop_name)

                    section = []  # Reinicia a seção

            else:
                section.append(line)

        # Se houver uma seção final sem linha vazia no fim do arquivo
        if section:
            data.append(section)
            add_prop_ = "\n" + "\n".join(section)
            try:
                add_prop_name = add_prop_.split('@')[1].split(';')[0]
            except IndexError:
                add_prop_name = "unknown"
            add_prop = add_prop_.split('@')[0]

            if "fuel " in add_prop and "oxid " in add_prop:
                add_new_propellant(add_prop_name, add_prop)
                custom_options.append(add_prop_name)
            elif "fuel " in add_prop:
                add_new_fuel(add_prop_name, add_prop)
                custom_options_f.append(add_prop_name)
            elif "oxid " in add_prop:
                add_new_oxidizer(add_prop_name, add_prop)
                custom_options_o.append(add_prop_name)

except Exception as e:
    # Em caso de erro, utiliza dados padrão
    card_str = """
    fuel C20H42(S)  C 20.0   H 42.0    wt%=100.00
    h,cal=-142242.1     t(k)=298.15   rho=788.6
    """
    p_name = "Paraffin"
    add_new_fuel(p_name, card_str)
    custom_options_f.append(p_name)

    card_str = """
    oxid NitrousOxide  N 2.0 O 1.0  wt%=100.00
    h,cal= 19467.0 t(k)=298.15
    """
    p_name = "N2O_custom"
    add_new_oxidizer(p_name, card_str)
    custom_options_o.append(p_name)


###

# TABS

###

tab_setup, tab_results = st.tabs(["Setup", "Results"])


###

# SETUP TAB

###

with tab_setup:

    col_setup_1, col_setup_2 = st.columns(2, gap="large")

    with col_setup_1:
        st.subheader("Operating conditions", divider="gray", anchor=False)

        P_3 = st.number_input(
            label='Ambient pressure',
            format="%f",
            step=1.,
            key='p_3',
            help="Ambient pressure in N/m²"
        )

        P_1 = st.number_input(
            label='Chamber pressure',
            min_value=P_3,
            format="%f",
            step=1.,
            key='p_1',
            help="Chamber pressure in N/m²"
        )

        F = st.number_input(
            label='Desired thrust',
            min_value=0.,
            format="%f",
            step=100.,
            key='f',
            help="Thrust in Newtons"
        )

        Method = st.radio('Spike nozzle contour method', [1,2], horizontal=True, help='1: [6][7] Method  |  2: [8][9] Method', key='method')

    with col_setup_2:
        st.subheader("Propellant", divider="gray", anchor=False)

        F_name = st.selectbox('Fuel', ['A50', 'Acetylene', 'AL', 'AP', 'B2H6', 'C2H2', 'C2H5OH', 'C2H6', 'C2H6_167', 'C3H8', 'CFx', 'CH3OH', 'CH4', 'CINCH', 'DMAZ', 'ECP_dimer', 'Ethanol', 'Gasoline', 'GCH4', 'GH2', 'GH2_160', 'H2', 'H2O', 'HTPB', 'Isopropanol', 'JetA', 'JP10', 'JP4', 'JPX', 'Kerosene', 'Kerosene90_H2O10', 'LCH4_NASA', 'LH2', 'M20', 'M20_NH3', 'Methanol', 'MHF3', 'MMH', 'N2H4', 'NH3', 'NITROMETHANE', 'Propane', 'Propylene', 'RP1', 'UDMH']+custom_options+custom_options_f,
                              key='f_name',
                              help="Select the fuel for bipropellant systems or the propellant for solid/monopropellant systems (ends with *)."
        )

        O_name = st.selectbox(
            'Oxidizer', ['90_H2O2', '98_H2O2', 'AIR', 'AIRSIMP', 'CLF3', 'CLF5', 'F2', 'GO2', 'H2O', 'H202', 'HAN315', 'HNO3', 'IRFNA', 'LO2', 'MON15', 'MON25', 'MON3', 'N2F4', 'N2H4', 'N2O', 'N2O3', 'N2O4', 'N2O_nbp', 'O2', 'OF2', 'Peroxide90', 'Peroxide98']+custom_options_o,
            key='o_name',
            help="Select the oxidizer for bipropellant systems. Unnecessary for solid/monopropellant systems."
        )

        OF = st.number_input(
            label='Mixture ratio',
            min_value=0.,
            format="%f",
            step=1.,
            key='of',
            help="Oxidizer-to-fuel mass ratio in the combustion chamber for bipropellant systems."
        )
    prop_num = 2

    with st.expander("Optional setup"):
        conv_on = st.checkbox(
            'Include the convergent section (chamber diameter)',
            key='conv_on',
            help="Conical and Bell nozzles: extends the convergent section at 45° (tangent to the entrance throat arc) up to the chamber diameter. "
                 "Spike nozzle: extends the cowl at 45° from the straight convergent section up to the chamber diameter (the central body stem continues straight)."
        )

        D_c = st.number_input(
            label='Chamber diameter',
            min_value=0.,
            format="%f",
            step=1.,
            key='d_c',
            disabled=not conv_on,
            help="Combustion chamber (nozzle inlet) diameter in mm."
        )

    st.session_state['OF'] = OF
    st.session_state['P_1'] = P_1
    st.session_state['P_3'] = P_3

    run_button = st.button("Run", type="primary")

    if run_button:

        def calculate_initial_parameters(Prop, P_1, OF, P_3, F):

            # Calculated Parameters:

            eps = Prop.get_eps_at_PcOvPe(Pc=P_1, MR=OF, PcOvPe=P_1/101325, frozen=1, frozenAtThroat=1)  # Nozzle Expansion Area Ratio
            c_star = Prop.get_Cstar(Pc=P_1, MR=OF)  # Initial C* (m/s)
            c_f, _, __ = Prop.getFrozen_PambCf(Pamb=P_3, Pc=P_1, MR=OF, eps=eps, frozenAtThroat=1)  # Initial thrust coefficient
            mw, gamma = Prop.get_Chamber_MolWt_gamma(Pc=P_1, MR=OF, eps=eps)  # Molar mass (g/mol) and gamma: specific heat ratio
            R = 8314 / mw  # Gas constant for the propellant: Ru/MM
            T_1 = Prop.get_Tcomb(Pc=P_1, MR=OF)  # Adiabatic flame temperature - Combustion temperature (K)
            mach = Prop.get_MachNumber(Pc=P_1, MR=OF, eps=eps, frozen=0, frozenAtThroat=0) # Return nozzle exit mach number

            #


            # Calculation of mass flow rates:

            A_t = (F) / (P_1 * c_f)  # Throat area of the nozzle (m²)
            m_total = (F) / (c_star * c_f)  # Initial total propellant mass flow rate (kg/s)
            m_f = m_total / (OF + 1)  # Initial fuel mass flow rate (kg/s)
            m_ox = m_total - m_f  # Initial oxidizer mass flow rate (kg/s)
            A_2 = A_t*eps   # Exit area of the nozzle (m²)

            R_2 = (A_2/math.pi)**0.5    # Exit radius (m)
            R_t = (A_t/math.pi)**0.5    # Throat radius (m)

            #


            initial_parameters = {
                "eps": eps,
                "c_star": c_star,
                "c_f": c_f,
                "mw": mw,
                "gamma": gamma,
                "R": R,
                "T_1": T_1,
                "A_t": A_t,
                "R_t": R_t,
                "R_2": R_2,
                "A_2": A_2,
                "m_total": m_total,
                "m_f": m_f,
                "m_ox": m_ox,
                "mach_2": mach
            }

            return initial_parameters

        from rocketcea.cea_obj_w_units import CEA_Obj

        Prop = CEA_Obj(propName=F_name, pressure_units='Pa', cstar_units='m/s', density_units='g/cc', temperature_units='K') if F_name.endswith(" *") else CEA_Obj(oxName=O_name, fuelName=F_name, pressure_units='Pa', cstar_units='m/s', density_units='g/cc', temperature_units='K')

        from rocketcea.cea_obj import CEA_Obj
        ispObj = CEA_Obj( propName=F_name ) if F_name.endswith(" *") else CEA_Obj(oxName=O_name, fuelName=F_name)
        st.session_state['IsoObj'] = ispObj

        initial_params = calculate_initial_parameters(Prop, P_1, OF, P_3, F)

        # P_1 - eps error:
        if initial_params['eps'] == 0:
            st.error('Error: CEA Bad Solution for the selected chamber pressure')
            initial_params = 0
        else:
            st.success("Check the **Results** tab.")

        st.session_state['initial_params'] = initial_params

        ## Entradas usadas no último 'Run' (para avisar se o setup mudou)
        st.session_state['run_inputs'] = (P_3, P_1, F, F_name, O_name, OF)


###

# RESULTS TAB

###

with tab_results:

    if 'initial_params' not in st.session_state or st.session_state['initial_params'] == 0:
        st.info("Set up your engine in the **Setup** tab and click on 'Run'")

    else:
        try:
            # CadQuery é importado só aqui (biblioteca pesada: importar no início deixaria a abertura do app mais lenta)
            import cadquery as cq
            from cadquery import exporters

            if st.session_state.get('run_inputs') != (P_3, P_1, F, F_name, O_name, OF):
                st.warning("The setup has changed since the last run. Click on 'Run' again to update the results.")

            initial_params = st.session_state['initial_params']
            Method = st.session_state['method']
            spike_detail = st.session_state['spike_detail']

            st.subheader("Rocket Nozzle Dimensions", anchor=False, divider='gray')

            nozzle_choice = st.radio(
                'Type of nozzle',
                ['Conical', 'Bell', 'Spike'],
                horizontal=True,
                key='nozzle_type'
            )

            with st.spinner('Loading...'):

                if nozzle_choice == "Conical":

                    conical = {}
                    conical['Throat radius (mm)'] = initial_params["R_t"]*1000
                    conical['Exit radius (mm)'] = initial_params["R_2"]*1000
                    conical['Divergent Length (mm)'] = 0
                    conical['Curve 1 Radius (mm)'] = 0
                    conical['Curve 2 Radius (mm)'] = 0


                    # Throat circular arc

                    ## Entrance throat circular arc (Curve 1) [3][1]
                    theta1 = np.linspace(-135, -90, num=100)  # Values of theta from -135 to -90
                    x1c = 1.5 * conical['Throat radius (mm)'] * np.cos(np.radians(theta1))
                    y1c = 1.5 * conical['Throat radius (mm)'] * np.sin(np.radians(theta1)) + 1.5 * conical['Throat radius (mm)'] + conical['Throat radius (mm)']
                    initial_params['L_c'] = x1c[-1] # Convergent length (mm)
                    conical['Curve 1 Radius (mm)'] = 1.5*conical['Throat radius (mm)']

                    x1_start = x1c[0]
                    x1_end = x1c[-1]
                    y1_start = y1c[0]
                    y1_end = y1c[-1]

                    ## Convergent section (Curve 0) - Optional setup: chamber diameter
                    ### Straight line tangent to the start of Curve 1 (45°), from the chamber radius up to Curve 1
                    conv_on = False
                    if st.session_state.get('conv_on', False):
                        R_c = st.session_state.get('d_c', 0.) / 2  # Chamber radius (mm)

                        if R_c > y1_start:
                            theta_conv = 45  # Convergent half-angle (°): same angle where Curve 1 starts (-135°)
                            x0_start = x1_start - (R_c - y1_start) / np.tan(np.radians(theta_conv))
                            x0c = np.linspace(x0_start, x1_start, num=100)
                            y0c = y1_start - np.tan(np.radians(theta_conv)) * (x0c - x1_start)

                            x0_end = x0c[-1]
                            y0_start = y0c[0]
                            y0_end = y0c[-1]

                            conical['Chamber radius (mm)'] = R_c
                            conical['Convergent Length (mm)'] = x1_end - x0_start  # From the chamber to the throat
                            conv_on = True
                        else:
                            st.warning(f"The chamber diameter must be larger than {2 * y1_start:.2f} mm (start of Curve 1). The convergent section was not included.")


                    ## Exit throat circular arc (Curve 2) [3][1]
                    theta2 = np.linspace(-90, (15 - 90), num=100)
                    x2c = 0.382 * conical['Throat radius (mm)'] * np.cos(np.radians(theta2))
                    y2c = 0.382 * conical['Throat radius (mm)'] * np.sin(np.radians(theta2)) + 0.382 * conical['Throat radius (mm)'] + conical['Throat radius (mm)']
                    R_n = y2c[-1]
                    X_n = x2c[-1]
                    conical['Curve 2 Radius (mm)'] = 0.382*conical['Throat radius (mm)']

                    x2_start = x2c[0]
                    x2_end = x2c[-1]
                    y2_start = y2c[0]
                    y2_end = y2c[-1]

                    ###


                    # Divergent section

                    ## Divergent section length (15° Conical Nozzle Length) [1]
                    L_d = (conical['Exit radius (mm)']-y2_end)/(np.tan(np.radians(15)))
                    conical['Divergent Length (mm)'] = L_d

                    ## Exit shape
                    t = np.linspace(x2_end, L_d, num=100)
                    x3c = t
                    y3c = (np.tan(np.radians(15)))*t + y2_end-(np.tan(np.radians(15)))*x2_end

                    x3_start = x3c[0]
                    x3_end = x3c[-1]
                    y3_start = y3c[0]
                    y3_end = y3c[-1]

                    ###


                    conical_xy_1 = pd.DataFrame({'x (m)': [item/1000 for item in x1c], 'y (m)': [item/1000 for item in y1c]})
                    conical_xy_2 = pd.DataFrame({'x (m)': [item/1000 for item in x2c], 'y (m)': [item/1000 for item in y2c]})
                    conical_xy_3 = pd.DataFrame({'x (m)': [item/1000 for item in x3c], 'y (m)': [item/1000 for item in y3c]})

                    ## Lista com as curvas do contorno (Curve 0 só se o convergente estiver incluído)
                    curvas_xy_c = [conical_xy_1, conical_xy_2, conical_xy_3]
                    if conv_on:
                        conical_xy_0 = pd.DataFrame({'x (m)': [item / 1000 for item in x0c], 'y (m)': [item / 1000 for item in y0c]})
                        curvas_xy_c = [conical_xy_0] + curvas_xy_c


                    colunas_tabela = ['Throat radius (mm)', 'Exit radius (mm)', 'Divergent Length (mm)', 'Curve 1 Radius (mm)',
                                      'Curve 2 Radius (mm)']
                    valores_tabela = [round(conical['Throat radius (mm)'], 2),
                                      round(conical['Exit radius (mm)'], 2),
                                      round(conical['Divergent Length (mm)'], 2),
                                      round(conical['Curve 1 Radius (mm)'], 2),
                                      round(conical['Curve 2 Radius (mm)'], 2)]
                    if conv_on:
                        colunas_tabela = ['Chamber radius (mm)', 'Convergent Length (mm)'] + colunas_tabela
                        valores_tabela = [round(conical['Chamber radius (mm)'], 2), round(conical['Convergent Length (mm)'], 2)] + valores_tabela

                    table_conical_dimensions = go.Figure(data=[go.Table(header=dict(
                        values=colunas_tabela, height=40, align=['center'], line_color='darkslategray', fill_color='royalblue',
                        font=dict(color='white', size=16)),
                                                                        cells=dict(values=valores_tabela,
                                                                                   line_color='darkslategray', height=30,
                                                                                   fill_color=['lightcyan'],
                                                                                   font=dict(color='darkslategray', size=14)))
                                                               ], layout=go.Layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                                                         )

                    table_conical_dimensions.update_layout(title=dict(text='Conical Nozzle Dimensions', font=dict(color='royalblue', size=28)),
                                                           height=175 if conv_on else 150, margin=dict(l=0, r=0, t=60, b=0))

                    #

                    # Conical nozzle CAD

                    ## Combinar os pontos das curvas (Curve 0 se houver, Curve 1, Curve 2 e Curve 3)
                    lista_pontos_c = [
                        (round(x*1e3,4), round(y*1e3,4))
                        for curva in curvas_xy_c
                        for x, y in zip(curva['x (m)'], curva['y (m)'])
                    ]

                    ## Remover pontos repetidos (junção entre as curvas)
                    lista_pontos_c_ = [lista_pontos_c[0]]
                    for i in range(1, len(lista_pontos_c)):
                        if lista_pontos_c[i] != lista_pontos_c[i - 1]:  # Comparar com o ponto anterior
                            lista_pontos_c_.append(lista_pontos_c[i])


                    ## 2D (Sketch)

                    ### Cria a curva usando spline, liga ao eixo central, fecha o contorno e extrai o Wire (linha)
                    wire = cq.Workplane("XY").spline(lista_pontos_c_).lineTo(lista_pontos_c_[-1][0], 0).lineTo(lista_pontos_c_[0][0], 0).close().val()

                    ### Converte o Wire fechado diretamente em uma Superfície 2D (Face/Shape)
                    face = cq.Face.makeFromWires(wire)

                    ### Adiciona a face de volta ao Workplane
                    conical_nozzle = cq.Workplane("XY").add(face)

                    exporters.export(conical_nozzle, cad_dir+'/conical_nozzle_sketch.STEP')


                    ## 3D

                    ### Criar o esboço (spline) no CadQuery
                    perfil = [(r, z) for z, r in lista_pontos_c_]  # Inverter para (r, z) para o plano XY
                    esboco = cq.Workplane("XY").spline(perfil).lineTo(0, perfil[-1][1]).lineTo(0, perfil[0][1]).close()  # Fechar o perfil no eixo

                    ### Revolver ao redor do eixo Y
                    tubeira = esboco.revolve(angleDegrees=360, axisStart=(0, 0, 0), axisEnd=(0, 1, 0))

                    ### Exportar como STL e STEP
                    exporters.export(tubeira, cad_dir+'/conical_nozzle_3d.stl')
                    exporters.export(tubeira, cad_dir+'/conical_nozzle_3d.STEP')

                    #


                    # Results

                    st.plotly_chart(table_conical_dimensions)

                    col_plot, col_cad = st.columns(2)

                    with col_plot:
                        # Plot Nozzle Chart
                        curvas_plot = [('Curve 1', x1c, y1c, '#1f77b4'),
                             ('Curve 2', x2c, y2c, '#ff7f0e'),
                             ('Curve 3', x3c, y3c, '#2ca02c')]
                        pontos_plot = [(x1_start, y1_start, '#1f77b4'), (x1_end, y1_end, '#1f77b4'),
                             (x2_start, y2_start, '#ff7f0e'), (x2_end, y2_end, '#ff7f0e'),
                             (x3_start, y3_start, '#2ca02c'), (x3_end, y3_end, '#2ca02c')]

                        if conv_on:
                            curvas_plot = [('Curve 0', x0c, y0c, '#d62728')] + curvas_plot
                            pontos_plot = [(x0_start, y0_start, '#d62728'), (x0_end, y0_end, '#d62728')] + pontos_plot

                        plotContour(curvas_plot, pontos_plot, 'Conical Nozzle')

                    with col_cad:
                        displayCAD([('Conical nozzle', cad_dir+'/conical_nozzle_3d.stl')], 'Conical Nozzle - 3D')

                    # Coordinates plot
                    coordinates_conical = {'Coordinate': ['Start (x, y)', 'End (x, y)'],
                                           'Curve 1': [(round(x1_start, 2), round(y1_start, 2)), (round(x1_end, 2), round(y1_end, 2))],
                                           'Curve 2': [(round(x2_start, 2), round(y2_start, 2)), (round(x2_end, 2), round(y2_end, 2))],
                                           'Curve 3': [(round(x3_start, 2), round(y3_start, 2)), (round(x3_end, 2), round(y3_end, 2))]}

                    coordinates_conical = pd.DataFrame(coordinates_conical)
                    if conv_on:
                        coordinates_conical.insert(1, 'Curve 0', [(round(x0_start, 2), round(y0_start, 2)), (round(x0_end, 2), round(y0_end, 2))])

                    coordinates_conical = coordinates_conical.map(lambda p: f"({p[0]:.2f}, {p[1]:.2f})" if isinstance(p, tuple) else p)
                    st.table(coordinates_conical)
                    #


                    # Download Buttons

                    buffer = io.BytesIO()

                    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                        conical_xy = pd.concat(curvas_xy_c)
                        conical_xy.reset_index(drop=True, inplace=True)
                        conical_xy.to_excel(writer, sheet_name="CONICAL",index=False)

                    col_d1, col_d2, col_d3, col_d4 = st.columns(4)

                    col_d1.download_button(
                        label="Contour Coordinates (.xlsx)",
                        data=buffer.getvalue(),
                        use_container_width=True,
                        file_name="Conical_Nozzle_Contour_Coordinates.xlsx"
                    )
                    col_d2.download_button(
                        label="Nozzle Sketch (.STEP)",
                        data=open(cad_dir+'/conical_nozzle_sketch.STEP', "rb").read(),
                        file_name="conical_nozzle_sketch.STEP",
                        use_container_width=True,
                        mime="application/step"
                    )
                    col_d3.download_button(
                        label="Nozzle 3D (.STEP)",
                        data=open(cad_dir+'/conical_nozzle_3d.STEP', "rb").read(),
                        file_name="conical_nozzle_3d.STEP",
                        use_container_width=True,
                        mime="application/step"
                    )
                    col_d4.download_button(
                        label="Nozzle 3D (.STL)",
                        data=open(cad_dir+'/conical_nozzle_3d.stl', "rb").read(),
                        use_container_width=True,
                        file_name="conical_nozzle_3d.stl"
                    )


                if nozzle_choice == "Bell":

                    bell = {}
                    bell['Throat radius (mm)'] = initial_params["R_t"] * 1000
                    bell['Exit radius (mm)'] = initial_params["R_2"] * 1000
                    bell['Divergent Length (mm)'] = 0
                    bell['Divergent Theta n (°)'] = 0
                    bell['Divergent Theta e (°)'] = 0
                    bell['Curve 1 Radius (mm)'] = 0
                    bell['Curve 2 Radius (mm)'] = 0

                    # Parameters obtained from curve fitting [4][3]

                    ## theta n
                    a = 4.090132978351974
                    b = 16.539279319795025

                    theta_n = a * np.log(initial_params['eps']) + b

                    ## theta e
                    a = -2.175213837970657
                    b = 15.932404342184924

                    theta_e = a * np.log(initial_params['eps']) + b

                    ###

                    # Throat circular arc

                    ## Entrance throat circular arc (Curve 1) [3][5]
                    theta1 = np.linspace(-135, -90, num=100)  # Values of theta from -135 to -90
                    x1b = 1.5 * bell['Throat radius (mm)'] * np.cos(np.radians(theta1))
                    y1b = 1.5 * bell['Throat radius (mm)'] * np.sin(np.radians(theta1)) + 1.5 * bell['Throat radius (mm)'] + bell[
                        'Throat radius (mm)']
                    initial_params['L_c'] = x1b[-1]  # Convergent length (mm)
                    bell['Curve 1 Radius (mm)'] = 1.5 * bell['Throat radius (mm)']

                    x1_start = x1b[0]
                    x1_end = x1b[-1]
                    y1_start = y1b[0]
                    y1_end = y1b[-1]

                    ## Convergent section (Curve 0) - Optional setup: chamber diameter
                    ### Straight line tangent to the start of Curve 1 (45°), from the chamber radius up to Curve 1
                    conv_on = False
                    if st.session_state.get('conv_on', False):
                        R_c = st.session_state.get('d_c', 0.) / 2  # Chamber radius (mm)

                        if R_c > y1_start:
                            theta_conv = 45  # Convergent half-angle (°): same angle where Curve 1 starts (-135°)
                            x0_start = x1_start - (R_c - y1_start) / np.tan(np.radians(theta_conv))
                            x0b = np.linspace(x0_start, x1_start, num=100)
                            y0b = y1_start - np.tan(np.radians(theta_conv)) * (x0b - x1_start)

                            x0_end = x0b[-1]
                            y0_start = y0b[0]
                            y0_end = y0b[-1]

                            bell['Chamber radius (mm)'] = R_c
                            bell['Convergent Length (mm)'] = x1_end - x0_start  # From the chamber to the throat
                            conv_on = True
                        else:
                            st.warning(f"The chamber diameter must be larger than {2 * y1_start:.2f} mm (start of Curve 1). The convergent section was not included.")

                    ## Exit throat circular arc (Curve 2) [3][5]
                    theta2 = np.linspace(-90, (theta_n - 90), num=100)
                    x2b = 0.382 * bell['Throat radius (mm)'] * np.cos(np.radians(theta2))
                    y2b = 0.382 * bell['Throat radius (mm)'] * np.sin(np.radians(theta2)) + 0.382 * bell['Throat radius (mm)'] + bell[
                        'Throat radius (mm)']
                    R_n = y2b[-1]
                    X_n = x2b[-1]
                    bell['Curve 2 Radius (mm)'] = 0.382 * bell['Throat radius (mm)']

                    x2_start = x2b[0]
                    x2_end = x2b[-1]
                    y2_start = y2b[0]
                    y2_end = y2b[-1]

                    ###

                    # Divergent section [3][5]

                    ## Divergent section length (80% 15° Conical Nozzle Length)
                    L_d = 0.8 * ((((initial_params['eps'] ** 0.5) - 1) * bell['Throat radius (mm)']) / (np.tan(np.radians(15))))

                    Nx = x2b[-1]
                    Ny = y2b[-1]
                    Ex = 0.8 * ((((initial_params["eps"] ** 0.5) - 1) * bell['Throat radius (mm)']) / (np.tan(np.radians(15))))
                    Ey = bell['Exit radius (mm)']

                    m1 = np.tan(np.radians(theta_n))
                    m2 = np.tan(np.radians(theta_e))
                    C1 = Ny - (m1 * Nx)
                    C2 = Ey - (m2 * Ex)
                    Qx = (C2 - C1) / (m1 - m2)
                    Qy = ((C2 * m1) - (C1 * m2)) / (m1 - m2)

                    ## Exit circular arc (Curve 3) [3]
                    t = np.linspace(0, 1, num=100)
                    x3b = (((1 - t) ** 2) * Nx) + (2 * (1 - t) * t * Qx) + ((t ** 2) * Ex)
                    y3b = (((1 - t) ** 2) * Ny) + (2 * (1 - t) * t * Qy) + ((t ** 2) * Ey)

                    x3_start = x3b[0]
                    x3_end = x3b[-1]
                    y3_start = y3b[0]
                    y3_end = y3b[-1]

                    bell['Divergent Length (mm)'] = L_d
                    bell['Divergent Theta n (°)'] = theta_n
                    bell['Divergent Theta e (°)'] = theta_e

                    ###

                    bell_xy_1 = pd.DataFrame({'x (m)': [item / 1000 for item in x1b], 'y (m)': [item / 1000 for item in y1b]})
                    bell_xy_2 = pd.DataFrame({'x (m)': [item / 1000 for item in x2b], 'y (m)': [item / 1000 for item in y2b]})
                    bell_xy_3 = pd.DataFrame({'x (m)': [item / 1000 for item in x3b], 'y (m)': [item / 1000 for item in y3b]})

                    ## Lista com as curvas do contorno (Curve 0 só se o convergente estiver incluído)
                    curvas_xy_b = [bell_xy_1, bell_xy_2, bell_xy_3]
                    if conv_on:
                        bell_xy_0 = pd.DataFrame({'x (m)': [item / 1000 for item in x0b], 'y (m)': [item / 1000 for item in y0b]})
                        curvas_xy_b = [bell_xy_0] + curvas_xy_b

                    # Table:

                    colunas_tabela = ['Throat radius (mm)', 'Exit radius (mm)', 'Divergent Length (mm)', 'Divergent Theta n (°)',
                                      'Divergent Theta e (°)', 'Curve 1 Radius (mm)', 'Curve 2 Radius (mm)']
                    valores_tabela = [round(bell['Throat radius (mm)'], 2),
                                      round(bell['Exit radius (mm)'], 2),
                                      round(bell['Divergent Length (mm)'], 2),
                                      round(bell['Divergent Theta n (°)'], 1),
                                      round(bell['Divergent Theta e (°)'], 1),
                                      round(bell['Curve 1 Radius (mm)'], 2),
                                      round(bell['Curve 2 Radius (mm)'], 2)]
                    if conv_on:
                        colunas_tabela = ['Chamber radius (mm)', 'Convergent Length (mm)'] + colunas_tabela
                        valores_tabela = [round(bell['Chamber radius (mm)'], 2), round(bell['Convergent Length (mm)'], 2)] + valores_tabela

                    table_bell_dimensions = go.Figure(data=[go.Table(header=dict(
                        values=colunas_tabela, height=40, align=['center'],
                        line_color='darkslategray', fill_color='royalblue', font=dict(color='white', size=16)),
                                                                     cells=dict(values=valores_tabela,
                                                                                line_color='darkslategray', height=30,
                                                                                fill_color=['lightcyan'],
                                                                                font=dict(color='darkslategray', size=14)))
                                                            ], layout=go.Layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                                                      )

                    table_bell_dimensions.update_layout(title=dict(text='Bell-shaped Nozzle Dimensions', font=dict(color='royalblue', size=28)),
                                                        height=175, margin=dict(l=0, r=0, t=60, b=0))

                    #

                    # Bell nozzle CAD

                    ## Combinar os pontos das curvas (Curve 0 se houver, Curve 1, Curve 2 e Curve 3)
                    lista_pontos_b = [
                        (round(x*1e3,4), round(y*1e3,4))
                        for curva in curvas_xy_b
                        for x, y in zip(curva['x (m)'], curva['y (m)'])
                    ]

                    ## Remover pontos repetidos (junção entre as curvas)
                    lista_pontos_b_ = [lista_pontos_b[0]]
                    for i in range(1, len(lista_pontos_b)):
                        if lista_pontos_b[i] != lista_pontos_b[i - 1]:  # Comparar com o ponto anterior
                            lista_pontos_b_.append(lista_pontos_b[i])


                    ## 2D (Sketch)

                    ### Cria a curva usando spline, liga ao eixo central, fecha o contorno e extrai o Wire (linha)
                    wire = cq.Workplane("XY").spline(lista_pontos_b_).lineTo(lista_pontos_b_[-1][0], 0).lineTo(lista_pontos_b_[0][0], 0).close().val()

                    ### Converte o Wire fechado diretamente em uma Superfície 2D (Face/Shape)
                    face = cq.Face.makeFromWires(wire)

                    ### Adiciona a face de volta ao Workplane
                    bell_nozzle = cq.Workplane("XY").add(face)

                    exporters.export(bell_nozzle, cad_dir+'/bell_nozzle_sketch.STEP')


                    ## 3D

                    ### Criar o esboço (spline) no CadQuery
                    perfil = [(r, z) for z, r in lista_pontos_b_]  # Inverter para (r, z) para o plano XY
                    esboco = cq.Workplane("XY").spline(perfil).lineTo(0, perfil[-1][1]).lineTo(0, perfil[0][1]).close()  # Fechar o perfil no eixo

                    ### Revolver ao redor do eixo Y
                    tubeira = esboco.revolve(angleDegrees=360, axisStart=(0, 0, 0), axisEnd=(0, 1, 0))

                    ### Exportar como STL e STEP
                    exporters.export(tubeira, cad_dir+'/bell_nozzle_3d.stl')
                    exporters.export(tubeira, cad_dir+'/bell_nozzle_3d.STEP')

                    #


                    # Results

                    st.plotly_chart(table_bell_dimensions)

                    col_plot, col_cad = st.columns(2)

                    with col_plot:
                        # Plot Nozzle Chart
                        curvas_plot = [('Curve 1', x1b, y1b, '#1f77b4'),
                             ('Curve 2', x2b, y2b, '#ff7f0e'),
                             ('Curve 3', x3b, y3b, '#2ca02c')]
                        pontos_plot = [(x1_start, y1_start, '#1f77b4'), (x1_end, y1_end, '#1f77b4'),
                             (x2_start, y2_start, '#ff7f0e'), (x2_end, y2_end, '#ff7f0e'),
                             (x3_start, y3_start, '#2ca02c'), (x3_end, y3_end, '#2ca02c')]

                        if conv_on:
                            curvas_plot = [('Curve 0', x0b, y0b, '#d62728')] + curvas_plot
                            pontos_plot = [(x0_start, y0_start, '#d62728'), (x0_end, y0_end, '#d62728')] + pontos_plot

                        plotContour(curvas_plot, pontos_plot, 'Bell-shaped Nozzle')

                    with col_cad:
                        displayCAD([('Bell nozzle', cad_dir+'/bell_nozzle_3d.stl')], 'Bell-shaped Nozzle - 3D')

                    # Coordinates plot

                    coordinates_bell = {'Coordinate': ['Start (x, y)', 'End (x, y)'],
                                        'Curve 1': [(round(x1_start, 2), round(y1_start, 2)), (round(x1_end, 2), round(y1_end, 2))],
                                        'Curve 2': [(round(x2_start, 2), round(y2_start, 2)), (round(x2_end, 2), round(y2_end, 2))],
                                        'Curve 3': [(round(x3_start, 2), round(y3_start, 2)), (round(x3_end, 2), round(y3_end, 2))]}

                    coordinates_bell = pd.DataFrame(coordinates_bell)
                    if conv_on:
                        coordinates_bell.insert(1, 'Curve 0', [(round(x0_start, 2), round(y0_start, 2)), (round(x0_end, 2), round(y0_end, 2))])

                    coordinates_bell = coordinates_bell.map(lambda p: f"({p[0]:.2f}, {p[1]:.2f})" if isinstance(p, tuple) else p)
                    st.table(coordinates_bell)

                    #


                    # Download Buttons

                    buffer = io.BytesIO()

                    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                        bell_xy = pd.concat(curvas_xy_b)
                        bell_xy.reset_index(drop=True, inplace=True)
                        bell_xy.to_excel(writer, sheet_name="BELL",index=False)

                    col_d1, col_d2, col_d3, col_d4 = st.columns(4)

                    col_d1.download_button(
                        label="Contour Coordinates (.xlsx)",
                        data=buffer.getvalue(),
                        use_container_width=True,
                        file_name="Bell_Nozzle_Contour_Coordinates.xlsx"
                    )
                    col_d2.download_button(
                        label="Nozzle Sketch (.STEP)",
                        data=open(cad_dir+'/bell_nozzle_sketch.STEP', "rb").read(),
                        use_container_width=True,
                        file_name="bell_nozzle_sketch.STEP",
                        mime="application/step"
                    )
                    col_d3.download_button(
                        label="Nozzle 3D (.STEP)",
                        data=open(cad_dir+'/bell_nozzle_3d.STEP', "rb").read(),
                        use_container_width=True,
                        file_name="bell_nozzle_3d.STEP",
                        mime="application/step"
                    )
                    col_d4.download_button(
                        label="Nozzle 3D (.STL)",
                        data=open(cad_dir+'/bell_nozzle_3d.stl', "rb").read(),
                        use_container_width=True,
                        file_name="bell_nozzle_3d.stl"
                    )


                if nozzle_choice == "Spike":

                    spike = {}
                    spike['Throat gap (mm)'] = 0
                    spike['Spike base radius (mm)'] = 0
                    spike['Spike Length (mm)'] = 0
                    spike['Spike Length 50% (mm)'] = 0
                    spike['Initial angle (°)'] = 0
                    spike['50% Length angle (°)'] = 0
                    spike['Final angle (°)'] = 0

                    # Method:

                    # Method = 1   # 1: [6][7] Method | 2: [8][9] Method

                    #

                    i = 1

                    if initial_params['mach_2'] <= 1.5:
                        N = 1349
                    elif initial_params['mach_2'] <= 2:
                        N = 6205
                    elif initial_params['mach_2'] <= 3:
                        N = 27052
                    elif initial_params['mach_2'] <= 4:
                        N = 59094
                    else:
                        N = 97901

                    if spike_detail is False or spike_detail == 0:
                        N = 200
                    elif isinstance(spike_detail, int) and spike_detail is not True:
                        N = spike_detail if spike_detail > 100 else 200

                    # Divergent section (Curve 1) - Method 1 [6][7]

                    if Method == 1:

                        thetab = (((initial_params['gamma'] + 1) / (initial_params['gamma'] - 1)) ** (1 / 2)) * np.arctan(((((initial_params['gamma'] - 1) / (initial_params['gamma'] + 1)) * ((initial_params['mach_2'] ** 2) - 1)) ** (1 / 2))) - np.arctan(((initial_params['mach_2'] ** 2) - 1) ** (1 / 2))
                        re2_rt2 = (initial_params["A_t"] * np.cos(thetab)) / (np.pi)
                        mach_list = []  # Mach number
                        v_list = []
                        x_list = []
                        y_list = []

                        while i <= N:
                            mach_i = 1 + (i - 1) * ((initial_params['mach_2'] - 1) / (N - 1))  # Mach number
                            mach_list.append(mach_i)

                            v_i = (((initial_params['gamma'] + 1) / (initial_params['gamma'] - 1)) ** (1 / 2)) * np.arctan(((((initial_params['gamma'] - 1) / (initial_params['gamma'] + 1)) * ((mach_i ** 2) - 1)) ** (1 / 2))) - np.arctan(((mach_i ** 2) - 1) ** (1 / 2))
                            u_i = np.arcsin(1 / mach_i)  # Angle of Mach
                            thetha_i = thetab - v_i
                            phi_i = thetab - v_i + u_i  # Polar angle

                            Ai_At = (1 / mach_i) * (((2 / (initial_params['gamma'] + 1)) * (1 + (((initial_params['gamma'] - 1) / 2) * (mach_i ** 2)))) ** ((initial_params['gamma'] + 1) / (2 * (initial_params['gamma'] - 1))))

                            y_i = ((initial_params["R_2"] ** 2) - ((re2_rt2) * Ai_At * ((np.sin(phi_i)) / (np.sin(u_i) * np.cos(thetab))))) ** (1 / 2)
                            x_i = (initial_params["R_2"] - y_i) / np.tan(phi_i)

                            x_list.append(x_i)
                            y_list.append(y_i)

                            v_list.append(v_i)

                            i = i + 1

                        x1s = [item * 1000 for item in x_list]
                        y1s = [item * 1000 for item in y_list]

                        # Throat section (Curve 2)

                        x2s = np.linspace(x1s[0], 0, num=N)
                        y2s = np.tan(thetab) * (-x2s) + initial_params["R_2"] * 1000

                        #


                    # Divergent section (Curve 1) - Method 2 [8][9]

                    elif Method == 2:

                        thetab = (((initial_params['gamma'] + 1) / (initial_params['gamma'] - 1)) ** (1 / 2)) * np.arctan(((((initial_params['gamma'] - 1) / (initial_params['gamma'] + 1)) * ((initial_params['mach_2'] ** 2) - 1)) ** (1 / 2))) - np.arctan(((initial_params['mach_2'] ** 2) - 1) ** (1 / 2))
                        lipang = (np.pi / 2) - thetab  # 𝛙
                        lambdab = initial_params["R_2"] / initial_params['eps']  # Initial polar ray (λ)

                        lambda_list = [lambdab]  # Polar ray (λ)
                        mach_list = []  # Mach number
                        v_list = []

                        x_list = []
                        y_list = []

                        while i <= N:
                            ## Initial parameters for i
                            lambda_i = lambda_list[-1]  # Polar ray (λ)

                            mach_i = 1 + (i - 1) * ((initial_params['mach_2'] - 1) / (N - 1))  # Mach number
                            mach_list.append(mach_i)

                            v_i = (((initial_params['gamma'] + 1) / (initial_params['gamma'] - 1)) ** (1 / 2)) * np.arctan(((((initial_params['gamma'] - 1) / (initial_params['gamma'] + 1)) * ((mach_i ** 2) - 1)) ** (1 / 2))) - np.arctan(((mach_i ** 2) - 1) ** (1 / 2))
                            u_i = np.arcsin(1 / mach_i)  # Angle of Mach
                            phi_i = (np.pi / 2) - lipang - v_i + u_i  # Polar angle
                            ##

                            ## Parameters for i+1 in order to calculate 'beta_i'
                            mach_i1 = 1 + ((i + 1) - 1) * ((initial_params['mach_2'] - 1) / (N - 1))
                            v_i1 = (((initial_params['gamma'] + 1) / (initial_params['gamma'] - 1)) ** (1 / 2)) * np.arctan(((((initial_params['gamma'] - 1) / (initial_params['gamma'] + 1)) * ((mach_i1 ** 2) - 1)) ** (1 / 2))) - np.arctan(((mach_i1 ** 2) - 1) ** (1 / 2))
                            u_i1 = np.arcsin(1 / mach_i1)
                            phi_i1 = (np.pi / 2) - lipang - v_i1 + u_i1
                            ##

                            ## Dimensions for i
                            alpha_i = np.pi - phi_i + thetab - v_i
                            beta_i = phi_i1 - thetab + v_i

                            y_i = (np.sin(phi_i)) * lambda_i
                            x_i = (np.cos(phi_i)) * lambda_i

                            x_list.append(x_i)
                            y_list.append(y_i)

                            ##

                            lambda_i1 = (np.sin(alpha_i) / np.sin(beta_i)) * lambda_i
                            lambda_list.append(lambda_i1)
                            v_list.append(v_i)

                            i = i + 1

                        x1s = [item * 1000 for item in x_list]
                        y1s = [item * 1000 for item in y_list]

                        ###

                        # Throat section (Curve 2)

                        x2s = np.linspace(x1s[0], 0, num=N)
                        y2s = np.tan(-thetab) * (-x2s)

                        #

                        # Normalizing data

                        y_axline = y1s[-1]
                        y1s = [abs(item - y_axline) for item in y1s]
                        y2s = [abs(item - y_axline) for item in y2s]
                        y_axline = y1s[-1]

                        #

                    else:
                        x1s, y1s, x2s, y2s = [0], [0], [0], [0]

                    x1_start = x1s[0]
                    x1_end = last_valid(x1s)
                    # x1_end = x1s[-1]
                    y1_start = y1s[0]
                    y1_end = last_valid(y1s)
                    # y1_end = y1s[-1]

                    x1_mean = abs((x1_end - x1_start) / 2)
                    nearest_xmean = min(x1s, key=lambda x: abs(x - x1_mean))
                    nearest_xmean_index = x1s.index(nearest_xmean)
                    x150_start = x1s[0]
                    x150_end = nearest_xmean
                    y150_start = y1s[0]
                    y150_end = y1s[nearest_xmean_index]

                    x2_start = x2s[0]
                    x2_end = x2s[-1]
                    y2_start = y2s[0]
                    y2_end = y2s[-1]

                    spike['Throat gap (mm)'] = abs(y2_start - y1_start)
                    spike['Spike base radius (mm)'] = initial_params["R_2"] * 1000
                    spike['Spike Length (mm)'] = x1_end - x1_start
                    spike['Spike Length 50% (mm)'] = x150_end - x1_start

                    spike['Initial angle (°)'] = math.degrees(thetab - v_list[0])
                    spike['50% Length angle (°)'] = math.degrees(thetab - v_list[nearest_xmean_index])
                    spike['Final angle (°)'] = math.degrees(thetab - v_list[x1s.index(x1_end)])

                    spike_xy_1 = pd.DataFrame({'x (m)': [item / 1000 for item in x1s], 'y (m)': [item / 1000 for item in y1s]})
                    spike_xy_2 = pd.DataFrame({'x (m)': [item / 1000 for item in x2s], 'y (m)': [item / 1000 for item in y2s]})

                    ## Afastamento da curva 2 (espessura do lábio/carenagem)
                    afastamento_s2 = round(max(spike_xy_1['y (m)'])*1e3,4)/2
                    espessura_s2 = afastamento_s2 * math.cos(math.atan2(y2_start - y2_end, x2_end - x2_start))  # espessura normal da carenagem

                    ## Convergent section: carenagem reta (cilíndrica) até a Curve 2 e plug com cone de 45° desde o eixo central (+ arco até a Curve 1)
                    ## Extension to the chamber (Curve 0) - Optional setup: chamber diameter -> carenagem abre a 45° até a câmara e o eixo central continua reto
                    R_c = st.session_state.get('d_c', 0.) / 2 if st.session_state.get('conv_on', False) else 0.  # Chamber radius (mm)
                    carenagem_cs, plug_cs, carenagem_0s, plug_0s, r_haste_s, D_c_min = spikeConvergent(x1s, y1s, x2s, y2s, R_c)
                    conv_on = carenagem_0s is not None
                    if R_c > 0 and not conv_on:
                        st.warning(f"The chamber diameter must be larger than {D_c_min:.2f} mm (start of Curve 2). The extension to the chamber (Curve 0) was not included.")

                    ### Pontos de cada curva (trechos unidos)
                    juntar = lambda pecas: np.vstack([pecas[0]] + [q[1:] for q in pecas[1:]])
                    xcs, ycs = list(juntar(carenagem_cs)[:, 0]), list(juntar(carenagem_cs)[:, 1])     # Convergent (cowl)
                    xcps, ycps = list(juntar(plug_cs)[:, 0]), list(juntar(plug_cs)[:, 1])             # Convergent (plug)
                    spike_xy_c = pd.DataFrame({'x (m)': [item / 1000 for item in xcs], 'y (m)': [item / 1000 for item in ycs]})
                    spike_xy_cp = pd.DataFrame({'x (m)': [item / 1000 for item in xcps], 'y (m)': [item / 1000 for item in ycps]})

                    spike['Stem radius (mm)'] = r_haste_s
                    spike['Convergent Length (mm)'] = x2_end - xcs[0]  # From the start of the convergent section to the lip

                    if conv_on:
                        x0s, y0s = list(juntar(carenagem_0s)[:, 0]), list(juntar(carenagem_0s)[:, 1])     # Curve 0 (cowl)
                        x0ps, y0ps = list(juntar(plug_0s)[:, 0]), list(juntar(plug_0s)[:, 1])             # Curve 0 (plug)

                        x0_start = x0s[0]
                        x0_end = x0s[-1]
                        y0_start = y0s[0]
                        y0_end = y0s[-1]

                        spike['Chamber radius (mm)'] = R_c
                        spike['Convergent Length (mm)'] = x2_end - x0_start  # From the chamber to the lip
                        spike_xy_0 = pd.DataFrame({'x (m)': [item / 1000 for item in x0s], 'y (m)': [item / 1000 for item in y0s]})
                        spike_xy_0p = pd.DataFrame({'x (m)': [item / 1000 for item in x0ps], 'y (m)': [item / 1000 for item in y0ps]})

                    # Table:

                    colunas_tabela = ['Spike base radius (mm)', 'Throat gap (mm)', 'Spike Length (mm)', 'Spike Length 50% (mm)',
                                      'Initial angle (°)', '50% Length angle (°)', 'Final angle (°)']
                    valores_tabela = [round(spike['Spike base radius (mm)'], 2),
                                      round(spike['Throat gap (mm)'], 2),
                                      round(spike['Spike Length (mm)'], 2),
                                      round(spike['Spike Length 50% (mm)'], 2),
                                      round(spike['Initial angle (°)'], 2),
                                      round(spike['50% Length angle (°)'], 2),
                                      round(spike['Final angle (°)'], 2)]
                    colunas_tabela = ['Convergent Length (mm)', 'Stem radius (mm)'] + colunas_tabela
                    valores_tabela = [round(spike['Convergent Length (mm)'], 2), round(spike['Stem radius (mm)'], 2)] + valores_tabela
                    if conv_on:
                        colunas_tabela = ['Chamber radius (mm)'] + colunas_tabela
                        valores_tabela = [round(spike['Chamber radius (mm)'], 2)] + valores_tabela

                    table_spike_dimensions = go.Figure(data=[go.Table(header=dict(
                        values=colunas_tabela, height=40, align=['center'],
                        line_color='darkslategray', fill_color='royalblue', font=dict(color='white', size=16)),
                                                                      cells=dict(values=valores_tabela,
                                                                                 line_color='darkslategray', height=30,
                                                                                 fill_color=['lightcyan'],
                                                                                 font=dict(color='darkslategray', size=14)))
                                                             ], layout=go.Layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                                                       )

                    table_spike_dimensions.update_layout(title=dict(text='Spike Nozzle Dimensions', font=dict(color='royalblue', size=28)),
                                                         height=200, margin=dict(l=0, r=0, t=60, b=0))

                    #

                    # Spike nozzle CAD

                    ## Tratar os pontos da lista spike_xy_1
                    lista_pontos_s = [
                        (round(x * 1e3, 4), round(y * 1e3, 4))
                        for x, y in zip(spike_xy_1['x (m)'], spike_xy_1['y (m)'])
                        if not (math.isnan(x) or math.isnan(y))
                    ]

                    ## Remover pontos repetidos
                    lista_pontos_s_ = [lista_pontos_s[0]]
                    for i in range(1, len(lista_pontos_s)):
                        if lista_pontos_s[i] != lista_pontos_s[i - 1]:  # Comparar com o ponto anterior
                            lista_pontos_s_.append(lista_pontos_s[i])

                    ## Tratar os pontos da lista spike_xy_2
                    lista_pontos_s2 = [
                        (round(x * 1e3, 4), round(y * 1e3, 4))
                        for x, y in zip(spike_xy_2['x (m)'], spike_xy_2['y (m)'])
                        if not (math.isnan(x) or math.isnan(y))
                    ]

                    ## Remover pontos repetidos
                    lista_pontos_s2_ = [lista_pontos_s2[0]]
                    for i in range(1, len(lista_pontos_s2)):
                        if lista_pontos_s2[i] != lista_pontos_s2[i - 1]:  # Comparar com o ponto anterior
                            lista_pontos_s2_.append(lista_pontos_s2[i])

                    ## Plug: trechos da extensão (Curve 0, se houver) + convergente; carenagem: contorno interno (vértices) e externo (espessura constante)
                    pecas_plug = (plug_0s if conv_on else []) + plug_cs
                    vertices_ci = np.vstack([juntar((carenagem_0s if conv_on else []) + carenagem_cs), np.array(lista_pontos_s2_)[[-1]]])
                    vertices_ce = cowlOuter(vertices_ci, espessura_s2)
                    lista_pontos_ci_ = [(round(x, 4), round(y, 4)) for x, y in vertices_ci]
                    lista_pontos_ce_ = [(round(x, 4), round(y, 4)) for x, y in vertices_ce]

                    ### Esboço do plug: retas e arco do convergente + Curve 1 (spline) + linhas até o eixo central
                    def esbocoPlug(inverter):
                        P = lambda x, y: (round(float(y), 4), round(float(x), 4)) if inverter else (round(float(x), 4), round(float(y), 4))
                        esboco = cq.Workplane("XY").moveTo(*P(*pecas_plug[0][0]))
                        for peca in pecas_plug:
                            esboco = esboco.lineTo(*P(*peca[-1])) if len(peca) == 2 else esboco.spline([P(*q) for q in peca[1:]], includeCurrent=True)
                        esboco = esboco.spline([P(*q) for q in lista_pontos_s_[1:]], includeCurrent=True)
                        if lista_pontos_s_[-1][1] != 0:  # Se a curva não terminar no eixo, liga ao eixo
                            esboco = esboco.lineTo(*P(lista_pontos_s_[-1][0], 0))
                        return esboco.lineTo(*P(pecas_plug[0][0][0], 0)).close()


                    ## 2D (Sketch)

                    ### Curva 1 (spike) com o plug do convergente
                    wire1 = esbocoPlug(False).val()
                    face1 = cq.Face.makeFromWires(wire1)

                    ### Carenagem com espessura constante: contorno interno (convergente + Curve 2) + face do lábio + contorno externo
                    wire2 = cq.Workplane("XY").polyline(lista_pontos_ci_ + lista_pontos_ce_).close().val()
                    face2 = cq.Face.makeFromWires(wire2)

                    ### Adiciona as faces ao Workplane
                    spike_nozzle = cq.Workplane("XY").add(face1).add(face2)

                    exporters.export(spike_nozzle, cad_dir+'/spike_nozzle_sketch.STEP')


                    ## 3D

                    ### Primeiro esboço (plug + spike), em (r, z) no plano XY, e revolver
                    solido1 = esbocoPlug(True).revolve(angleDegrees=360, axisStart=(0, 0, 0), axisEnd=(0, 1, 0))  # Revolve ao redor do eixo Y

                    ### Segundo esboço (carenagem) e revolver
                    perfil_c = [(r, z) for z, r in lista_pontos_ci_ + lista_pontos_ce_]
                    esboco2 = cq.Workplane("XY").polyline(perfil_c).close()
                    solido2 = esboco2.revolve(angleDegrees=360, axisStart=(0, 0, 0), axisEnd=(0, 1, 0))

                    ### Combinar os dois sólidos
                    modelo_combinado = solido1.union(solido2)

                    ### Exportar como STL e STEP
                    exporters.export(solido1, cad_dir+'/spike_nozzle_3d_spike.stl')
                    exporters.export(solido2, cad_dir+'/spike_nozzle_3d_cowl.stl')
                    exporters.export(modelo_combinado, cad_dir+'/spike_nozzle_3d.stl')
                    exporters.export(modelo_combinado, cad_dir+'/spike_nozzle_3d.STEP')

                    #


                    # Results

                    st.plotly_chart(table_spike_dimensions)

                    col_plot, col_cad = st.columns(2)

                    with col_plot:
                        # Plot Nozzle Chart
                        curvas_plot = [('Curve 1', x1s, y1s, '#1f77b4'),
                             ('Curve 2', x2s, y2s, '#ff7f0e')]
                        pontos_plot = [(x1_start, y1_start, '#1f77b4'), (x1_end, y1_end, '#1f77b4'),
                             (x2_start, y2_start, '#ff7f0e'), (x2_end, y2_end, '#ff7f0e'),
                             (x150_start, y150_start, '#1f77b4'), (x150_end, y150_end, '#1f77b4')]

                        curvas_plot = [('Convergent', xcs, ycs, '#8c564b'), ('Convergent (plug)', xcps, ycps, '#e377c2')] + curvas_plot
                        pontos_plot = [(xcs[0], ycs[0], '#8c564b'), (xcs[-1], ycs[-1], '#8c564b'),
                                       (xcps[0], ycps[0], '#e377c2'), (xcps[-1], ycps[-1], '#e377c2')] + pontos_plot

                        if conv_on:
                            curvas_plot = [('Curve 0', x0s, y0s, '#d62728'), ('Curve 0 (plug)', x0ps, y0ps, '#9467bd')] + curvas_plot
                            pontos_plot = [(x0_start, y0_start, '#d62728'), (x0_end, y0_end, '#d62728'),
                                           (x0ps[0], y0ps[0], '#9467bd'), (x0ps[-1], y0ps[-1], '#9467bd')] + pontos_plot

                        plotContour(curvas_plot, pontos_plot, 'Spike Nozzle')

                    with col_cad:
                        displayCAD([('Spike', cad_dir+'/spike_nozzle_3d_spike.stl'),
                                    ('Throat (cowl)', cad_dir+'/spike_nozzle_3d_cowl.stl')], 'Spike Nozzle - 3D')

                    # Coordinates plot

                    coordinates_spike = {'Coordinate': ['Start (x, y)', 'End (x, y)'],
                                         'Curve 1': [(round(x1_start, 2), round(y1_start, 2)), (round(x1_end, 2), round(y1_end, 2))],
                                         'Curve 1 (50% length)': [(round(x150_start, 2), round(y150_start, 2)),
                                                                  (round(x150_end, 2), round(y150_end, 2))],
                                         'Curve 2': [(round(x2_start, 2), round(y2_start, 2)), (round(x2_end, 2), round(y2_end, 2))]}

                    coordinates_spike = pd.DataFrame(coordinates_spike)
                    coordinates_spike.insert(1, 'Convergent', [(round(xcs[0], 2), round(ycs[0], 2)), (round(xcs[-1], 2), round(ycs[-1], 2))])
                    coordinates_spike.insert(2, 'Convergent (plug)', [(round(xcps[0], 2), round(ycps[0], 2)), (round(xcps[-1], 2), round(ycps[-1], 2))])
                    if conv_on:
                        coordinates_spike.insert(1, 'Curve 0', [(round(x0_start, 2), round(y0_start, 2)), (round(x0_end, 2), round(y0_end, 2))])
                        coordinates_spike.insert(2, 'Curve 0 (plug)', [(round(x0ps[0], 2), round(y0ps[0], 2)), (round(x0ps[-1], 2), round(y0ps[-1], 2))])

                    coordinates_spike = coordinates_spike.map(lambda p: f"({p[0]:.2f}, {p[1]:.2f})" if isinstance(p, tuple) else p)
                    st.table(coordinates_spike)

                    #


                    # Download Buttons

                    buffer = io.BytesIO()

                    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                        if conv_on:
                            spike_xy_0.to_excel(writer, sheet_name="SPIKE - Curve 0",index=False)
                            spike_xy_0p.to_excel(writer, sheet_name="SPIKE - Curve 0 (plug)",index=False)
                        spike_xy_c.to_excel(writer, sheet_name="SPIKE - Convergent",index=False)
                        spike_xy_cp.to_excel(writer, sheet_name="SPIKE - Convergent (plug)",index=False)
                        spike_xy_1.to_excel(writer, sheet_name="SPIKE - Curve 1",index=False)
                        spike_xy_2.to_excel(writer, sheet_name="SPIKE - Curve 2",index=False)

                    col_d1, col_d2, col_d3, col_d4 = st.columns(4)

                    col_d1.download_button(
                        label="Contour Coordinates (.xlsx)",
                        data=buffer.getvalue(),
                        use_container_width=True,
                        file_name="Spike_Nozzle_Contour_Coordinates.xlsx"
                    )
                    col_d2.download_button(
                        label="Nozzle Sketch (.STEP)",
                        data=open(cad_dir+'/spike_nozzle_sketch.STEP', "rb").read(),
                        file_name="spike_nozzle_sketch.STEP",
                        use_container_width=True,
                        mime="application/step"
                    )
                    col_d3.download_button(
                        label="Nozzle 3D (.STEP)",
                        data=open(cad_dir+'/spike_nozzle_3d.STEP', "rb").read(),
                        file_name="spike_nozzle_3d.STEP",
                        use_container_width=True,
                        mime="application/step"
                    )
                    col_d4.download_button(
                        label="Nozzle 3D (.STL)",
                        data=open(cad_dir+'/spike_nozzle_3d.stl', "rb").read(),
                        use_container_width=True,
                        file_name="spike_nozzle_3d.stl"
                    )

                #

        except Exception as e:
            st.error(f"Error while generating the nozzle: {e}")


        # CEA Results
        from rocketcea.cea_obj import CEA_Obj

        try:
            st.subheader("CEA Results", anchor=False, divider='gray')
            initial_params = st.session_state['initial_params']
            ispObj = st.session_state['IsoObj']
            P_3_run, P_1_run, F_run, F_name_run, O_name_run, OF_run = st.session_state['run_inputs']  # Valores usados no último 'Run'

            col_m1, col_m2, col_m3, col_m4, col_m5, col_m6 = st.columns(6)
            col_m1.metric('Expansion ratio (ε)', f"{initial_params['eps']:.2f}")
            col_m2.metric('Exit Mach', f"{initial_params['mach_2']:.2f}")
            col_m3.metric('c* (m/s)', f"{initial_params['c_star']:.1f}")
            col_m4.metric('Cf', f"{initial_params['c_f']:.3f}")
            col_m5.metric('Chamber temp. (K)', f"{initial_params['T_1']:.0f}")
            col_m6.metric('Mass flow (kg/s)', f"{initial_params['m_total']:.3f}")

            dadosCEA = ispObj.get_full_cea_output(Pc=P_1_run * 1e-5, MR=OF_run, eps=initial_params['eps'], PcOvPe=P_1_run / P_3_run,
                                                  frozen=1, frozenAtThroat=1, pc_units='bar')
            st.download_button("Download NASA's CEA Full Output", str(dadosCEA), file_name='CEA_Output.txt')

        except:
            pass


        # Mesh
        try:
            st.subheader("Mesh", anchor=False, divider='gray')

            if not gmsh_ok:
                st.error(f"Gmsh could not be loaded: {gmsh_erro}\n\nInstall it with `pip install gmsh==4.15.2`. "
                         "On Linux (e.g. Streamlit Cloud) it also needs the system libraries listed in packages.txt (libglu1-mesa, libxcursor1, libxinerama1, libxft2).")

            else:
                P_3_run, P_1_run, F_run, F_name_run, O_name_run, OF_run = st.session_state['run_inputs']  # Valores usados no último 'Run'
                ispObj = st.session_state['IsoObj']

                if nozzle_choice == "Spike":
                    ## Spike (Curve 1, pontos válidos e sem repetição, em m), Mach de projeto em cada ponto e lábio (fim da Curve 2)
                    spike_m = spike_xy_1[['x (m)', 'y (m)']].to_numpy()
                    mach_spike = np.asarray(mach_list, dtype=float)
                    validos = ~np.isnan(spike_m).any(axis=1)
                    spike_m, mach_spike = spike_m[validos], mach_spike[validos]
                    unicos = np.r_[True, np.linalg.norm(np.diff(spike_m, axis=0), axis=1) > 1e-9]
                    spike_m, mach_spike = spike_m[unicos], mach_spike[unicos]
                    lip_m = (float(x2s[-1]) / 1000, float(y2s[-1]) / 1000)
                    w_m = math.dist(spike_m[0], lip_m)                                                        # largura da garganta
                    R_t_m = (initial_params['A_t'] / math.pi) ** 0.5                                           # raio equivalente da garganta
                    R_e_m = lip_m[1]

                    ## Carenagem e plug (m), na mesma geometria do CAD: trechos da extensão (Curve 0, se houver) + convergente (+ Curve 2 na carenagem)
                    carenagem_m = [q / 1000 for q in (carenagem_0s if conv_on else []) + carenagem_cs] + [np.array([[x2_start, y2_start], [x2_end, y2_end]]) / 1000]
                    plug_m = [q / 1000 for q in (plug_0s if conv_on else []) + plug_cs]
                    carenagem_ext_m = vertices_ce / 1000                                                       # parede externa (espessura do CAD)
                    curvas_malha = [spike_m, juntar(carenagem_m), juntar(plug_m), carenagem_ext_m]
                    extra_assinatura = (conv_on,)

                else:
                    ## Contorno da parede (m) da tubeira escolhida: lista de curvas (Curve 0 se houver, Curve 1, 2 e 3)
                    curvas_malha = [curva[['x (m)', 'y (m)']].to_numpy() for curva in (curvas_xy_c if nozzle_choice == "Conical" else curvas_xy_b)]
                    R_t_m = min(float(np.min(c[:, 1])) for c in curvas_malha)
                    R_e_m = float(curvas_malha[-1][-1][1])
                    extra_assinatura = ()

                ## Setup da malha
                col_ms1, col_ms2, col_ms3, col_ms4 = st.columns(4)
                L_out_D = col_ms1.number_input('Outlet domain length', min_value=0.5, step=0.5, format="%.1f", key='mesh_L',
                                               help="Length of the plume region downstream of the nozzle exit (spike: downstream of the spike end), in exit diameters.")
                H_out_D = col_ms2.number_input('Outlet domain height', min_value=0.75, step=0.25, format="%.2f", key='mesh_H',
                                               help="Height of the plume region measured from the axis, in exit diameters (must be larger than 0.5).")
                parede = col_ms3.radio('Wall treatment', ['Wall functions', 'Resolved wall'], key='mesh_wall',
                                       help="Wall functions: 30 ≤ y+ ≤ 300 from the throat to the exit (k-ε + standard wall functions, as in the Fluent tutorial). Resolved wall: y+ < 1 on the whole wall (k-ω SST to the wall).")
                densidade = col_ms4.radio('Mesh density', ['Coarse', 'Medium', 'Fine'], key='mesh_density', horizontal=True,
                                          help="Axial cell size in the nozzle: throat radius / 6, / 10 or / 14 (refinement ratio ≈ 1.4, as in a GCI study). "
                                               "Spike: throat gap / 6, / 10 or / 14 near the walls and at the throat, and equivalent throat radius / 3, / 5 or / 7 in the plume.")
                gerar = st.button('Generate mesh', type='primary')

                parede_resolvida = parede == 'Resolved wall'
                divisor = {'Coarse': 6, 'Medium': 10, 'Fine': 14}[densidade]
                dx_malha = R_t_m / divisor
                r_out_max = {'Coarse': 1.05, 'Medium': 1.03, 'Fine': 1.02}[densidade]

                ## Propriedades na garganta (CEA) para o y+
                gamma_c, R_gas = initial_params['gamma'], initial_params['R']
                T_0, P_0 = initial_params['T_1'], P_1_run
                try:
                    mu_t = ispObj.get_Throat_Transport(Pc=P_0 / 6894.757, MR=OF_run, frozen=0)[1] * 1e-4   # millipoise -> Pa.s
                except:
                    mu_t = 1.716e-5 * (T_0 * 2 / (gamma_c + 1) / 273.15) ** 0.7                            # aproximação (ar)

                ## Assinatura (para saber se a malha mostrada corresponde à geometria e ao setup atuais)
                assinatura = hashlib.md5(np.vstack(curvas_malha).tobytes() + str((nozzle_choice, L_out_D, H_out_D, parede, densidade, T_0, P_0) + extra_assinatura).encode()).hexdigest()

                if gerar:
                    with st.spinner('Generating mesh...'):
                        if nozzle_choice == "Spike":
                            ## Altura da primeira célula: y+ por metro de altura da célula nas paredes da entrada e do spike
                            _, y_un, sup_un = spikeYplus(spike_m, mach_spike, juntar(carenagem_m), juntar(plug_m), gamma_c, R_gas, T_0, P_0, mu_t, 1.0)
                            if parede_resolvida:
                                h1_malha = 0.5 / np.nanmax(y_un)                                       # y+ <= 0,5 em toda a parede
                            else:
                                h1_malha = min(35 / np.nanmin(y_un[sup_un]), 300 / np.nanmax(y_un))    # y+ >= 35 no spike, sem passar de 300
                            with gmshLock():
                                malha_res = generateSpikeMesh(spike_m, carenagem_m, carenagem_ext_m, plug_m, L_out_D * 2 * R_e_m, H_out_D * 2 * R_e_m,
                                                              dx_malha, w_m / divisor, h1_malha, 1.2, cad_dir + '/nozzle_mesh')
                            qualidade = meshQuality(malha_res["nos"], malha_res["quads"], malha_res["tris"])
                            x_yp, yplus, supersonico = spikeYplus(malha_res["spike"], mach_spike[:len(malha_res["spike"])], juntar(carenagem_m), juntar(plug_m),
                                                                  gamma_c, R_gas, T_0, P_0, mu_t, h1_malha)
                        else:
                            h1_malha = firstCellHeight(curvas_malha, gamma_c, R_gas, T_0, P_0, mu_t, parede_resolvida)
                            with gmshLock():
                                malha_res = generateMesh(curvas_malha, L_out_D * 2 * R_e_m, H_out_D * 2 * R_e_m, dx_malha, h1_malha,
                                                         1.2, r_out_max, cad_dir + '/nozzle_mesh')
                            qualidade = meshQuality(malha_res["nos"], malha_res["quads"])
                            x_yp, yplus = wallYplus(curvas_malha, gamma_c, R_gas, T_0, P_0, mu_t, h1_malha)
                            pts_parede = np.vstack(curvas_malha)
                            supersonico = x_yp >= pts_parede[np.argmin(pts_parede[:, 1]), 0]   # da garganta até a saída
                        st.session_state['mesh'] = {'malha': malha_res, 'qualidade': qualidade, 'x_yp': x_yp, 'yplus': yplus, 'supersonico': supersonico,
                                                    'resolvida': parede_resolvida, 'assinatura': assinatura, 'tipo': nozzle_choice}

                if 'mesh' not in st.session_state:
                    st.info("Set up the mesh above and click on 'Generate mesh'.")

                else:
                    res = st.session_state['mesh']
                    malha_res, qualidade = res['malha'], res['qualidade']
                    hibrida = 'tris' in malha_res                          # malha do spike (quads + triângulos)

                    if res['assinatura'] != assinatura:
                        st.warning(f"This mesh was generated for a previous geometry or setup ({res['tipo']} nozzle). Click on 'Generate mesh' to update it.")

                    ## Resumo
                    n_quads = len(malha_res['quads'])
                    n_tris = len(malha_res['tris']) if hibrida else 0
                    n_cel, n_nos = n_quads + n_tris, len(malha_res['nos'])
                    x_yp, yplus = res['x_yp'], res['yplus']

                    ## Visualizador
                    opcoes_cor = {'None': None,
                                  'Orthogonal quality': qualidade['ortho'],
                                  'Equiangle skewness': qualidade['skew_eq'],
                                  'Aspect ratio': qualidade['aspect'],
                                  'Growth rate': qualidade['growth'],
                                  'Cell size (mm)': qualidade['tamanho'] * 1000}
                    cor_por = st.selectbox('Color cells by', list(opcoes_cor.keys()), key='mesh_color')
                    fig_malha = plotMesh(malha_res, qualidade, None if opcoes_cor[cor_por] is None else (cor_por, opcoes_cor[cor_por]))
                    st.plotly_chart(fig_malha, config={'scrollZoom': True})
                    st.caption("Scroll to zoom and drag to pan (double-click resets). Boundaries: :red[inlet], :green[outlet], wall (white), axis (gray, dash-dot), :orange[farfield]"
                               + (" and :violet[lateral] (inlet plane above the cowl)." if hibrida else "."))

                    ## Downloads
                    col_md1, col_md2, col_md3, col_md4, col_md5 = st.columns(5)
                    col_md1.download_button("Mesh (.msh, Gmsh)", malha_res['arquivos']['msh'], file_name="nozzle_mesh.msh", use_container_width=True)
                    col_md2.download_button("Mesh (.cgns)", malha_res['arquivos']['cgns'], file_name="nozzle_mesh.cgns", use_container_width=True)
                    col_md3.download_button("Mesh (.unv)", malha_res['arquivos']['unv'], file_name="nozzle_mesh.unv", use_container_width=True)
                    col_md4.download_button("Mesh (.su2)", malha_res['arquivos']['su2'], file_name="nozzle_mesh.su2", use_container_width=True)
                    col_md5.download_button("Mesh viewer (.html)", fig_malha.to_html(include_plotlyjs='cdn', config={'scrollZoom': True}),
                                            file_name="mesh_viewer.html", use_container_width=True)

                    ## Verificações de qualidade (inicialmente minimizado)
                    with st.expander("Mesh quality checks"):
                        rho_min = float(np.min(malha_res['rho']))
                        sk_max, sk_med = float(qualidade['skew_eq'].max()), float(qualidade['skew_eq'].mean())
                        oq_min, oq_med = float(qualidade['ortho'].min()), float(qualidade['ortho'].mean())
                        no_max, no_med = float(qualidade['nao_ort'].max()), float(qualidade['nao_ort'].mean())
                        so_max = float(qualidade['skew_of'].max())
                        gr_pct, gr_max = 100 * float(np.mean(qualidade['growth'] > 2)), float(qualidade['growth'].max())
                        ar_max, ar_p99 = float(qualidade['aspect'].max()), float(np.percentile(qualidade['aspect'], 99))
                        y_min_nos = float(np.min(malha_res['nos'][:, 1]))

                        if hibrida:
                            sicn_min, gam_min = float(np.min(malha_res['sicn'])), float(np.min(malha_res['gamma']))
                            tri_pct = 100 * float(np.mean(np.minimum(malha_res['sicn'], malha_res['gamma']) < 0.3))
                            tri_res = f"SICN min {sicn_min:.3f}, Gamma min {gam_min:.3f}, {tri_pct:.2f}% < 0.3"
                            tri_ok = "OK" if (sicn_min >= 0.1 and gam_min >= 0.1 and tri_pct <= 0.1) else "FAIL"
                        else:
                            tri_res, tri_ok = "all-quad mesh", "n/a"

                        trecho = "along the spike" if hibrida else "from the throat to the exit"
                        if res['resolvida']:
                            yp_crit = "max < 1 (k-ω SST to the wall)"
                            yp_res = f"max {np.nanmax(yplus):.2f}"
                            yp_ok = np.nanmax(yplus) < 1
                        else:
                            yp_div = yplus[res['supersonico']]
                            yp_crit = f"30 ≤ y+ ≤ 300 {trecho} (standard wall functions)"
                            yp_res = f"{yp_div.min():.0f} to {yp_div.max():.0f} (chamber side min {np.nanmin(yplus):.1f})"
                            yp_ok = (yp_div.min() >= 30) and (yp_div.max() <= 300)

                        verificacoes = [
                            ["Rho = Scaled Jacobian (Gmsh)", "min ≥ 0.3" + (" (boundary layer quads)" if hibrida else ""), f"min {rho_min:.3f}", "OK" if rho_min >= 0.3 else "FAIL"],
                            ["SICN / Gamma (Gmsh)", "triangles: min ≥ 0.1, ≤ 0.1% below 0.3", tri_res, tri_ok],
                            ["Equiangle skewness (ANSYS)", "max < 0.95 (good < 0.8)", f"max {sk_max:.3f}, mean {sk_med:.3f}", "OK" if sk_max < 0.95 else "FAIL"],
                            ["Orthogonal quality (ANSYS)", "min > 0.1 (good > 0.2)", f"min {oq_min:.3f}, mean {oq_med:.3f}", "OK" if oq_min > 0.1 else "FAIL"],
                            ["Non-orthogonality (OpenFOAM)", "max ≤ 70° (ideal ≤ 40°)", f"max {no_max:.1f}°, mean {no_med:.1f}°", "OK" if no_max <= 70 else "FAIL"],
                            ["Skewness (OpenFOAM)", "max < 4", f"max {so_max:.3f}", "OK" if so_max < 4 else "FAIL"],
                            ["Growth rate (area ratio)", "≤ 1% of cells with GR > 2", f"{gr_pct:.2f}% (max {gr_max:.2f})", "OK" if gr_pct <= 1 else "FAIL"],
                            ["Positive cell areas (checkMesh)", "no inverted cells", "all cells valid" if qualidade['positivas'] else "inverted cells", "OK" if qualidade['positivas'] else "FAIL"],
                            ["y+ (estimate)", yp_crit, yp_res, "OK" if yp_ok else "FAIL"],
                            ["Axisymmetric 2D (Fluent)", "axis on x, y ≥ 0", f"y min {y_min_nos * 1000:.3g} mm", "OK" if y_min_nos >= -1e-12 else "FAIL"],
                            ["Aspect ratio", "informative", f"max {ar_max:.0f}, p99 {ar_p99:.0f}", "info"],
                        ]
                        cor_status = {"OK": "#2ca02c", "FAIL": "#d62728", "n/a": "gray", "info": "gray"}

                        table_mesh_checks = go.Figure(data=[go.Table(
                            columnwidth=[2.2, 3, 2.6, 0.8],
                            header=dict(values=['Check', 'Criterion', 'Result', 'Status'], height=40, align=['left'],
                                        line_color='darkslategray', fill_color='royalblue', font=dict(color='white', size=16)),
                            cells=dict(values=[list(c) for c in zip(*verificacoes)], align=['left'], height=30,
                                       line_color='darkslategray', fill_color=['lightcyan'],
                                       font=dict(color=[['darkslategray'] * len(verificacoes)] * 3 + [[cor_status[v[3]] for v in verificacoes]], size=14)))
                        ], layout=go.Layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'))
                        table_mesh_checks.update_layout(height=50 + 36 * len(verificacoes), margin=dict(l=0, r=0, t=0, b=0))
                        st.plotly_chart(table_mesh_checks)

                        if hibrida:
                            st.caption(f"Criteria from the reference CFD report (Gmsh / ANSYS / OpenFOAM metrics) and from the Fluent nozzle tutorial setup. "
                                       f"Spike: hybrid 2D axisymmetric mesh, structured quad boundary layer on the walls + triangles (Frontal-Delaunay), cowl with the same thickness as the CAD. "
                                       f"y+ is an estimate (isentropic flow + flat-plate correlation Cf = 0.058 Re^-0.2 with the local annulus hydraulic diameter, "
                                       f"Mach from the spike design method, throat viscosity from CEA); check it in the solver.")
                        else:
                            st.caption(f"Criteria from the reference CFD report (Gmsh / ANSYS / OpenFOAM metrics) and from the Fluent nozzle tutorial setup "
                                       f"(2D axisymmetric, structured quads; tutorial mesh: 64,950 quads, orthogonal quality min 0.889 / mean 0.994, aspect ratio max 11.95). "
                                       f"y+ is an estimate (isentropic flow + flat-plate correlation Cf = 0.058 Re^-0.2, throat viscosity from CEA); check it in the solver.")

                        ## Distribuição das métricas e y+
                        st.plotly_chart(plotMeshQuality(malha_res, qualidade))
                        st.plotly_chart(plotYplus(x_yp, yplus, res['resolvida']))

                    ## Detalhes da malha (inicialmente minimizado)
                    with st.expander("Mesh details"):
                        col_mm1, col_mm2, col_mm3, col_mm4, col_mm5 = st.columns(5)
                        col_mm1.metric('Cells (quads + triangles)' if hibrida else 'Cells (quads)', f"{n_cel:,}")
                        col_mm2.metric('Nodes', f"{n_nos:,}")
                        col_mm3.metric('First cell height (mm)', f"{malha_res['h1'] * 1000:.3g}")
                        col_mm4.metric('Boundary layer cells', f"{malha_res['n_bl']}")
                        col_mm5.metric('y+ max (estimate)', f"{np.nanmax(yplus):.3g}")

                        if hibrida:
                            razao_in = malha_res['razao_entrada']
                            mach_in = float(machFromArea(razao_in, gamma_c, False)[0])
                            detalhes = pd.DataFrame({
                                'Parameter': ['First cell height (mm)', 'Boundary layer thickness (mm)', 'Boundary layer cells / growth ratio',
                                              'Quads / triangles', 'Throat gap (mm)', 'Cell size near the walls and at the throat (mm)',
                                              'Cell size in the plume (mm)', 'Inlet outer / inner diameter (mm)',
                                              'Inlet / throat area ratio (inlet Mach)', 'Outlet domain length × height (mm)',
                                              'Throat viscosity (Pa·s)', 'Units of the exported files'],
                                'Value': [f"{malha_res['h1'] * 1000:.4g}", f"{malha_res['delta'] * 1000:.3f}",
                                          f"{malha_res['n_bl']} / {malha_res['r_bl']:.3f}", f"{n_quads:,} / {n_tris:,}",
                                          f"{malha_res['w'] * 1000:.3f}", f"{malha_res['dx_ch'] * 1000:.3f}", f"{2 * malha_res['dx'] * 1000:.3f}",
                                          f"{2 * malha_res['R_in'] * 1000:.2f} / {2 * malha_res['r_in'] * 1000:.2f}",
                                          f"{razao_in:.2f} (M = {mach_in:.2f})", f"{malha_res['L_out'] * 1000:.1f} × {malha_res['H_out'] * 1000:.1f}",
                                          f"{mu_t:.3e}", "meters"]})
                            st.table(detalhes)
                            st.markdown("Suggested boundary conditions (Fluent): **inlet** → pressure-inlet (chamber conditions), "
                                        "**outlet** → pressure-outlet, **wall** → wall (cowl inside and outside, lip, central body and spike), **axis** → axis, "
                                        "**farfield** → pressure-far-field (or pressure-outlet at ambient conditions), "
                                        "**lateral** (inlet plane above the cowl) → pressure-far-field (or wall, if the vehicle body is there). "
                                        "The inlet is at the start of the convergent section (cylindrical cowl + 45° plug), or at the chamber (Curve 0) when the chamber diameter of the Optional setup is set.")
                        else:
                            detalhes = pd.DataFrame({
                                'Parameter': ['First cell height (mm)', 'Boundary layer thickness (mm)', 'Boundary layer cells / growth ratio',
                                              'Core cells (radial)', 'Axial cell size in the nozzle (mm)', 'Outlet domain length × height (mm)',
                                              'Outlet axial cells / growth ratio', 'Upper block cells / growth ratio',
                                              'Throat viscosity (Pa·s)', 'Units of the exported files'],
                                'Value': [f"{malha_res['h1'] * 1000:.4g}", f"{malha_res['delta'] * 1000:.3f}",
                                          f"{malha_res['n_bl']} / {malha_res['r_bl']:.3f}", f"{malha_res['n_core']}",
                                          f"{malha_res['dx'] * 1000:.3f}", f"{malha_res['L_out'] * 1000:.1f} × {malha_res['H_out'] * 1000:.1f}",
                                          f"{malha_res['n_out']} / {malha_res['r_out']:.3f}", f"{malha_res['n_sup']} / {malha_res['r_sup']:.3f}",
                                          f"{mu_t:.3e}", "meters"]})
                            st.table(detalhes)
                            st.markdown("Suggested boundary conditions (Fluent): **inlet** → pressure-inlet, **outlet** → pressure-outlet, "
                                        "**wall** → wall, **axis** → axis, **farfield** → pressure-far-field (or pressure-outlet at ambient conditions). "
                                        "Keep the farfield open to the ambient: a wall there confines the plume.")

        except Exception as e:
            st.error(f"Error while generating the mesh: {e}")
