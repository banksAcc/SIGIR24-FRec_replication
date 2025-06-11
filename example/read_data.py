import pandas as pd

df = pd.read_csv("UserBehavior.csv", sep="\t", header=None)

# Mostra la riga 4 interamente
print(df.iloc[1].to_string())