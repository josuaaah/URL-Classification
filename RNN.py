from parser import parse
import numpy as np
import pandas as pd
import tensorflow as tf
from keras import layers
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras.models import Sequential
from keras.layers import LSTM, Dense, Dropout, Masking, Embedding, Bidirectional
from keras.preprocessing.sequence import pad_sequences
from keras.utils import to_categorical
from keras.wrappers.scikit_learn import KerasClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.model_selection import GridSearchCV

np.random.seed(42)
tf.random.set_seed(42)

def roc_auc_score_multiclass(actual_class, pred_class, average="macro"):
    """
        Source: https://stackoverflow.com/questions/39685740/
                calculate-sklearn-roc-auc-score-for-multi-class
    """
    unique_class = [[0,0,0,1], [0,0,1,0], [0,1,0,0], [1,0,0,0]]
    roc_auc_dict = {}
    for per_class in unique_class:
        other_class = [x for x in unique_class if x != per_class]
        new_actual_class = [0 if x in other_class else 1 for x in actual_class]
        new_pred_class = [0 if x in other_class else 1 for x in pred_class]
        roc_auc = roc_auc_score(new_actual_class, new_pred_class, average = average)
        roc_auc_dict[per_class] = roc_auc
    return roc_auc_dict

def get_word_freq_and_word_rep(data):
    word_freq = {}
    word_rep = []
    urls = data
    for url in urls:
        parsed = parse(url.lower())
        word_rep.append(parsed)
        for word in parsed:
            word_freq[word] = word_freq.get(word, 0) + 1
    return word_freq, word_rep

def get_vocab_index_dict(word_freq):
    vocab = sorted([w for w in word_freq if word_freq[w] > 1])
    vocab_index_dict = {}
    # vocab = sorted(list(word_freq)) 
    for i in range(len(vocab)):
        vocab_index_dict[vocab[i]] = i + 2 
    vocab_index_dict['UNK'] = 1 # index 0: <PAD>, index 1: <UNK>
    return vocab_index_dict

def word_to_index(word, vocab_index_dict):
    return vocab_index_dict.get(word, vocab_index_dict['UNK'])

def get_vocab_index_rep(word_rep, vocab_index_dict):
    vocab_index_rep = []
    for rep in word_rep:
        vocab_index_rep.append([word_to_index(word, vocab_index_dict) for word in rep])
    return vocab_index_rep

df = pd.read_csv('data/balanced_data.csv', header=None) 
X_train, X_test, y_train, y_test = train_test_split(df[0].tolist(), np.array(df[1].tolist(), dtype=np.int), test_size=0.2, random_state=42)
y_train = to_categorical(y_train, 4)
y_test = to_categorical(y_test, 4)

X_train_word_freq, X_train_word_rep = get_word_freq_and_word_rep(X_train)
vocab_index_dict = get_vocab_index_dict(X_train_word_freq)
vocab_size = len(vocab_index_dict) + 1 # including <PAD> and <UNK>
X_train = get_vocab_index_rep(X_train_word_rep, vocab_index_dict)

X_test_word_freq, X_test_word_rep = get_word_freq_and_word_rep(X_test)
X_test = get_vocab_index_rep(X_test_word_rep, vocab_index_dict)

maxlen = 10
X_train = pad_sequences(X_train, padding='post', maxlen=maxlen)
X_test = pad_sequences(X_test, padding='post', maxlen=maxlen)


print('Finished preprocessing.')

# use vocab_index_dict to build word embedding matrix

embedding_dim = 50

def build_embedding_matrix(vocab_index_dict):
    embedding_matrix = np.zeros((vocab_size, embedding_dim), dtype=np.float32)

    with open('data/glove.6B.50d.txt', 'r') as f:
        for line in f:
            parts = line.split()
            word = parts[0]
            if word in vocab_index_dict:
                index = vocab_index_dict[word]
                vector = np.asarray(parts[1:], dtype=np.float32)
                embedding_matrix[index] = vector

        # <UNK> vector as average of all GloVe vectors
        # retrieved from https://stackoverflow.com/questions/49239941/what-is-unk-in-the-pretrained-glove-vector-files-e-g-glove-6b-50d-txt/53717345#53717345
        avg_glove_vec_str = '-0.12920076 -0.28866628 -0.01224866 -0.05676644 -0.20210965 -0.08389011 0.33359843 0.16045167 0.03867431 0.17833012 0.04696583 -0.00285802 0.29099807 0.04613704 -0.20923874 -0.06613114 -0.06822549 0.07665912 0.3134014 0.17848536 -0.1225775 -0.09916984 -0.07495987 0.06413227 0.14441176 0.60894334 0.17463093 0.05335403 -0.01273871 0.03474107 -0.8123879 -0.04688699 0.20193407 0.2031118 -0.03935686 0.06967544 -0.01553638 -0.03405238 -0.06528071 0.12250231 0.13991883 -0.17446303 -0.08011883 0.0849521 -0.01041659 -0.13705009 0.20127155 0.10069408 0.00653003 0.01685157'
        avg_glove_vec = np.array(avg_glove_vec_str.split())
        unk_index = vocab_index_dict['UNK']
        embedding_matrix[unk_index] = avg_glove_vec

    return embedding_matrix

embedding_matrix = build_embedding_matrix(vocab_index_dict)
print('Finished building embedding matrix with {:.4f} of vocabulary covered.'.format(np.count_nonzero(np.count_nonzero(embedding_matrix, axis=1)) / vocab_size))

# build RNN model
def build_model(dropout_rate, recurrent_dropout, n_dense_1, n_dense_2, n_dense_3):
    model = Sequential()
    model.add(Embedding(vocab_size, embedding_dim, input_length=maxlen, weights=[embedding_matrix], trainable=False))
    model.add(Masking(mask_value=0.0))
    
    # Recurrent layer
    model.add(LSTM(128, return_sequences=True)) #LSTM layer with 32 neurons
    # model.add(LSTM(64, return_sequences=False, dropout=dropout_rate, recurrent_dropout=recurrent_dropout))
    # with bidirectional gate
    model.add(Bidirectional(LSTM(64, return_sequences=False, dropout=dropout_rate, recurrent_dropout=recurrent_dropout)))
    
    model.add(Dropout(0.1))
    model.add(Dense(n_dense_1, activation='relu'))
    model.add(Dense(n_dense_2, activation='relu'))
    # model.add(Dense(n_dense_3, activation='relu'))
    model.add(layers.Dense(4, activation='softmax'))
    model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=[tf.keras.metrics.AUC()])
        # metrics=['accuracy'])
    return model

# grid search

# param_grid = dict(filters=[256],
#                   kernel_size=[2],
#                   pool_size=[3],
#                   dropout_rate=[0.2], 
#                   n_dense_1=[32], 
#                   n_dense_2=[16], 
#                   n_dense_3=[8])

# model = KerasClassifier(build_fn=build_model, epochs=10)
# grid = GridSearchCV(estimator=model, param_grid=param_grid, cv=5)
# # scoring='f1_weighted', 'roc_auc_ovr_weighted', 'roc_auc_ovo_weighted', refit=False
# grid_result = grid.fit(X_train, y_train)

# print('Best: %f using %s' % (grid_result.best_score_, grid_result.best_params_))
# test_score = grid.score(X_test, y_test)
# print('Test score: %f' % test_score)

# train model

#change dropout rates and nodes in dense layer
model = build_model(0.2, 0.2, 32, 8, 8)

# Create callbacks
callbacks = [EarlyStopping(monitor='val_loss', patience=5)]
# ModelCheckpoint('../models/model.h5', save_best_only=True, save_weights_only=False)]
model.fit(X_train, y_train, validation_data=(X_test, y_test), epochs=1, verbose=1, callbacks=callbacks)

# loss, score = model.evaluate(X_train, y_train, verbose=False)
# print('Training Score: {:.4f}'.format(score))
# loss, score = model.evaluate(X_test, y_test, verbose=False)
# print('Testing Score:  {:.4f}'.format(score))

y_val = model.predict(X_train)
y_pred = model.predict(X_test)
print('Training Score: {:.4f}'.format(roc_auc_score_multiclass(y_train, y_val)))
print('Training Score: {:.4f}'.format(roc_auc_score_multiclass(y_test, y_pred)))

'''
without gate
Training Score: 0.9237
Testing Score:  0.9252

with gate
Training Score: 0.9276
Testing Score:  0.9290
'''