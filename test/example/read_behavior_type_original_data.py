
import pandas as pd

df = pd.read_csv("UserBehavior.csv",
                 header=None,
                 names=["user_id",
                        "item_id",
                        "category_id",
                        "behavior_type",
                        "timestamp"
                    ]
                )

print(df["behavior_type"].value_counts())
