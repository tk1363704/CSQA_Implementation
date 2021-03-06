import logging
import os
import pickle
import time
import unittest
from collections import OrderedDict

import numpy as np
import tensorflow as tf

from neural_network_models.csqa_network import CSQANetwork
from utilities.constants import NUM_UNITS_HRE_UTTERANCE_CELL, NUM_UNITS_HRE_CONTEXT_CELL, NUM_HOPS, WORD_VEC_DIM, \
    ENCODER_VOCABUALRY_SIZE, DECODER_VOCABUALRY_SIZE, LEARNING_RATE, OPTIMIZER, MAX_NUM_UTTER_TOKENS, ADAM, \
    ENCODER_NUM_TRAINABLE_TOKENS, DECODER_NUM_TRAINABLE_TOKENS, BATCH_SIZE, KG_WORD, KG_WORD_ID, TOKEN_IDS, \
    TARGET_SOS_ID, EOS_TOKEN, SOS_TOKEN, TARGET_EOS_ID, \
    CANDIDATE_RESPONSE_ENTITIES_PROBABILITIES, CANDIDATE_RESPONSE_ENTITIES, QUES_TYPES, CSQA_QUESTION_TYPE
from utilities.corpus_preprocessing_utils.load_dialogues import load_data_from_json_file
from utilities.general_utils import load_dict_from_disk
from utilities.instance_creation_utils.dialogue_instance_creator import DialogueInstanceCreator
from utilities.prediction_utils import replace_kg_tokens_with_predicted_entities

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class TestCSQANetwork(unittest.TestCase):

    def setUp(self):
        # Paths to resources
        path_to_context_vocab_dict = '../test_resources/csqa_vocab_context_vocab_5.pkl'
        path_to_vocab_response_dict = '../test_resources/csqa_vocab_response_vocab_5.pkl'
        path_to_entity_id_to_label_mapping = '../test_resources/filtered_entity_mapping.json'
        path_to_property_id_to_label_mapping = '../test_resources/filtered_property_mapping.json'
        path_to_word_vec_model = '../test_resources/test_soccer_word_to_vec'
        path_to_kg_entity_embeddings = '../test_resources/kg_entity_to_embeddings.pkl'
        path_to_kg_relation_embeddings = '../test_resources/kg_relations_to_embeddings.pkl'
        path_to_wikidata_triples = '../test_resources/example_wikidata_triples_reduced.csv'
        self.dialogue_input_path = '../test_resources/example_dialogue.json'

        # Configure 'DialogueInstanceCreator'
        self.max_num_utter_tokens = 10
        max_dialogue_context_length = 2
        word_to_vec_model_dict = dict()
        word_to_vec_model_dict['Path'] = path_to_word_vec_model
        word_to_vec_model_dict['is_c_format'] = False
        word_to_vec_model_dict['is_binary'] = False
        ctx_vocab_freq_dict = load_dict_from_disk(path_to_dict=path_to_context_vocab_dict)
        response_vocab_freq_dict = load_dict_from_disk(path_to_dict=path_to_vocab_response_dict)

        self.instance_creator = DialogueInstanceCreator(max_num_utter_tokens=self.max_num_utter_tokens,
                                                        max_dialogue_context_length=max_dialogue_context_length,
                                                        path_to_entity_id_to_label_mapping=path_to_entity_id_to_label_mapping,
                                                        path_to_property_id_to_label_mapping=path_to_property_id_to_label_mapping,
                                                        ctx_vocab_freq_dict=ctx_vocab_freq_dict,
                                                        response_vocab_freq_dict=response_vocab_freq_dict,
                                                        word_to_vec_dict=word_to_vec_model_dict,
                                                        path_to_kb_entities_embeddings=path_to_kg_entity_embeddings,
                                                        path_to_wikidata_triples=path_to_wikidata_triples,
                                                        seed=2,
                                                        min_count_n_gram_matching=5)

        self.ctx_embeddings = np.array(list(self.instance_creator.ctx_token_to_embeddings.values()), dtype=np.float32)
        self.response_embeddings = np.array(list(self.instance_creator.response_token_to_embeddings.values()),
                                            dtype=np.float32)

        self.ctx_num_trainable_toks = self.instance_creator.ctx_num_trainable_toks
        self.response_num_trainable_toks = self.instance_creator.response_num_trainable_toks
        self.kg_entity_to_embeddings_dict = None
        self.kg_relation_to_embeddings_dict = None

        with open(path_to_kg_entity_embeddings, 'rb') as f:
            self.kg_entity_to_embeddings_dict = pickle.load(f)

        with open(path_to_kg_relation_embeddings, 'rb') as f:
            self.kg_relation_to_embeddings_dict = pickle.load(f)

        self.kg_entity_to_embeddings = np.array(list(self.kg_entity_to_embeddings_dict.values()), dtype=np.float32)
        self.kg_relations_embeddings = np.array(list(self.kg_relation_to_embeddings_dict.values()), dtype=np.float32)

        # Define model parameters
        self.model_params = OrderedDict()
        self.model_params[NUM_UNITS_HRE_UTTERANCE_CELL] = 15
        self.model_params[NUM_UNITS_HRE_CONTEXT_CELL] = 5
        self.model_params[NUM_HOPS] = 2
        self.model_params[WORD_VEC_DIM] = 100
        self.model_params[ENCODER_VOCABUALRY_SIZE] = len(self.ctx_embeddings)
        self.model_params[DECODER_VOCABUALRY_SIZE] = len(self.response_embeddings)
        self.model_params[LEARNING_RATE] = 0.01
        self.model_params[OPTIMIZER] = ADAM
        self.model_params[MAX_NUM_UTTER_TOKENS] = self.max_num_utter_tokens
        self.model_params[ENCODER_NUM_TRAINABLE_TOKENS] = self.ctx_num_trainable_toks
        self.model_params[DECODER_NUM_TRAINABLE_TOKENS] = self.response_num_trainable_toks
        self.model_params[BATCH_SIZE] = 1
        self.model_params[KG_WORD_ID] = self.instance_creator.response_word_to_id[KG_WORD]
        self.model_params[TARGET_SOS_ID] = self.instance_creator.response_word_to_id[SOS_TOKEN]
        self.model_params[TARGET_EOS_ID] = self.instance_creator.response_word_to_id[EOS_TOKEN]

    def test_initialize_model(self):
        current_time = time.strftime("%H:%M:%S")
        current_date = time.strftime("%d/%m/%Y").replace('/', '-')
        output_dir = '../test_resources/test_out'
        output_dir += '/' + current_date + '_' + current_time + ''
        os.makedirs(output_dir)

        nn_model = CSQANetwork(kg_entity_embeddings=list(self.kg_entity_to_embeddings_dict.values()),
                               kg_relations_embeddings=list(self.kg_relation_to_embeddings_dict.values()),
                               initial_encoder_embeddings=self.ctx_embeddings,
                               initial_decoder_embeddings=self.response_embeddings)

    def test_train_mode(self):
        current_time = time.strftime("%H:%M:%S")
        current_date = time.strftime("%d/%m/%Y").replace('/', '-')
        output_dir = '../test_resources/test_out'
        output_dir += '/' + current_date + '_' + current_time + ''
        os.makedirs(output_dir, exist_ok=True)

        file_id = 'example_dialogue.json'
        dialogue = load_data_from_json_file(input_path=self.dialogue_input_path)

        instances_of_dialogue, target_inst, relevant_kg_triples = self.instance_creator.create_training_instances(
            dialogue=dialogue, file_id=file_id)
        dialogues = [instances_of_dialogue]
        relevant_kg_triples = np.expand_dims(relevant_kg_triples, axis=0)
        responses = [target_inst]

        nn_model = CSQANetwork(kg_entity_embeddings=self.kg_entity_to_embeddings,
                               kg_relations_embeddings=self.kg_relations_embeddings,
                               initial_encoder_embeddings=self.ctx_embeddings,
                               initial_decoder_embeddings=self.response_embeddings)

        logging_hook = tf.train.LoggingTensorHook(
            ['compute_entites_in_response/probabilities_response_candidate_entities', 'decoder/logits',
             'embedded_subjs'],
            every_n_iter=10)
        nn_estimator = tf.estimator.Estimator(model_fn=nn_model.model_fct, params=self.model_params,
                                              model_dir=output_dir, config=None)

        nn_estimator.train(input_fn=lambda: nn_model.input_fct(dialogues=dialogues, responses=responses,
                                                               relevant_kg_triples=relevant_kg_triples,
                                                               batch_size=1), steps=100, hooks=[logging_hook])

    def test_predict_mode(self):
        current_time = time.strftime("%H:%M:%S")
        current_date = time.strftime("%d/%m/%Y").replace('/', '-')
        output_dir = '../test_resources/test_out'
        output_dir += '/' + current_date + '_' + current_time + ''
        os.makedirs(output_dir, exist_ok=True)

        file_id = 'example_dialogue.json'
        dialogue = load_data_from_json_file(input_path=self.dialogue_input_path)

        instances_of_dialogue, target_inst, relevant_kg_triples = self.instance_creator.create_training_instances(
            dialogue=dialogue, file_id=file_id)

        dialogues = [instances_of_dialogue]

        relevant_kg_triples = np.expand_dims(relevant_kg_triples, axis=0)
        responses = [target_inst]

        nn_model = CSQANetwork(kg_entity_embeddings=self.kg_entity_to_embeddings,
                               kg_relations_embeddings=self.kg_relations_embeddings,
                               initial_encoder_embeddings=self.ctx_embeddings,
                               initial_decoder_embeddings=self.response_embeddings)

        print("dict: ", self.kg_entity_to_embeddings_dict)

        logging_hook = tf.train.LoggingTensorHook(
            ['embedded_subjs', 'subjects_i'],
            every_n_iter=10)

        nn_estimator = tf.estimator.Estimator(model_fn=nn_model.model_fct, params=self.model_params,
                                              model_dir=output_dir, config=None)

        nn_estimator.train(input_fn=lambda: nn_model.input_fct(dialogues=dialogues, responses=responses,
                                                               relevant_kg_triples=relevant_kg_triples,
                                                               batch_size=1), steps=100, hooks=[logging_hook])

        prediction_generator = nn_estimator.predict(
            input_fn=nn_model.input_pred_fct(dialogues=dialogues, relevant_kg_triples=relevant_kg_triples))

        print("KG TOKEN: ", self.model_params[KG_WORD_ID])
        predicted_utterances = []
        pred_prob_entities = []
        candidate_entities = []

        for i, p in enumerate(prediction_generator):
            predicted_utterances.append(p[TOKEN_IDS])
            pred_prob_entities.append(p[CANDIDATE_RESPONSE_ENTITIES_PROBABILITIES])
            candidate_entities.append(p[CANDIDATE_RESPONSE_ENTITIES])
            print(p[QUES_TYPES])

            # print(p[LOGITS])
            # print(p[WORD_PROBABILITIES])
            # print(p[CANDIDATE_RESPONSE_ENTITIES_PROBABILITIES])
            # print(p[CANDIDATE_RESPONSE_ENTITIES][i])
            # entiy_integrated = replace_kg_tokens_with_predicted_entities(predicted_tok_ids=predicted_tok_id,
            #                                                              predicted_entities=predicted_entities,
            #                                                              pred_prob_entities=pred_prob_entities,
            #                                                              kg_tok_id=self.model_params[KG_WORD_ID])

            # print(predicted_tok_id)
            # print(entiy_integrated)

        word_to_id = self.instance_creator.response_word_to_id
        response_word_id_to_word = {value: key for key, value in word_to_id.items()}

        kg_entity_to_id = self.instance_creator.entity_to_id
        id_to_kg_entity = {value: key for key, value in kg_entity_to_id.items()}

        predicted_utterances = np.array(predicted_utterances)

        for i, pred_utter in enumerate(predicted_utterances ):
            merged_utter, pred_entites = replace_kg_tokens_with_predicted_entities(predicted_toks=pred_utter,
                                                                         predicted_entities=candidate_entities[i],
                                                                         pred_prob_entities=pred_prob_entities[i],
                                                                         kg_tok=4,
                                                                         kg_id_to_kg_entity=id_to_kg_entity,
                                                                         response_tok_id_to_word=response_word_id_to_word)
            print(merged_utter)
            print(pred_entites)
