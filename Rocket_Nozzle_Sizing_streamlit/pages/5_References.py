import streamlit as st
for k, v in st.session_state.items():
    st.session_state[k] = v

from PIL import Image
import os
path = os.path.dirname(__file__)
my_file = path+'/images/mechub_logo.png'
img = Image.open(my_file)

st.set_page_config(
    page_title='References - Rocket Nozzle Sizing',
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

st.header("References", anchor=False, divider='gray')
st.write("1.   Sutton, G.P. and Biblarz, O. (2001). Rocket Propulsion Elements. A Wiley Interscience publication. Wiley. ISBN: 9780471326427. [Online] Available at: < https://books.google.com.br/books?id=LQbDOxg3XZcC >.")
st.write("2.   Rao, G.V.R. (1958). Exhaust Nozzle Contour for Optimum Thrust. Journal of Jet Propulsion, 28(6), 377-382. DOI: < https://doi.org/10.2514/8.7324 >.")
st.write("3.   Newlands, R. (2017, April 18). The Thrust Optimized Parabolic Nozzle < http://www.aspirespace.org.uk/downloads/Thrust%20optimised%20parabolic%20nozzle.pdf >")
st.write("4.   Design of Thrust Chambers and Other Combustion Devices. In: Modern Engineering for Design of Liquid-Propellant Rocket Engines. (pp. 67-134). DOI: 10.2514/5.9781600866197.0067.0134. Available at: https://arc.aiaa.org/doi/abs/10.2514/5.9781600866197.0067.0134.")
st.write("5.   Samantra, A.K., Santhosh, K.S., Rashid, K., & Jayashree, A. (2020, August). Study of expansion ratio on dual bell nozzle of LOX-RP1 engine for replacing the existing bell nozzle to dual bell nozzle. IOP Conference Series: Materials Science and Engineering, 912(4), 042039. DOI: < https://dx.doi.org/10.1088/1757-899X/912/4/042039 >. IOP Publishing.")
st.write("6.   Vernacchia, M. (2013). Spike Contour Algorithm: Pyralis Rocket Engine. MIT Rocket Team. < https://www.bing.com/ck/a?!&&p=7434b40129859d8aJmltdHM9MTcwNjE0MDgwMCZpZ3VpZD0zMDFkNjRiZi02NjI0LTZhM2ItMDRkZi03NjFmNjdlYTZiMmMmaW5zaWQ9NTE4NA&ptn=3&ver=2&hsh=3&fclid=301d64bf-6624-6a3b-04df-761f67ea6b2c&psq=Vernacchia%2c+M.+(2013).+Spike+Contour+Algorithm%3a+Pyralis+Rocket+Engine.+MIT+Rocket+Team.+Date+Started%3a+December+13%2c+2013.+Date+Modified%3a+December+16%2c+2013.&u=a1aHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL212ZXJuYWNjL2Flcm9zcGlrZS1ub3p6bGUtZGVzaWduLWd1aS9tYXN0ZXIvU3Bpa2UlMjBDb250b3VyJTIwQWxnb3JpdGhtLnBkZg&ntb=1 > Date Started: December 13, 2013. Date Modified: December 16, 2013.")
st.write("7.   Besnard, E., Chen, H.H., Mueller, T., & Garvey, J. (2002). Design, Manufacturing and Test of a Plug Nozzle Rocket Engine. In 38th AIAA/ASME/SAE/ASEE Joint Propulsion Conference & Exhibit. DOI: 10.2514/6.2002-4038. < https://arc.aiaa.org/doi/abs/10.2514/6.2002-4038 >.")
st.write("8.  Haif, S., Kbab, H., & Benkhedda, A. (2022). \"Design and Numerical Analysis of a Plug Nozzle.\" Advances in Military Technology, 17(1), 17-32. ISSN 1802-2308, eISSN 2533-4123. DOI: < https://doi.org/10.3849/aimt.01523 >")
st.write("9.  Zebbiche, T. (2005). \"Supersonic Plug Nozzle Design.\" In 41st AIAA/ASME/SAE/ASEE Joint Propulsion Conference & Exhibit. DOI: < https://doi.org/10.2514/6.2005-4490 >.")
st.write(":red[10.  RocketCEA < https://rocketcea.readthedocs.io/en/latest/ >.]")
st.write(":red[11.  CEARUN < https://cearun.grc.nasa.gov/ >.]")
st.write(":red[12.  CadQuery < https://cadquery.readthedocs.io/en/latest/index.html >.]")
