import pandas as pd

file_path = "data/taobao/test_data"

# Separa per tabulazione o spazio (prova entrambi)
try:
    df = pd.read_csv(file_path, sep="\t", header=None)
except:
    df = pd.read_csv(file_path, sep=" ", header=None)

# Aggiunge nomi colonne
df.columns = [
    "label", "user_id", "item_id", "category_id", "timestamp",
    "history_item_ids", "history_category_ids", "history_timestamps"
]

# Visualizza prime righe
print(df.head(5))
