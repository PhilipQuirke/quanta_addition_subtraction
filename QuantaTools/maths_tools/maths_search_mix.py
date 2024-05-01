from QuantaTools.useful_node import position_name, location_name, answer_name, UsefulNode, UsefulNodeList

from QuantaTools.quanta_constants import QType, QCondition, NO_IMPACT_TAG
from QuantaTools.quanta_map_impact import get_question_answer_impact, sort_unique_digits
from QuantaTools.quanta_filter import FilterNode, FilterAnd, FilterOr, FilterHead, FilterContains, FilterPosition, FilterAttention, FilterImpact, FilterAlgo, filter_nodes

from QuantaTools.ablate_config import AblateConfig
from QuantaTools.ablate_hooks import a_predict_questions, a_run_attention_intervention

from .maths_constants import MathsToken, MathsBehavior, MathsTask 
from .maths_data_generator import make_maths_questions_and_answers
from .maths_complexity import get_maths_question_complexity
from .maths_utilities import int_to_answer_str


def run_intervention_core(cfg, acfg, store_question, clean_question, expected_answer_impact, expected_answer_int, strong):
    assert(store_question[0] < + 10 ** cfg.n_digits)
    assert(store_question[1] > - 10 ** cfg.n_digits)
    assert(store_question[0] < + 10 ** cfg.n_digits)
    assert(store_question[1] > - 10 ** cfg.n_digits)
    assert(clean_question[0] < + 10 ** cfg.n_digits)
    assert(clean_question[1] > - 10 ** cfg.n_digits)
    assert(clean_question[0] < + 10 ** cfg.n_digits)
    assert(clean_question[1] > - 10 ** cfg.n_digits)

    # Calculate the test (clean) question answer e.g. "+006671"
    clean_answer_int = clean_question[0]+clean_question[1] if acfg.operation == MathsToken.PLUS else clean_question[0]-clean_question[1]
    clean_answer_str = int_to_answer_str(cfg, clean_answer_int)
    expected_answer_str = int_to_answer_str(cfg, expected_answer_int)

    # Matrices of tokens
    store_question_and_answer = make_maths_questions_and_answers(cfg, acfg.operation, QType.UNKNOWN, MathsBehavior.UNKNOWN, [store_question])
    clean_question_and_answer = make_maths_questions_and_answers(cfg, acfg.operation, QType.UNKNOWN, MathsBehavior.UNKNOWN, [clean_question])

    acfg.reset_intervention(expected_answer_str, expected_answer_impact)
    
    run_description = a_run_attention_intervention(cfg, store_question_and_answer, clean_question_and_answer, clean_answer_str)

    acfg.ablate_description = "Ablate" + ("" if strong else "(Weak)") + ":" + acfg.ablate_node_names() + ", Op:" + str(acfg.operation) + ", " + run_description


# Run an intervention where we have a precise expectation of the intervention impact
def run_strong_intervention(cfg, acfg, store_question, clean_question, expected_answer_impact, expected_answer_int):
    
    # These are the actual model prediction outputs (while applying our node-level intervention).
    run_intervention_core(cfg, acfg, store_question, clean_question, expected_answer_impact, expected_answer_int, strong=True)

    answer_success = (acfg.intervened_answer == acfg.expected_answer)
    impact_success = (acfg.intervened_impact == acfg.expected_impact)
    success = answer_success and impact_success

    if acfg.show_test_failures and not success:
        print("Failed: " + acfg.ablate_description)
    if acfg.show_test_successes and success:
        print("Success: " + acfg.ablate_description)

    return success, answer_success, impact_success


# Run an intervention where we expect the intervention to have a non-zero impact but we cant precisely predict the answer impact
def run_weak_intervention(cfg, acfg, store_question, clean_question):
    
    # Calculate the test (clean) question answer e.g. "+006671"
    clean_answer = clean_question[0]+clean_question[1] if acfg.operation == MathsToken.PLUS else clean_question[0]-clean_question[1]

    run_intervention_core(cfg, acfg, store_question, clean_question, NO_IMPACT_TAG, clean_answer, strong=False)

    answer_success = (acfg.intervened_answer != acfg.expected_answer) # We can't predict the answer
    impact_success = (acfg.intervened_impact != NO_IMPACT_TAG) # Has some impact
    success = answer_success and impact_success

    if acfg.show_test_failures and not success:
        print("Failed: No answer impact.", acfg.ablate_description)
    if acfg.show_test_successes and success:
        print("Success: " + acfg.ablate_description)

    return success


# A test function that always suceeds 
def succeed_test(cfg, acfg, alter_digit, strong):
    print( "Test confirmed", acfg.ablate_node_names(), "" if strong else "Weak")
    return True


# Common set of node filters (pre-requisites) for some maths tasks based on token position, attention to Dn and D'n, and answer digit impact
def math_common_prereqs(cfg, position, attend_digit, impact_digit):
    return FilterAnd(
        FilterHead(), # Is an attention head
        FilterPosition(position_name(position)), # Is at token position Px
        FilterAttention(cfg.dn_to_position_name(attend_digit)), # Attends to Dn
        FilterAttention(cfg.ddn_to_position_name(attend_digit)), # Attends to D'n
        FilterImpact(answer_name(impact_digit))) # Impacts Am


# Operator task tag
def opr_tag(impact_digit):
    return MathsTask.OPR_TAG.value # Doesnt depend on impact_digit


# Operator task prerequisites
def opr_prereqs(cfg, position, impact_digit):
    return FilterAnd(
        FilterHead(),
        FilterPosition(position_name(position)),
        FilterAttention(cfg.op_position_name()))


# Sign task tag
def sgn_tag(impact_digit):
    return MathsTask.SGN_TAG.value # Doesnt depend on impact_digit


# Sign task prerequisites
def sgn_prereqs(cfg, position, impact_digit):
    return FilterAnd(
        FilterHead(),
        FilterPosition(position_name(position)),
        FilterAttention(cfg.an_to_position_name(cfg.n_digits+1)))


# Tag for Greater Than "Dn > D'n" (Dn.GT) task used in SUB and NEG
def gt_tag(impact_digit):
  return answer_name(impact_digit) + "." + MathsTask.GT_TAG.value


# Prerequisites for Greater Than "Dn > D'n" (Dn.GT) task used in SUB and NEG
def gt_prereqs(cfg, position, attend_digit):
    return FilterAnd(
        FilterHead(), # Is an attention head
        FilterPosition(position_name(position)), # Is at token position Px
        FilterAttention(cfg.dn_to_position_name(attend_digit)), # Attends to Dn
        FilterAttention(cfg.ddn_to_position_name(attend_digit))) # Attends to D'n

