import math
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score


class LogisticRegressionEmbedModel:
    def __init__(self, penalty):
        self.logistic_reg = LogisticRegression(max_iter=5000, penalty=penalty, solver='saga')
        self.embeds = dict()
        self.embeds = dict()
        self.load_embeds()

    def load_embeds(self):
        with open('data/glove.6B.50d.txt', 'r+', encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                word = parts[0]
                embedding = np.asarray(parts[1:], dtype=np.float32)
                self.embeds[word] = embedding

    def get_embed(self, word):
        if word in self.embeds:
            return self.embeds[word]
        return self.embeds['<unk>']

    def to_X_embed(self, X_data):
        X_each_word_embed = [[self.get_embed(word) for word in sentence]
                             for sentence in X_data]
        X_aggregate = [np.mean(vect_list, axis=0) for vect_list in X_each_word_embed]
        return X_aggregate

    def train(self, X_train, y_train):
        X_train_embed = self.to_X_embed(X_train)
        self.logistic_reg.fit(X_train_embed, y_train)

    def predict(self, X_test):
        X_test_embed = self.to_X_embed(X_test)
        return self.logistic_reg.predict(X_test_embed)


def roc_auc_score_multiclass(actual_class, pred_class, average="macro"):
    """
        Source: https://stackoverflow.com/questions/39685740/
                calculate-sklearn-roc-auc-score-for-multi-class
    """
    unique_class = set(actual_class)
    roc_auc_dict = {}
    for per_class in unique_class:
        other_class = [x for x in unique_class if x != per_class]
        new_actual_class = [0 if x in other_class else 1 for x in actual_class]
        new_pred_class = [0 if x in other_class else 1 for x in pred_class]
        roc_auc = roc_auc_score(new_actual_class, new_pred_class, average = average)
        roc_auc_dict[per_class] = roc_auc
    return roc_auc_dict


def get_best_params(X_data, y_data):
    from sklearn.model_selection import RepeatedStratifiedKFold
    from sklearn.model_selection import GridSearchCV
    tuning_model = LogisticRegression()
    cv = RepeatedStratifiedKFold(n_splits=10, n_repeats=3, random_state=1)
    space = dict()
    space['solver'] = ['newton-cg', 'lbfgs', 'liblinear', 'sag', 'saga']
    space['penalty'] = ['none', 'l1', 'l2', 'elasticnet']
    space['C'] = [1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1, 10, 100]
    search = GridSearchCV(tuning_model, space, scoring='accuracy', n_jobs=-1, cv=cv)
    X_train_embed = LogisticRegressionEmbedModel(penalty='l1').to_X_embed(X_data)
    result = search.fit(X_train_embed, y_data)
    print('Best Score: %s' % result.best_score_)
    print('Best Hyper-parameters: %s' % result.best_params_)


INDENT = '  '

# Read data
print("Reading data...")
MAX_DATA = 10000
data = pd.read_csv('data/balanced_parsed_data.csv', header=None)
X_data = data[0].tolist()[:MAX_DATA]
y_data = data[1].tolist()[:MAX_DATA]


"""
get_best_params(X_data, y_data)
Best Score: 0.40686666666666665
Best Hyper-parameters: {'C': 100, 'penalty': 'none', 'solver': 'sag'}
"""


# Partition data
part_ratio = (0.7, 0.2, 0.1)
last_train_idx = math.floor(part_ratio[0] * len(X_data))
last_valid_idx = last_train_idx + math.floor(part_ratio[1] * len(X_data))
X_train = X_data[:last_valid_idx]
y_train = y_data[:last_valid_idx]
X_valid = X_data[last_train_idx + 1:last_valid_idx]
y_valid_ans = y_data[last_train_idx + 1:last_valid_idx]
X_test = X_data[last_valid_idx + 1:]
y_test_ans = y_data[last_valid_idx + 1:]

model = LogisticRegressionEmbedModel(penalty='l1')

# Training
print("Training model...")
model.train(X_train, y_train)

# Validation
print("Validating model...")
y_valid_pred = model.predict(X_valid)
valid_score = roc_auc_score_multiclass(y_valid_ans, y_valid_pred)
print("Score on validation: " + str(valid_score))

# Testing
print("Testing model...")
y_test_pred = model.predict(X_test)
test_score = roc_auc_score_multiclass(y_test_ans, y_test_pred)
print("Score on testing: " + str(test_score))

