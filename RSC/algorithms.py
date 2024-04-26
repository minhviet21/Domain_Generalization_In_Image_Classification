import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.autograd as autograd

import numpy as np
import networks 
from hyperparameter import Hyperparameter
hp = Hyperparameter()

class ERM(torch.nn.Module):
    def __init__(self, num_classes, num_domains, hp, train_loader):
        super(ERM, self).__init__()
        self.hp = hp
        self.train_loader = train_loader

        self.featurizer = networks.ResNet(self.hp)
        self.classifier = networks.Classifier(self.featurizer.n_outputs, num_classes,
                                              self.hp.nonlinear_classifier)

        self.network = nn.Sequential(self.featurizer, self.classifier)
        self.optimizer = torch.optim.Adam(self.network.parameters(), lr=self.hp.lr,
                                          weight_decay=self.hp.weight_decay)

    def update(self):
        for images, labels in self.train_loader:
            outputs = self.predict(images)
            loss = F.cross_entropy(outputs, labels)
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()
            return loss.item()

        return loss.item()

    def predict(self, x):
        return self.network(x)

class RSC(ERM):
    def __init__(self, num_classes, num_domains, hp, train_loader):
        super(RSC, self).__init__(num_classes, num_domains, 
                                   hp, train_loader)
        self.drop_f = (1 - hp.rsc_f_drop_factor) * 100
        self.drop_b = (1 - hp.rsc_b_drop_factor) * 100
        self.num_classes = num_classes

    def update(self):
        for images, labels in self.train_loader:
            # one-hot labels
            all_o = torch.nn.functional.one_hot(labels, self.num_classes)
            # features
            all_f = self.featurizer(images)
            # predictions
            all_p = self.classifier(all_f)

            # Equation (1): compute gradients with respect to representation
            all_g = autograd.grad((all_p * all_o).sum(), all_f)[0]

            # Equation (2): compute top-gradient-percentile mask
            percentiles = np.percentile(all_g, self.drop_f, axis=1)
            percentiles = torch.Tensor(percentiles)
            percentiles = percentiles.unsqueeze(1).repeat(1, all_g.size(1))
            mask_f = all_g.lt(percentiles).float()

            # Equation (3): mute top-gradient-percentile activations
            all_f_muted = all_f * mask_f

            # Equation (4): compute muted predictions
            all_p_muted = self.classifier(all_f_muted)

            # Section 3.3: Batch Percentage
            all_s = F.softmax(all_p, dim=1)
            all_s_muted = F.softmax(all_p_muted, dim=1)
            changes = (all_s * all_o).sum(1) - (all_s_muted * all_o).sum(1)
            percentile = np.percentile(changes.detach(), self.drop_b)
            mask_b = changes.lt(percentile).float().view(-1, 1)
            mask = torch.logical_or(mask_f, mask_b).float()

            # Equations (3) and (4) again, this time mutting over examples
            all_p_muted_again = self.classifier(all_f * mask)

            # Equation (5): update
            loss = F.cross_entropy(all_p_muted_again, all_y)
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

        return loss.item()
