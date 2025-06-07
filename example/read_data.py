import pandas as pd

df = pd.read_csv("../data/data/taobao/train_data", sep="\t", header=None)
df.columns = ['user_id'] + [f'item_{i}' for i in range(1, df.shape[1])]
print(df.head())
