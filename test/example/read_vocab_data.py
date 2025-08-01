import pickle


with open("data/taobao/test_data", "rb") as f:
    item_vocab = pickle.load(f)

print(type(item_vocab))       # probabilmente un dict o un vocab custom
print(list(item_vocab.items())[:50])  # primi 5 elementi
