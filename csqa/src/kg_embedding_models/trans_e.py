import torch
import torch.nn as nn
from torch.autograd import Variable

"""Implementation is based on https://github.com/thunlp/OpenKE/blob/OpenKE-PyTorch/models/TransE.py"""

class TransE(nn.Module):

    def __init__(self, vocab_size, embedding_dim, margin_loss):
        super(TransE, self).__init__()
        # A simple lookup table that stores embeddings of a fixed dictionary and size
        self.embeddings = nn.Embedding(vocab_size, embedding_dim)
        self.margin_loss = margin_loss

    def loss_fct(self, pos_score, neg_score):
        """

        :param pos_score:
        :param neg_score:
        :return:
        """
        criterion = nn.MarginRankingLoss(margin=self.margin_loss, size_average=False)
        # y == -1 indicates that second input to criterion should get a larger loss
        y = Variable(torch.Tensor([-1]), requires_grad=True)
        loss = criterion(pos_score, neg_score, y)

        return loss

    def calc_score(self, h_emb, r_emb, t_emb):
        """

        :param h_emb:
        :param r_emb:
        :param t_emb:
        :return:
        """
        # TODO: - torch.abs(h_emb + r_emb - t_emb) or + torch.abs(h_emb + r_emb - t_emb) ??
        return torch.sum(torch.abs(h_emb + r_emb - t_emb))

    def predict(self, head, relation, tail):
        """

        :param head:
        :param relation:
        :param tail:
        :return:
        """
        head_emb = self.embeddings(head)
        relation_emb = self.embeddings(relation)
        tail_emb = self.embeddings(tail)

        score = self.calc_score(h_emb=head_emb, r_emb=relation_emb, t_emb=tail_emb)

        return score

    def forward(self, pos_exmpl, neg_exmpl):
        """

        :param pos_exmpl:
        :param neg_exmpl:
        :return:
        """
        pos_h, pos_r, pos_t = pos_exmpl
        neg_h, neg_r, neg_t, = neg_exmpl

        pos_h_emb = self.embeddings(torch.tensor([pos_h], dtype=torch.long))
        pos_r_emb = self.embeddings(torch.tensor([pos_r], dtype=torch.long))
        pos_t_emb = self.embeddings(torch.tensor([pos_t], dtype=torch.long))

        neg_h_emb = self.embeddings(torch.tensor([neg_h], dtype=torch.long))
        neg_r_emb = self.embeddings(torch.tensor([neg_r], dtype=torch.long))
        neg_t_emb = self.embeddings(torch.tensor([neg_t], dtype=torch.long))

        pos_score = self.calc_score(h_emb=pos_h_emb, r_emb=pos_r_emb, t_emb=pos_t_emb)
        neg_score = self.calc_score(h_emb=neg_h_emb, r_emb=neg_r_emb, t_emb=neg_t_emb)

        loss = self.loss_fct(pos_score=Variable(torch.tensor([pos_score]), requires_grad=True),
                             neg_score=Variable(torch.tensor([neg_score]), requires_grad=True))

        return loss
