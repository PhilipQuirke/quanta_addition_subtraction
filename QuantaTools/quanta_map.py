import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import textwrap

from .useful_node import NodeLocation, UsefulNode, row_location_name
from .useful_info import UsefulInfo, useful_info


# Results to display in a quanta cell
class QuantaResult(NodeLocation):
  cell_text : str = ""
  color_index : int = -1


  def __init__(self, node, cell_text, color_index):
    super().__init__(node.position, node.layer, node.is_head, node.num)  # Call the parent class's constructor    
    self.cell_text = cell_text    
    self.color_index = color_index


# Calculate the results to display in all the quanta cell
def calc_quanta_results( major_tag, minor_tag, get_node_details, shades ):

  quanta_results = []

  for node in useful_info.nodes:
    cell_text, color_index = get_node_details(node, major_tag, minor_tag, shades)
    if cell_text != "" :
      quanta_results +=[QuantaResult(node, cell_text, color_index)]

  return quanta_results


# Define a colormap for use with graphing
def create_custom_colormap():
    colors = ["green", "yellow"]
    return mcolors.LinearSegmentedColormap.from_list("custom_colormap", colors)


# Blend the color with white to make it paler
def pale_color(color, factor=0.5):
    color_array = np.array(color)
    white = np.array([1, 1, 1, 1])
    return white * factor + color_array * (1 - factor)


# Row in the quanta map (covering L0H0 .. L0Hn L0MLP L1H0 .. L1Hn L1MLP ...):
def quanta_row(n_heads, the_layer, is_head, num):
    return the_layer * (n_heads+1) + ( num if is_head else n_heads)
  

# Find the quanta result for the specified cell
def find_quanta_result_by_row_col(n_heads, row, col, quanta_results):
    for result in quanta_results:
        result_row = quanta_row(n_heads, result.layer, result.is_head, result.num)
        if result_row == row and result.position == col:
            return result
    return None


# Get the row heading e.g. L1H2 or L2MLP
def get_quanta_row_heading(n_heads, r):
  head = r % (n_heads + 1)
  layer = r // (n_heads + 1)
  return row_location_name(layer, head)
  

# Draw a cell in the specified color
def show_quanta_add_patch(ax, j, row, cell_color):
  ax.add_patch(plt.Rectangle((j, row), 1, 1, fill=True, color=cell_color))


# Calculate (but do not draw) the quanta map with cell contents provided by get_node_details 
def calc_quanta_map( n_heads, token_position_meanings, custom_cmap, shades, major_tag, minor_tag, get_node_details, base_fontsize = 10, max_width = 10):
    
  if shades == None:
    shades = create_custom_colormap()
  
  quanta_results = calc_quanta_results(major_tag, minor_tag, get_node_details, shades)

  distinct_rows = set()
  distinct_cols = set()

  for result in quanta_results:
      result_row = quanta_row(n_heads, result.layer, result.is_head, result.num)    
      distinct_rows.add(result_row)
      distinct_cols.add(result.model_col)

  distinct_rows = sorted(distinct_rows)
  distinct_cols = sorted(distinct_cols)

  # Create figure and axes
  fig1, ax1 = plt.subplots(figsize=(2*len(distinct_cols)/3, 2*len(distinct_rows)/3))  # Adjust the figure size as needed

  # Ensure cells are square
  ax1.set_aspect('equal', adjustable='box')
  ax1.yaxis.set_tick_params(labelleft=True, labelright=False)

  colors = [pale_color(custom_cmap(i/shades)) for i in range(shades)]
  vertical_labels = []
  horizontal_labels = []
  wrapper = textwrap.TextWrapper(width=max_width)


  show_row = len(distinct_rows)-1
  for raw_row in distinct_rows:
    vertical_labels += [get__heading(n_heads, raw_row)]

    show_col = 0
    for raw_col in distinct_cols:
      cell_color = 'lightgrey'  # Color for empty cells

      if show_row == 0:
        horizontal_labels += [token_position_meanings[raw_col] + "/" + position_name(raw_col)]

      result = find_quanta_result_by_row_col(n_heads, raw_row, raw_col, quanta_results)
      if result != None:
        cell_color = colors[result.color_index] if result.color_index >= 0 else 'lightgrey'
        the_fontsize = base_fontsize if len(result.cell_text) < 4 else base_fontsize-1 if len(result.cell_text) < 5 else base_fontsize-2
        wrapped_text = wrapper.fill(text=result.cell_text)
        ax1.text(show_col + 0.5, show_row + 0.5, wrapped_text, ha='center', va='center', color='black', fontsize=the_fontsize)

      show_quanta_add_patch(ax1, show_col, show_row, cell_color)
      show_col += 1

    show_row -= 1


  # Configure x axis
  ax1.set_xlim(0, len(horizontal_labels))
  ax1.set_xticks(np.arange(0.5, len(horizontal_labels), 1))
  ax1.set_xticklabels(horizontal_labels)
  ax1.xaxis.tick_top()
  ax1.xaxis.set_label_position('top')
  ax1.tick_params(axis='x', length=0)
  for label in ax1.get_xticklabels():
    label.set_fontsize(9)

  # Configure y axis
  vertical_labels = vertical_labels[::-1] # Reverse the order
  ax1.set_ylim(0, len(vertical_labels))
  ax1.set_yticks(np.arange(0.5, len(vertical_labels), 1))
  ax1.set_yticklabels(vertical_labels)
  ax1.tick_params(axis='y', length=0)
  for label in ax1.get_yticklabels():
    label.set_horizontalalignment('left')
    label.set_position((-0.1, 0))  # Adjust the horizontal position

  return ax1, quanta_results