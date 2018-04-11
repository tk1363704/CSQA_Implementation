import logging

from gensim.models import KeyedVectors

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

from utilities.constants import WORD_VEC_DIM, CSQA_UTTERANCE


class Utterance2TensorCreator(object):
    def __init__(self, max_num_utter_tokens, features_spec_dict, word_to_vec_dict=None, path_to_kb_embeddings=None):
        """
        :param max_num_utter_tokens: Maximum length (in tokens) of an utterance
        :param features_spec_dict: dictionary describing which features to use and their dimension
        :param word_to_vec_dict: Dictionary containing as keys the paths to the word2Vec models. Values indicate
        wheter a model is in binary format or not.
        :param path_to_kb_embeddings: Path to KB embeddings
        """
        if WORD_VEC_DIM in features_spec_dict:
            assert (word_to_vec_dict is not None)

        self.word_to_vec_models = self.load_word_2_vec_models(word_to_vec_dict=word_to_vec_dict)
        self.kg_embeddings_dict = self.load_kg_embeddings(path_to_kb_embeddings=path_to_kb_embeddings)
        self.max_num_utter_tokens = max_num_utter_tokens
        self.features_spec_dict = features_spec_dict

    def load_word_2_vec_models(self, word_to_vec_dict):
        """
        Loads word2Vec models from disk.
        :param word_to_vec_dict: Dictionary containing as keys the paths to the word2Vec models. Values indicate
        wheter a model is in binary format or not.
        :rtype: list
        """
        word_to_vec_models = []

        for current_path, format in word_to_vec_dict.items():
            word_to_vec_models.append(KeyedVectors.load_word2vec_format(current_path, binary=format))

        return word_to_vec_models

    def load_kg_embeddings(self, path_to_kb_embeddings):
        pass

    def create_training_instances(self, dialogue, file_id):
        """
        Computes training instances for a specific dialogue. Call function for each dialogue containd in training set.
        :param dialogue: List containing all utterances of a specific dialogue
        :param file_id: 'directory/filename'. Is needed for mapping.
        :rtype: list
        """
        questions = dialogue[0::2]
        answers = dialogue[1::2]
        assert (len(questions) == len(answers))

        training_instance_dicts = []

        for i in range(len(questions)):
            question = questions[i]
            answer = answers[i]

            # Step 1: Get offsets of utterance-parts based on mentioned entites
            question_offsets_info_dict = self.get_offsets_of_parts_in_utterance(question)
            answer_offsets_info_dict = self.get_offsets_of_parts_in_utterance(answer)

            # Step 2: Compute tensor embedding for utterance
            embedded_question = self.compute_tensor_embedding(utterance_dict=question)
            embedded_answer = self.compute_tensor_embedding(utterance_dict=answer)

            # Step 3: Create training instance
            training_instance_dict = self.create_instance_dict(is_training_instance=True)
            training_instance_dicts.append(training_instance_dict)

        return training_instance_dict



    def get_offsets_of_parts_in_utterance(self, utterance_dict):
        """
        Returns sorted (increasing) offsets of utterance-parts based on mentioned entities
        :param utterance_dict: Dictionary containing all information about passed utterance
        :rtype: dict
        """
        utterance = utterance_dict[CSQA_UTTERANCE]

    def compute_tensor_embedding(self,utterance_dict, utterance_offsets_info_dict):
        pass

    def create_instances_for_prediction(self):
        pass

    def create_instance_dict(self, is_training_instance):
        pass