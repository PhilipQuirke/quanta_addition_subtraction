import torch
from tqdm.notebook import tqdm
from QuantaMechInterp import (to_numpy, tokens_to_string, logits_to_tokens_loss, get_question_answer_impact, sort_unique_digits, NodeLocation, a_predict_questions, loss_fn, QType)
from MathsMechInterp.maths_complexity import get_maths_question_complexity
from MathsMechInterp.maths_constants import MathsToken, MathsBehavior, maths_tokens_to_names
from MathsMechInterp.maths_data_generator import maths_data_generator


def test_maths_questions_by_complexity(cfg, acfg, varied_questions):
    # Test maths question prediction accuracy on the sample questions provided.
    # Does NOT use acfg.* or UsefulInfo.* information
    # Used to estimate the accuracy of the model's predictions.
    # Returns a reduced set of questions - removing questions that the model failed to answer.

    num_questions = varied_questions.shape[0]
    correct_list = [True] * num_questions

    all_logits = cfg.main_model(varied_questions.cuda())
    _, all_max_prob_tokens = logits_to_tokens_loss(cfg, all_logits, varied_questions.cuda())


    # Evaluate and categorize each object
    categorization_results = {}
    for question_num in range(num_questions):
        q_and_a = varied_questions[question_num]

        # Get the last cfg.num_answer_positions tokens in the q_and_a, which is the correct answer
        correct_answer_str = tokens_to_string(cfg, q_and_a[-cfg.num_answer_positions:])

        model_answer_str = tokens_to_string(cfg, all_max_prob_tokens[question_num])

        correct = (model_answer_str == correct_answer_str)
        correct_list[question_num] = correct

        major_tag, minor_tag = get_maths_question_complexity(cfg, q_and_a)
        group_name = major_tag.value + "." + minor_tag.value

        if group_name not in categorization_results:
            categorization_results[group_name] = [0, 0]  # Initialize counts for new group

        if correct:
            categorization_results[group_name][0] += 1  # Increment good count for this group
        else:
            categorization_results[group_name][1] += 1  # Increment bad count for this group

        if acfg.show_test_failures and not correct:
            q_and_a_str = tokens_to_string(cfg, q_and_a)
            print("Failed: Q&A:", q_and_a_str, "ModelAnswer:", model_answer_str, "Complexity:", group_name)


    # Calculate and print summary success rates per group
    acfg.num_varied_questions = 0
    acfg.num_varied_successes = 0
    for group_name, counts in categorization_results.items():
        total = sum(counts)
        success_rate = counts[0] / total * 100 if total != 0 else 0
        print(f"Group {group_name}: Success Rate = {success_rate:.2f}% ({counts[0]} good, {counts[1]} bad)")
        acfg.num_varied_questions += total
        acfg.num_varied_successes += counts[0]


    acfg.print_prediction_success_rate()
    if acfg.num_varied_successes < acfg.num_varied_questions:
        # Remove the questions that the model failed to answer as they turn up in every cell of the quanta maps
        org_size = varied_questions.shape[0]
        varied_questions = varied_questions[torch.tensor(correct_list)]
        new_size = varied_questions.shape[0]
        print("NEXT STEP: Understand the failure case(s). Enrich the training data to provide more examples. Retrain the model.")
        print("WORKAROUND: Have reduced 'varied_questions' size from", org_size, "to", new_size, "so can continue.")

    return varied_questions


def test_maths_questions_by_impact(cfg, acfg, questions, position : int, ablate : bool ):
    # Test accuracy of model in predicting question answers. Ablates all nodes at position
    # Does NOT use UsefulInfo.* information. Used to populate UsefulInfo.useful_positions

    the_hooks = acfg.resid_put_hooks if ablate else None
    if ablate:
        assert not (the_hooks == None)

    acfg.ablate_node_locations = [NodeLocation(position, 0, True, 0)]  # Ablate all nodes at position
    all_losses_raw, all_max_prob_tokens = a_predict_questions(cfg, questions, the_hooks)

    num_fails = 0
    for question_num in range(questions.shape[0]):
        q = questions[question_num]
        assert q.shape[0] == cfg.n_ctx # Check answer is embedded in question

        the_loss_mean = to_numpy(loss_fn(all_losses_raw[question_num]).mean())

        # Only show the question if the loss exceeds the threshold (because of the ablated token position)
        if the_loss_mean > acfg.threshold:

            answer_str = tokens_to_string(cfg, all_max_prob_tokens[question_num])

            # Only count the question if the model got the question wrong
            impact_str = get_question_answer_impact(cfg, q, answer_str )
            if 'A' in impact_str:
                num_fails += 1

                if acfg.show_test_failures:
                    print(tokens_to_string(cfg, q), "ModelAnswer:", answer_str, "Impact:", impact_str, "Loss:", format(the_loss_mean, ".4f"))

    return num_fails


def test_maths_questions_and_add_useful_node_tags(cfg, acfg, questions, node_location, all_losses_raw, all_max_prob_tokens):
    # Test accuracy of model in predicting question answers, when a single node is ablated.
    # Adds nodes to Useful.useful_nodes and adds tags to those nodes.

    num_fails = 0
    impact_fails = ""
    add_complexity_fails = ""
    sub_complexity_fails = ""
    neg_complexity_fails = ""

    for question_num in range(questions.shape[0]):
        q = questions[question_num]

        the_loss_mean = to_numpy(loss_fn(all_losses_raw[question_num]).mean())

        # Only show the question if the loss exceeds the threshold (because of the ablated token position)
        if the_loss_mean > acfg.threshold:
            answer_str = tokens_to_string(cfg, all_max_prob_tokens[question_num])

            impact_str = get_question_answer_impact(cfg, q, answer_str )
            # Only count the question if the model got the question wrong
            if 'A' in impact_str:
                num_fails += 1

                impact_fails += impact_str

                major_tag, minor_tag = get_maths_question_complexity(cfg, q)
                if major_tag == QType.MATH_ADD:
                    add_complexity_fails += minor_tag.value
                elif major_tag == QType.MATH_SUB:
                    sub_complexity_fails += minor_tag.value
                elif major_tag == QType.MATH_NEG:
                    neg_complexity_fails += minor_tag.value

                if acfg.show_test_failures :
                    print(tokens_to_string(cfg, q), "U: ModelAnswer:", answer_str, "Complexity:", major_tag, "Impact:", impact_str, "Loss:", the_loss_mean )

    if num_fails > 0:

        # Add percentage failure quanta
        perc = int( 100.0 * num_fails / len(questions))
        cfg.add_useful_node_tag( node_location, QType.FAIL.value, str(perc) )

        # Add summary of all answer digit impact quanta failures
        cfg.add_useful_node_tag( node_location, QType.IMPACT.value, "A" + sort_unique_digits(impact_fails, True) )

        # Add summary of all addition question complexity quanta failures
        if add_complexity_fails != "":
            cfg.add_useful_node_tag( node_location, QType.MATH_ADD.value, MathsBehavior.ADD_COMPLEXITY_PREFIX.value + sort_unique_digits(add_complexity_fails, False) )

        # Add summary of all subtraction question complexity quanta failures
        if sub_complexity_fails != "":
            cfg.add_useful_node_tag( node_location, QType.MATH_SUB.value, MathsBehavior.SUB_COMPLEXITY_PREFIX.value + sort_unique_digits(sub_complexity_fails, False) )
        if neg_complexity_fails != "":
            cfg.add_useful_node_tag( node_location, QType.MATH_NEG.value, MathsBehavior.NEG_COMPLEXITY_PREFIX.value + sort_unique_digits(neg_complexity_fails, False) )


def test_correctness_on_num_questions(cfg, acfg, num_questions=1000000, enrich_data=True):
    store_perc_sub = cfg.perc_sub
    store_perc_mult = cfg.perc_mult

    def print_config():
        print("%Add=", cfg.perc_add, "%Sub=", cfg.perc_sub, "%Mult=", cfg.perc_mult, "File", cfg.file_config_prefix)

    print_config()
    print()

    if cfg.perc_add > 0:
        print("Addition:")
        cfg.perc_sub = 0
        cfg.perc_mult = 0
        test_correctness_on_num_questions_core(cfg, acfg, num_questions=num_questions, enrich_data=enrich_data)

    if store_perc_sub > 0:
        print("Subtraction:")
        cfg.perc_sub = 100
        cfg.perc_mult = 0
        test_correctness_on_num_questions_core(cfg, acfg, num_questions=num_questions, enrich_data=enrich_data)
        print()

    cfg.perc_sub = store_perc_sub
    cfg.perc_mult = store_perc_mult


def test_correctness_on_num_questions_core(cfg, acfg, num_questions=1000000, enrich_data=True):
    old_seed = cfg.analysis_seed

    # Create a local data generator
    cfg.analysis_seed = 345621  # Randomly chosen
    assert( cfg.analysis_seed != cfg.training_seed ) # Must be ifferent from training
    local_ds = maths_data_generator(cfg=cfg, enrich_data=enrich_data)  

    the_successes = 0
    the_fails = 0

    num_batches = 1 + ( num_questions//cfg.batch_size )
    for epoch in tqdm(range(num_batches)):
        tokens = next(local_ds)

        the_fails += test_maths_questions_by_impact(cfg, acfg, tokens, 0, False)

        the_successes = the_successes + cfg.batch_size

        if epoch % 100 == 0:
            print("Batch", epoch, "of", num_batches, "#Successes=", the_successes, "#Fails=", the_fails)

    print("successes", the_successes, "num_fails", the_fails)
    if num_questions == 1000000:
        if the_fails <= 1:
            print("Model has six 9s accuracy") # 99.9999%
        elif the_fails <= 10:
            print("Model has five 9s accuracy") # 99.999%
        elif the_fails <= 100:
            print("Model has four 9s accuracy") # 99.99%
        elif the_fails <= 1000:
            print("Model has three 9s accuracy") # 99.9%
        elif the_fails <= 10000:
            print("Model has two 9s accuracy") # 99%
            
    cfg.analysis_seed = old_seed