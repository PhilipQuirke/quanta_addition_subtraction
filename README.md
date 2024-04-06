<p align="center">
    <br>
    <img src="./pics/banner.png" width="500"/>
    <br>
<p>

## Introduction
This library support goals and uses terminology introduced in the paper https://arxiv.org/abs/2402.02619 . Please read the paper. In brief:
- Given an existing transformer model with low loss, this library help a researcher to analyze and understand the algorithm implemented by a transformer model.
- The "useful" token positions, attention heads and MLP neurons that are used in predictions are identified.  
- Various tools and techniques evaluate aspects of the model's "behavior" (e.g. attention patterns).
- The researcher can extend the tools with model-specific searches and tests - searching for hypothesised model components that perform model-specific algorithm "sub-tasks" (e.g. Base Add in the Addition model)
- Useful facts found in this way are stored as JSON (refer [Useful_Tags](./useful_tags.md) for details) and can be visualized (refer [Assets](./Assets/"Assets") for samples).
- A researcher can describe an algorithm hypothesis as a series of claims, and evaluate those claims against the facts found. The resulting insights can be used to refine and\or extend both the algorithm sub-task tests and the algorithm hypothesis description, leading to a full description of the model's algorithm.   

## Test bed
Much of this library is generic (can be applied to any transformer model). As a "real-world" testbed to help refine this library we use models trained to perform integer addition and subtraction (e.g. 133357+182243=+0315600 and 123450-345670=-0123230). Arithmetic-specific algorithm sub-task searches are defined (e.g. Base Add, Use Sum 9, Make Carry, Base Subtract, Borrow One). Addition and Subtraction hypothesises are described and evaluated in the Colab notebook VerifiedArithmeticAnalyse.ipynb. Arithmetic-specific python code is in files like [maths_config.py](./QuantaTools/maths_config.py).   

## Folders, Files and Classes 
This library contains files:

- **Notebooks:** Jupyter notebooks which are run in Google Colab or Jupyter: 
  - VerifiedArithmeticTrain.ipynb: Colab used to train transformer arithmetic models. 
    - Outputs pth and json files that are (manually) stored on HuggingFace
  - VerifiedArithmeticAnalyse.ipynb: Colab used to analyze the behavior and algorithm of transformer arithmetic models
    - Inputs pth files (generated above) from HuggingFace
    - Outputs *_behavior and *_algorithm json files that are (manually) stored on HuggingFace 
  - Accurate_Math_Train.ipynb: Deprecated. Predecessor of VerifiedArithmeticTrain associated with https://arxiv.org/abs/2402.02619 
  - Accurate_Math_Analyse.ipynb: Deprecated. Predecessor of VerifiedArithmeticAnalyse associated with https://arxiv.org/abs/2402.02619

- **QuantaTools:** Python library code imported into the notebooks:
  - model_*.py: Contains the configuration of the transformer model being trained/analysed. Includes class ModelConfig 
  - useful_*.py: Contains data on the useful token positions and useful nodes (attention heads and MLP neurons) that the model uses in predictions. Includes class UsefulConfig derived from ModelConfig. Refer [Useful_Tags](./useful_tags.md) for more detail. 
  - algo_*.py: Contains tools to support declaring and validating a model algorithm. Includes class AlgoConfig derived from UsefulConfig.
  - quanta_*.py: Contains categorisations of model behavior (aka quanta), with ways to detect, filter and graph them. Refer [Filter](./filter.md) for more detail. 
  - ablate_*.py: Contains ways to "intervention ablate" the model and detect the impact of the ablation
  - maths_*.py: Contains specializations of the above specific to arithmetic (addition and subtraction) transformer models. Includes class MathsConfig derived from AlgoConfig.
          
- **Tests:** Unit tests 

## HuggingFace resources
The HuggingFace website permanently stores the output files generated by the "arithmetic" 'train and 'analyse' notebooks:
- VerifiedArithmeticTrain/Analyse files are stored at https://huggingface.co/PhilipQuirke/VerifiedArithmetic covering these models:
  - add_**d5_l1**_h3_t30K: Inaccurate **5-digit, 1-layer, 3-attention-head**, addition model. 
  - add_d5_**l2**_h3_t15K: **Accurate** 5-digit, **2-layers**, 3-head addition model trained for 15K epochs. Training loss is 9e-9
  - add_**d6**_l2_h3_t15K: **Accurate** **6-digit**, 2-layers, 3-head addition model trained for 15K epochs.  
  - **sub**_d6_l2_h3_t30K: Inaccurate 6-digit, 2-layers, 3-head **subtraction** model trained for 30K epochs.
  - **mix**_d6_l3_h4_t40K: Inaccurate 6-digit, **3-layers, 4-head mixed** (add and subtract) model trained for 40K epochs. Training loss is 8e-09
  - **ins1**_mix_d6_l3_h4_t40K: **Accurate** 6-digit, 3-layers, 4-head mixed **initialise with addition model**. Handles 1m Qs for Add and Sub. 
  - **ins2**_mix_d6_l4_h4_t40K: Inaccurate 6-digit, 3-layers, 4-head mixed initialise with addition model. **Reset useful heads every 100 epochs**. Training loss is 7e-09. Fails 1m Qs
  - **ins3**_mix_d6_l4_h3_t40K: Inaccurate 6-digit, 3-layers, 4-head mixed initialise with addition model. **Reset useful heads and MLP every 100 epochs**. 
- Accurate_Math_Train/Analyse (deprecated) files are stored at https://huggingface.co/PhilipQuirke/Accurate5DigitAddition

## Papers
The papers associated with this content are:
- Understanding Addition in Transformers: https://arxiv.org/abs/2310.13121 . Aka Paper1. Model add_d5_l1_h3_t30K is very similar to the one in this paper. 
- Increasing Trust in Language Models through the Reuse of Verified Circuits. https://arxiv.org/abs/2402.02619 . Aka Paper2. Uses many of these models mostly focusing on add_d5_l2_h3_t15K, add_d6_l2_h3_t15K and ins1_mix_d6_l3_h4_t40K
- A future paper (Paper3) will include explaining the algorithm of the "mixed" model ins1_mix_d6_l3_h4_t40K

## Environment
Most exploratory work is done in a Google Colab in the 'train and 'analyse' notebooks. 
After a new 'search' is sucessfully developed and tested in the notebook, the code is migrated to the QuantaTools code folder. 

The files in the QuantaTools code folder have better version control and are easier to maintain than code blocks in a notebook.  
Using QuantaTools files also reduces version change conflicts between multiple people working to improve the library.
