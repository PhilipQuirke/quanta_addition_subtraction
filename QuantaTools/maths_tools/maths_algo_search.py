
from QuantaTools.model_loss import logits_to_tokens_loss, loss_fn
from QuantaTools.model_token_to_char import tokens_to_string

from QuantaTools.useful_node import NodeLocation
from QuantaTools.useful_node import position_name, location_name, answer_name, NodeLocation, UsefulNode, UsefulNodeList

from QuantaTools.quanta_constants import QType, QCondition, NO_IMPACT_TAG
from QuantaTools.quanta_map_impact import get_question_answer_impact, sort_unique_digits
from QuantaTools.quanta_filter import FilterNode, FilterAnd, FilterOr, FilterHead, FilterNeuron, FilterContains, FilterPosition, FilterAttention, FilterImpact, FilterAlgo, filter_nodes

from QuantaTools.ablate_config import AblateConfig
from QuantaTools.ablate_hooks import a_predict_questions, a_run_attention_intervention

from .maths_constants import MathsToken, MathsBehavior, MathsTask 
from .maths_data_generator import maths_data_generator, maths_data_generator_core, make_maths_questions_and_answers
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

    acfg.ablate_description = "Intervening on " + acfg.node_names() + ", " + ("Strong" if strong else "Weak") + ", Node[0]=" + acfg.ablate_node_locations[0].name() + ", " + run_description


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
        print("Failed: Intervention had no impact on the answer", acfg.ablate_description)
    if acfg.show_test_successes and success:
        print("Success: " + acfg.ablate_description)

    return success


# A test function that always suceeds 
def succeed_test(cfg, acfg, alter_digit, strong):
    print( "Test confirmed", acfg.node_locations[0].name(), acfg.node_locations[1].name() if len(acfg.node_locations)>1 else "", "" if strong else "Weak")
    return True


# Common set of node filters (pre-requisites) for some maths tasks based on token position, attention to Dn and D'n, and answer digit impact
def math_common_prereqs(cfg, position, attend_digit, impact_digit):
    return FilterAnd(
        FilterHead(), # Is an attention head
        FilterPosition(position_name(position)), # Is at token position Px
        FilterAttention(cfg.dn_to_position_name(attend_digit)), # Attends to Dn
        FilterAttention(cfg.ddn_to_position_name(attend_digit)), # Attends to D'n
        FilterImpact(answer_name(impact_digit))) # Impacts Am


# Tag for addition "Use Sum 9" (SS) task e.g. 34633+55555=+090188 where D4 and D'4 sum to 9 (4+5), and D3 + D'3 > 10
def add_ss_tag(impact_digit):
    return answer_name(impact_digit-1)  + "." + MathsTask.SS_TAG.value


# Node rerequisites for addition "Use Sum 9" (SS) task
def add_ss_prereqs(cfg, position, impact_digit):
    # Pays attention to Dn-2 and D'n-2. Impacts An
    return math_common_prereqs(cfg, position, impact_digit-2, impact_digit)


# Intervention ablation test for addition "Use Sum 9" (SS) task
def add_ss_test(cfg, acfg, alter_digit, strong):
    if alter_digit < 2 or alter_digit > cfg.n_digits:
        acfg.reset_intervention()
        return False

    intervention_impact = answer_name(alter_digit)

    # 25222 + 44444 = 69666. Has no Dn-2.SC but has Dn-1.SS so not a UseSum9 case
    store_question = [cfg.repeat_digit(2), cfg.repeat_digit(4)]
    store_question[0] += (5-2) * 10 ** (alter_digit - 1)

    # 34633 + 55555 = 90188. Has Dn-2.SC and Dn-1.SS so is a UseSum9 case
    clean_question = [cfg.repeat_digit(3), cfg.repeat_digit(5)]
    clean_question[0] += (4-3) * 10 ** (alter_digit - 1)
    clean_question[0] += (6-3) * 10 ** (alter_digit - 2)

    # When we intervene we expect answer 80188
    intervened_answer = clean_question[0] + clean_question[1] - 10 ** (alter_digit)


    # Unit test
    if cfg.n_digits == 5 and alter_digit == 4:
        assert store_question[0] == 25222
        assert clean_question[0] == 34633
        assert clean_question[0] + clean_question[1] == 90188
        assert intervened_answer == 80188


    success, _, _ = run_strong_intervention(cfg, acfg, store_question, clean_question, intervention_impact, intervened_answer)

    if success:
        print( "Test confirmed", acfg.node_names(), "perform A"+str(alter_digit)+".SS impacting "+intervention_impact+" accuracy.", "" if strong else "Weak")

    return success


# Tag for addition "Make Carry 1" (SC) task e.g. 222222+666966=+0889188 where D2 + D'2 > 10
def add_sc_tag(impact_digit):
    return answer_name(impact_digit-1)  + "." + MathsTask.SC_TAG.value


# Node rerequisites for addition "Make Carry 1" (SC) task
def add_sc_prereqs(cfg, position, impact_digit):
    # Pays attention to Dn-1 and D'n-1. Impacts An
    return math_common_prereqs(cfg, position, impact_digit-1, impact_digit)


# Intervention ablation test for addition "Make Carry 1" (SC) task
def add_sc_test(cfg, acfg, impact_digit, strong):
    alter_digit = impact_digit - 1

    if alter_digit < 0 or alter_digit >= cfg.n_digits:
        acfg.reset_intervention()
        return False

    intervention_impact = answer_name(impact_digit)

    # 222222 + 666966 = 889188. Has Dn.SC
    store_question = [cfg.repeat_digit(2), cfg.repeat_digit(6)]
    store_question[1] += (9 - 6) * (10 ** alter_digit)

    # 333333 + 555555 = 888888. No Dn.SC
    clean_question = [cfg.repeat_digit(3), cfg.repeat_digit(5)]

    # When we intervene we expect answer 889888
    intervened_answer = clean_question[0] + clean_question[1] + 10 ** (alter_digit+1)

    success, _, _ = run_strong_intervention(cfg, acfg, store_question, clean_question, intervention_impact, intervened_answer)

    if success:
        print( "Test confirmed", acfg.node_names(), "perform A"+str(alter_digit)+".SC impacting "+intervention_impact+" accuracy.", "" if strong else "Weak")

    return success


# Tag for addition "Simple Add" (SA) task e.g. 555555+111111=+0666666 where D3 + D'3 < 10
def add_sa_tag(impact_digit):
    return answer_name(impact_digit) + "." + MathsTask.SA_TAG.value


# Node rerequisites for addition "Simple Add" (SA) task
def add_sa_prereqs(cfg, position, impact_digit):
    # Pays attention to Dn and D'n. Impacts An
    return math_common_prereqs(cfg, position, impact_digit, impact_digit)


def add_sa_test1(cfg, alter_digit):
    # 222222 + 111111 = +333333. No Dn.SC
    store_question = [cfg.repeat_digit(2), cfg.repeat_digit(1)]

    # 555555 + 444444 = +999999. No Dn.SC
    clean_question = [cfg.repeat_digit(5), cfg.repeat_digit(4)]

    # When we intervene we expect answer +999399
    intervened_answer = clean_question[0] + clean_question[1] + (3-9) * 10 ** alter_digit

    return store_question, clean_question, intervened_answer


def add_sa_test2(cfg, alter_digit):
    # 222222 + 666666 = +888888. No Dn.SC
    store_question = [cfg.repeat_digit(2), cfg.repeat_digit(6)]

    # 555555 + 111111 = +666666. No Dn.SC
    clean_question = [cfg.repeat_digit(5), cfg.repeat_digit(1)]

    # When we intervene we expect answer +666866
    intervened_answer = clean_question[0] + clean_question[1] + (8-6) * 10 ** alter_digit

    return store_question, clean_question, intervened_answer


# Intervention ablation test for addition "Simple Add" (SA) task
def add_sa_test(cfg, acfg, alter_digit, strong):
    # Note: MD and SA give the same result when D'=0 or D=D'=5. We avoid ablation tests like this.

    intervention_impact = answer_name(alter_digit)

    store_question, clean_question, intervened_answer = add_sa_test1(cfg, alter_digit)
    success1, _, impact_success1 = run_strong_intervention(cfg, acfg, store_question, clean_question, intervention_impact, intervened_answer)

    store_question, clean_question, intervened_answer = add_sa_test2(cfg, alter_digit)
    success2, _, impact_success2 = run_strong_intervention(cfg, acfg, store_question, clean_question, intervention_impact, intervened_answer)

    success = (success1 and success2) if strong else (impact_success1 and impact_success2)

    if success:
        print( "Test confirmed:", acfg.node_names(), "perform A"+str(alter_digit)+"SA = (D"+str(alter_digit)+" + D'"+str(alter_digit)+") % 10 impacting "+intervention_impact+" accuracy.", "" if strong else "Weak", acfg.intervened_answer)

    return success


# Tag for addition An.ST 
def add_st_tag(focus_digit):
    return "A" + str(focus_digit) + "." + MathsTask.ST_TAG.value


# Prerequisites for addition An.ST 
def add_st_prereqs(cfg, position, focus_digit):
    return FilterAnd(
        FilterHead(),
        FilterPosition(position_name(cfg.n_digits), QCondition.MIN), # Occurs from the operator token
        FilterPosition(position_name(cfg.num_question_positions), QCondition.MAX), # Occurs by the = token
        FilterAttention(cfg.dn_to_position_name(focus_digit)), # Attends to Dn
        FilterAttention(cfg.ddn_to_position_name(focus_digit)), # Attends to D'n
        FilterContains(QType.MATH_ADD, MathsBehavior.ADD_PCA_TAG.value), # Node PCA is interpretable (bigram or trigram output) with respect to addition T8,T9,T10
        FilterContains(QType.MATH_ADD, MathsBehavior.ADD_COMPLEXITY_PREFIX.value), # Impacts addition questions
        FilterPosition(position_name(position))) # Is at token position Px


# Intervention ablation test for addition An.ST with impact "A65432" to "A65" in early tokens.
def add_st_test(cfg, acfg, focus_digit, strong):
    # 222222 + 777977 = 1000188. Has Dn.SC
    store_question = [cfg.repeat_digit(2), cfg.repeat_digit(7)]
    store_question[1] += (9 - 7) * (10 ** focus_digit)

    # 333333 + 666666 = 999999. No Dn.SC
    clean_question = [cfg.repeat_digit(3), cfg.repeat_digit(6)]

    success = run_weak_intervention(cfg, acfg, store_question, clean_question)

    if success:
        description = acfg.node_names() + " perform D"+str(focus_digit)+".ST = TriCase(D"+str(focus_digit)+" + D'"+str(focus_digit)+")"
        print("Test confirmed", description, "Impact:", acfg.intervened_impact, "" if strong else "Weak")

    return success


# Tag for positive-answer subtraction "Difference" (MD) tasks e.g. 666666-222222=+0444444 where D3 >= D'3
def sub_md_tag(impact_digit):
    return answer_name(impact_digit) + "." + MathsTask.MD_TAG.value


# Prerequisites for positive-answer subtraction "Difference" (MD) tasks 
def sub_md_prereqs(cfg, position, impact_digit):
    # Pays attention to Dn and D'n. Impacts An
    return math_common_prereqs(cfg, position, impact_digit, impact_digit)


def sub_md_test1(cfg, alter_digit):
    # 333333 - 111111 = +222222. No Dn.MB
    store_question = [cfg.repeat_digit(3), cfg.repeat_digit(1)]

    # 999999 - 444444 = +555555. No DN.MB
    clean_question = [cfg.repeat_digit(9), cfg.repeat_digit(4)]

    # When we intervene we expect answer +555255
    intervened_answer = clean_question[0] - clean_question[1] + (2-5) * 10 ** alter_digit

    return store_question, clean_question, intervened_answer


def sub_md_test2(cfg, alter_digit):
    # 666666 - 222222 = +444444. No DN.MB
    store_question = [cfg.repeat_digit(6), cfg.repeat_digit(2)]

    # 999999 - 333333 = +666666. No DN.MB
    clean_question = [cfg.repeat_digit(9), cfg.repeat_digit(3)]

    # When we intervene we expect answer +666466
    intervened_answer = clean_question[0] - clean_question[1] + (4-6) * 10 ** alter_digit

    return store_question, clean_question, intervened_answer


# Intervention ablation test for positive-answer subtraction "Difference" (MD) tasks 
def sub_md_test(cfg, acfg, alter_digit, strong):
    # Note: MD and SA give the same result when D'=0 or D=D'=5. We avoid ablation tests like this.
    
    intervention_impact = answer_name(alter_digit)

    store_question, clean_question, intervened_answer = sub_md_test1(cfg, alter_digit)
    success1, _, impact_success1 = run_strong_intervention(cfg, acfg, store_question, clean_question, intervention_impact, intervened_answer)

    store_question, clean_question, intervened_answer = sub_md_test2(cfg, alter_digit)
    success2, _, impact_success2 = run_strong_intervention(cfg, acfg, store_question, clean_question, intervention_impact, intervened_answer)

    success = (success1 and success2) if strong else (impact_success1 and impact_success2)

    if success:
        print( "Test confirmed", acfg.node_names(), "perform A"+str(alter_digit)+".MD = (D"+str(alter_digit)+" + D'"+str(alter_digit)+") % 10 impacting "+intervention_impact+" accuracy.", "" if strong else "Weak")

    return success


# Tag for positive-answer subtraction "Borrow One" (MB) task e.g. 222222-111311=+0110911 where D2 > D'2
def sub_mb_tag(impact_digit):
    return answer_name(impact_digit-1)  + "." + MathsTask.MB_TAG.value    


# Prerequisites for positive-answer subtraction "Borrow One" (MB) task
def sub_mb_prereqs(cfg, position, impact_digit):
    # Pays attention to Dn-1 and D'n-1. Impacts An    
    return math_common_prereqs(cfg,  position, impact_digit-1, impact_digit)


# Intervention ablation test for positive-answer subtraction "Borrow One" (MB) task
def sub_mb_test(cfg, acfg, impact_digit, strong):
    alter_digit = impact_digit - 1

    if alter_digit < 0 or alter_digit >= cfg.n_digits:
        acfg.reset_intervention()
        return False

    intervention_impact = answer_name(impact_digit)

    # 222222 - 111311 = +0110911. Has Dn.MB
    store_question = [cfg.repeat_digit(2), cfg.repeat_digit(1)]
    store_question[1] += (3 - 1) * (10 ** alter_digit)

    # 777777 - 444444 = +0333333. No Dn.MB
    clean_question = [cfg.repeat_digit(7), cfg.repeat_digit(4)]

    # When we intervene we expect answer +0332333
    intervened_answer = clean_question[0] - clean_question[1] - 10 ** (alter_digit+1)

    success, _, _ = run_strong_intervention(cfg, acfg, store_question, clean_question, intervention_impact, intervened_answer)

    if success:
        print( "Test confirmed", acfg.node_names(), "perform A"+str(alter_digit)+".MB impacting "+intervention_impact+" accuracy.", "" if strong else "Weak")
        
    return success


# Tag for positive-answer subtraction "TriCase" task "MT"
def sub_mt_tag(impact_digit):
    return answer_name(impact_digit)  + "." + MathsTask.MT_TAG.value


def sub_mt_prereqs(cfg, position, focus_digit):
    return FilterAnd(
        FilterHead(),
        FilterPosition(position_name(cfg.n_digits), QCondition.MIN), # Occurs in early tokens
        FilterPosition(position_name(cfg.num_question_positions), QCondition.MAX), # Occurs in early tokens   
        FilterAttention(cfg.dn_to_position_name(focus_digit)), # Attends to Dn
        FilterAttention(cfg.ddn_to_position_name(focus_digit)), # Attends to D'n
        FilterContains(QType.MATH_SUB, MathsBehavior.SUB_PCA_TAG.value), # Node PCA is interpretable (bigram or trigram output) with respect to subtraction T8,T9,T10
        FilterContains(QType.MATH_SUB, MathsBehavior.SUB_COMPLEXITY_PREFIX.value), # Impacts positive-answer questions (cover M1 to M4)
        FilterPosition(position_name(position)))


# Test that if we ablate this node then a negative-answer-subtraction question answer swaps to its positive complement
def sub_mt_test(cfg, acfg, focus_digit, strong):

    if focus_digit >= cfg.n_digits:
        acfg.reset_intervention()
        return False

    # 555555 - 000000 = +0555555. Is a positive-answer-subtraction
    store_question = [cfg.repeat_digit(5), cfg.repeat_digit(0)]

    # 222222 - 222422 = -0000200. Is a negative-answer-subtraction question because of focus_digit
    clean_question = [cfg.repeat_digit(2), cfg.repeat_digit(2)]
    clean_question[1] += 2 * (10 ** focus_digit)

    success = run_weak_intervention(cfg, acfg, store_question, clean_question)

    if success:
        print("Test confirmed", acfg.node_names(), " perform D"+str(focus_digit)+".MT", "Impact:", acfg.intervened_impact, "" if strong else "Weak")

    return success


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


# Negative-answer subtraction "Difference" (ND) task tag
def neg_nd_tag(impact_digit):
    return answer_name(impact_digit) + "." + MathsTask.ND_TAG.value


# These rules are prerequisites for (not proof of) a Neg Difference node
def neg_nd_prereqs(cfg, position, impact_digit):
    # Impacts An and pays attention to Dn and D'n
    return math_common_prereqs(cfg, position, impact_digit, impact_digit)


def neg_nd_test1(cfg, acfg, alter_digit):
    # 033333 - 111111 = -077778. No Dn.NB
    store_question = [cfg.repeat_digit(3), cfg.repeat_digit(1)]
    store_question[0] = store_question[0] // 10 # Convert 333333 to 033333

    # 099999 - 444444 = -344445. No Dn.NB
    clean_question = [cfg.repeat_digit(9), cfg.repeat_digit(4)]
    clean_question[0] = clean_question[0] // 10 # Convert 999999 to 099999

    # When we intervene we expect answer -347445
    intervened_answer = clean_question[0] - clean_question[1] - (7-4) * 10 ** alter_digit

    # Unit test
    if cfg.n_digits == 6 and alter_digit == 3:
        assert store_question[0] == 33333
        assert clean_question[0] == 99999
        assert clean_question[0] - clean_question[1] == -344445
        assert intervened_answer == -347445

    return store_question, clean_question, intervened_answer


def neg_nd_test2(cfg, acfg, alter_digit):
    # 066666 - 222222 = -155556. No Dn.NB
    store_question = [cfg.repeat_digit(6), cfg.repeat_digit(2)]
    store_question[0] = store_question[0] // 10 # Remove top digit

    # 099999 - 333333 = -233334. No Dn.NB
    clean_question = [cfg.repeat_digit(9), cfg.repeat_digit(3)]
    clean_question[0] = clean_question[0] // 10 # Remove top digit

    # When we intervene we expect answer -231334
    intervened_answer = clean_question[0] - clean_question[1] - (5-3) * 10 ** alter_digit

    return store_question, clean_question, intervened_answer


# Negative-answer subtraction "Difference" (ND) task ablation test
def neg_nd_test(cfg, acfg, alter_digit, strong):
    intervention_impact = answer_name(alter_digit)

    store_question, clean_question, intervened_answer = neg_nd_test1(cfg, acfg, alter_digit)
    success1, _, impact_success1 = run_strong_intervention(cfg, acfg, store_question, clean_question, intervention_impact, intervened_answer)

    store_question, clean_question, intervened_answer = neg_nd_test2(cfg, acfg, alter_digit)
    success2, _, impact_success2 = run_strong_intervention(cfg, acfg, store_question, clean_question, intervention_impact, intervened_answer)

    success = (success1 and success2) if strong else (impact_success1 and impact_success2)

    if success:
        print( "Test confirmed", acfg.node_names(), "perform A"+str(alter_digit)+".ND = (D"+str(alter_digit)+" + D'"+str(alter_digit)+") % 10 impacting "+intervention_impact+" accuracy.", "" if strong else "Weak")

    return success


# Negative-answer subtraction "Borrow One" (NB) task tag
def neg_nb_tag(impact_digit):
    return answer_name(impact_digit) + "." + MathsTask.NB_TAG.value


# Prerequisites for negative-answer subtraction "Borrow One" (NB) task
def neg_nb_prereqs(cfg, position, impact_digit):
    # Pays attention to Dn-1 and D'n-1. Impacts An
    return math_common_prereqs(cfg,  position, impact_digit-1, impact_digit)


# Intervention ablation test for negative-answer subtraction "Borrow One" (NB) task
def neg_nb_test(cfg, acfg, impact_digit, strong):
    alter_digit = impact_digit - 1

    if alter_digit < 0 or alter_digit >= cfg.n_digits:
        acfg.reset_intervention()
        return False

    intervention_impact = answer_name(impact_digit)

    # 022222 - 111311 = -0089089. Has Dn.MB
    store_question = [cfg.repeat_digit(2), cfg.repeat_digit(1)]
    store_question[0] = store_question[0] // 10 # Convert 222222 to 022222
    store_question[1] += (3 - 1) * (10 ** alter_digit)

    # 077777 - 444444 = -0366667. No Dn.MB
    clean_question = [cfg.repeat_digit(7), cfg.repeat_digit(4)]
    clean_question[0] = clean_question[0] // 10 # Convert 777777 to 077777

    # When we intervene we expect answer -0366677
    intervened_answer = clean_question[0] - clean_question[1] - 10 ** (alter_digit+1)

    success, _, _ = run_strong_intervention(cfg, acfg, store_question, clean_question, intervention_impact, intervened_answer)

    if success:
        print( "Test confirmed", acfg.node_names(), "perform A"+str(alter_digit)+".NB impacting "+intervention_impact+" accuracy.", "" if strong else "Weak")

    return success