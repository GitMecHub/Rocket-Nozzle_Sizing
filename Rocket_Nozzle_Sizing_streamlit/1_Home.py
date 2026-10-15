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

import cadquery as cq
from cadquery import exporters

from stl import mesh

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


# Visualização 3D do CAD (numpy-stl + Plotly)
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

    # Fundo transparente (sem cor de fundo na cena e nos planos dos eixos)
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
            help="Conical and Bell nozzles only. Extends the convergent section at 45° (tangent to the entrance throat arc) up to the chamber diameter."
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

                    # Table:

                    table_spike_dimensions = go.Figure(data=[go.Table(header=dict(
                        values=['Spike base radius (mm)', 'Throat gap (mm)', 'Spike Length (mm)', 'Spike Length 50% (mm)',
                                'Initial angle (°)', '50% Length angle (°)', 'Final angle (°)'], height=40, align=['center'],
                        line_color='darkslategray', fill_color='royalblue', font=dict(color='white', size=16)),
                                                                      cells=dict(values=[round(spike['Spike base radius (mm)'], 2),
                                                                                         round(spike['Throat gap (mm)'], 2),
                                                                                         round(spike['Spike Length (mm)'], 2),
                                                                                         round(spike['Spike Length 50% (mm)'], 2),
                                                                                         round(spike['Initial angle (°)'], 2),
                                                                                         round(spike['50% Length angle (°)'], 2),
                                                                                         round(spike['Final angle (°)'], 2)],
                                                                                 line_color='darkslategray', height=30,
                                                                                 fill_color=['lightcyan'],
                                                                                 font=dict(color='darkslategray', size=14)))
                                                             ], layout=go.Layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                                                       )

                    table_spike_dimensions.update_layout(title=dict(text='Spike Nozzle Dimensions', font=dict(color='royalblue', size=28)),
                                                         height=175, margin=dict(l=0, r=0, t=60, b=0))

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

                    ## Afastamento da curva 2 (espessura do lábio/carenagem)
                    afastamento_s2 = round(max(spike_xy_1['y (m)'])*1e3,4)/2


                    ## 2D (Sketch)

                    ### Curva 1 (spike): spline + linhas até o eixo central
                    esboco1 = cq.Workplane("XY").spline(lista_pontos_s_)
                    if lista_pontos_s_[-1][1] != 0:  # Se a curva não terminar no eixo, liga ao eixo
                        esboco1 = esboco1.lineTo(lista_pontos_s_[-1][0], 0)
                    wire1 = esboco1.lineTo(lista_pontos_s_[0][0], 0).close().val()
                    face1 = cq.Face.makeFromWires(wire1)

                    ### Curva 2 (garganta): spline + linhas até a curva afastada
                    wire2 = cq.Workplane("XY").spline(lista_pontos_s2_).lineTo(lista_pontos_s2_[-1][0], lista_pontos_s2_[-1][1] + afastamento_s2).lineTo(lista_pontos_s2_[0][0], lista_pontos_s2_[0][1] + afastamento_s2).close().val()
                    face2 = cq.Face.makeFromWires(wire2)

                    ### Adiciona as faces ao Workplane
                    spike_nozzle = cq.Workplane("XY").add(face1).add(face2)

                    exporters.export(spike_nozzle, cad_dir+'/spike_nozzle_sketch.STEP')


                    ## 3D

                    ### Lista de pontos para o primeiro esboço
                    perfil1 = [(r, z) for z, r in lista_pontos_s_]  # Inverter para (r, z) para o plano XY

                    ### Criar o primeiro esboço (spline) e revolver
                    esboco1 = cq.Workplane("XY").spline(perfil1)
                    if perfil1[-1][0] != 0:  # Se a curva não terminar no eixo, liga ao eixo
                        esboco1 = esboco1.lineTo(0, perfil1[-1][1])
                    esboco1 = esboco1.lineTo(0, perfil1[0][1]).close()
                    solido1 = esboco1.revolve(angleDegrees=360, axisStart=(0, 0, 0), axisEnd=(0, 1, 0))  # Revolve ao redor do eixo Y

                    ### Lista de pontos para o segundo esboço
                    perfil2 = [(r, z) for z, r in lista_pontos_s2_]

                    ### Criar o segundo esboço (spline) e revolver
                    esboco2 = cq.Workplane("XY").spline(perfil2).lineTo(perfil2[-1][0] + afastamento_s2, perfil2[-1][1]).lineTo(perfil2[0][0] + afastamento_s2, perfil2[0][1]).close()
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
                        plotContour(
                            [('Curve 1', x1s, y1s, '#1f77b4'),
                             ('Curve 2', x2s, y2s, '#ff7f0e')],
                            [(x1_start, y1_start, '#1f77b4'), (x1_end, y1_end, '#1f77b4'),
                             (x2_start, y2_start, '#ff7f0e'), (x2_end, y2_end, '#ff7f0e'),
                             (x150_start, y150_start, '#1f77b4'), (x150_end, y150_end, '#1f77b4')],
                            'Spike Nozzle'
                        )

                    with col_cad:
                        displayCAD([('Spike', cad_dir+'/spike_nozzle_3d_spike.stl'),
                                    ('Throat (cowl)', cad_dir+'/spike_nozzle_3d_cowl.stl')], 'Spike Nozzle - 3D')

                    # Coordinates plot

                    coordinates_spike = {'Coordinate': ['Start (x, y)', 'End (x, y)'],
                                         'Curve 1': [(round(x1_start, 2), round(y1_start, 2)), (round(x1_end, 2), round(y1_end, 2))],
                                         'Curve 1 (50% length)': [(round(x150_start, 2), round(y150_start, 2)),
                                                                  (round(x150_end, 2), round(y150_end, 2))],
                                         'Curve 2': [(round(x2_start, 2), round(y2_start, 2)), (round(x2_end, 2), round(y2_end, 2))]}

                    coordinates_spike = pd.DataFrame(coordinates_spike).map(lambda p: f"({p[0]:.2f}, {p[1]:.2f})" if isinstance(p, tuple) else p)
                    st.table(coordinates_spike)

                    #


                    # Download Buttons

                    buffer = io.BytesIO()

                    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
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
