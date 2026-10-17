import streamlit as st
for k, v in st.session_state.items():
    st.session_state[k] = v

from PIL import Image
import os
path = os.path.dirname(__file__)
my_file = path+'/images/mechub_logo.png'
img = Image.open(my_file)

st.set_page_config(
    page_title='About - Rocket Nozzle Sizing',
    layout="wide",
    page_icon=img
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

st.header("Rocket Nozzle Sizing v2.0.0", divider="gray", anchor=False)

st.markdown('''
This App enables you to design three different types of nozzle contours based on the propulsive parameters of your rocket engine:
- Conical;
- Bell-shaped;
- Spike.

The code generates a graph for each type of nozzle contour, a table with its main dimensions, and a .xlsx spreadsheet containing all the coordinates for each design.

The propulsive data is acquired using the RocketCEA library.

You can add custom propellants by editing the 'add_propellant.txt' file.

- Tutorial Video:

  [![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://youtu.be/Crxc9OeuSTg)

- How to use this code to design a free 3D CAD of the nozzle:

  [![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)]([https://youtu.be/Crxc9OeuSTg](https://www.youtube.com/watch?v=XwzFDo7mbuQ))

- How can you help me to improve this code:

  [![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/watch?v=z66-aUrW6dE&t=58s)
  '''
            )



path2 = os.path.dirname(__file__)
my_file2 = path2+'/images/Thumb_Mechub.png'
img2 = Image.open(my_file2)

st.image(img2)
