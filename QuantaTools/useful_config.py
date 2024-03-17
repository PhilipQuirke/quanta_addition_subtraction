import matplotlib.pyplot as plt

from .model_config import ModelConfig

from .useful_node import position_name, position_name_to_int, row_location_name, location_name, answer_name, NodeLocation, UsefulNode, UsefulNodeList


# Extends ModelConfig with info on which layers and nodes (attention heads and MLP neuron) in the model are actually useful.
class UsefulConfig(ModelConfig):
 
    def __init__(self):
        super().__init__()

        # sparce ordered list of useful (question and answer) token positions actually used by the model e.g. 0,1,8,9,10,11
        self.useful_positions = []

        # List of the useful attention heads and MLP neurons that the model actually uses
        self.useful_nodes = UsefulNodeList()
 
  
    def min_useful_position(self):
        return min(self.useful_positions)


    def max_useful_position(self):
        return max(self.useful_positions)


    # Add a token position that we know is used in calculations
    def add_useful_position(self, position):
        if not (position in self.useful_positions):
            self.useful_positions += [position]


    # Show the positions, their meanings, and the number of questions that failed when that position is ablated in a 3 row table
    def calc_position_failures_map(self, num_failures_list, width_inches=16):
        columns = ["Posn"]
        for i in range(len(self.token_position_meanings)):
          columns += [position_name(i)]
    
        rows = ["Posn", "# fails"]
        data = [
            ["Posn"] + self.token_position_meanings,
            ["# fails"] + num_failures_list
        ]
    
        fig, ax = plt.subplots(figsize=(width_inches,1))
        ax.axis('tight')
        ax.axis('off')
    
        table = ax.table(cellText=data, colLabels=columns, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(10)  # Set the font size here
        table.scale(1, 1.5)  # The first parameter scales column widths, the second scales row heights