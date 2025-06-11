
import pandas as pd

df = pd.read_csv("UserBehavior.csv",
                  sep="\t",
                  header=None,
                  nrows=4
                )
print(df)
