import matplotlib as mpl
from cycler import cycler
import seaborn as sns

class Colors:
    dark_red = '#a61b14'
    red = '#da291c'
    medium_red = '#ed7b73'
    light_red = '#f9d3d0'

    dark_purple = '#7e5aa6'
    purple = '#ae90c3'
    medium_purple = '#cebcdb'
    light_purple = '#efe9f3'

    dark_yellow = '#c9a300'
    yellow = '#fecf28'
    medium_yellow = '#ffeca9'
    light_yellow = '#fff5d4'

    dark_blue = '#007f79'
    blue = '#00B2A9'
    medium_blue = '#66CCC6'
    light_blue = '#CCEEEC'

    dark_green = '#2f8a63'
    green = '#45b283'
    medium_green = '#8dd3b5'
    light_green = '#d9f0e6'

    grey_1000 = '#1F1F1F'
    grey_900 = '#2B2B2B'
    grey_700 = '#666666'
    grey_500 = '#9E9E9E'
    grey_300 = '#D9D9D9'
    grey_200 = '#EEEEEE'
    grey_100 = '#F5F5F5'


def sc_theme():

    palette = [
        Colors.red,
        Colors.blue,
        Colors.green,
        Colors.purple,
        Colors.yellow,
        Colors.medium_red,
        Colors.medium_blue,
        Colors.medium_green,
    ]

    mpl.rcParams['font.family'] = 'sans-serif'
    mpl.rcParams['font.sans-serif'] = ['Segoe UI', 'Arial']

    mpl.rcParams.update({
        "figure.facecolor": Colors.grey_100,
        "axes.facecolor": Colors.grey_200,
        "axes.edgecolor": Colors.grey_500,
        "axes.labelcolor": Colors.grey_1000,
        "xtick.color": Colors.grey_1000,
        "ytick.color": Colors.grey_1000,
        "text.color": Colors.grey_1000,
        "axes.spines.top": False,
        "axes.spines.right": False,
        'ytick.major.size': 0,
        'xtick.major.size': 0,
        'xtick.minor.size': 0,
        'ytick.minor.size': 0,
        'axes.grid': False,
        'grid.color': Colors.grey_100,
        'grid.alpha': .50,
        'grid.linestyle': '-',
        'grid.linewidth': .5,
        'savefig.bbox': 'tight',
        'savefig.dpi': 300,
        'savefig.pad_inches': 0.3,
        'axes.titlepad': 12,
        "axes.prop_cycle": cycler(color=palette)
    })

    sns.set_palette(palette)
