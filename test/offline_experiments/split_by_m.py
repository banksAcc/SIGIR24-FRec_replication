import pandas as pd
import random
import pickle
from tqdm import tqdm

# === Percorsi file ===
data_path = "data/taobao/"
test_file = data_path + "test_data"
cat_vocab_file = data_path + "category_vocab.pkl"
item_vocab_file = data_path + "item_vocab.pkl"

# === Caricamento vocabolari ===
with open(cat_vocab_file, 'rb') as f:
    category_vocab = pickle.load(f)  # item_id → category_id

with open(item_vocab_file, 'rb') as f:
    item_vocab = pickle.load(f)
    # Ignora chiavi non intere (es. 'default_mid')
    all_items = set()
    for k in item_vocab.keys():
        try:
            all_items.add(int(k))
        except:
            continue

print(f"Totale item_vocab: {len(item_vocab)}")
print(f"Totale category_vocab: {len(category_vocab)}")
print(f"Totale all_items (filtrati): {len(all_items)}")

# === Leggi il file test ===
df = pd.read_csv(test_file, sep="\t", header=None, nrows=2000)

df.columns = [
    "label", "user_id", "item_id", "category_id", "timestamp",
    "history_item_ids", "history_category_ids", "history_timestamps"
]

# === Funzione per convertire stringhe in liste ===
def str_to_list(s):
    return list(map(int, s.split(",")))

# === Contenitori per i 4 bucket ===
buckets = {
    "1-3": [],
    "3-5": [],
    "5-7": [],
    "7-9": []
}
count_total = 0
count_valid = 0
count_bucket = {key: 0 for key in buckets}

print("Processing rows and computing m...")
for _, row in tqdm(df.iterrows(), total=len(df)):
    try:
        count_total += 1

        # === Parsing dati ===
        uid = row["user_id"]
        i_pos = row["item_id"]
        cat_pos = row["category_id"]
        ts = row["timestamp"]

        hist_items = str_to_list(row["history_item_ids"])
        hist_cats = str_to_list(row["history_category_ids"])
        hist_ts = str_to_list(row["history_timestamps"])

        if count_total <= 10:
            print(f"[DEBUG] Inizio riga {count_total} - item_pos {i_pos} - ts {ts}")
            print(f"[DEBUG] Riga {count_total}: parsed history OK — {len(hist_items)} items")

        # === Negative sampling ===
        user_seen = set(hist_items)
        neg_candidates = list(all_items - user_seen)
        random.shuffle(neg_candidates)

        i_neg = None
        for item in neg_candidates:
            if item in category_vocab:
                i_neg = item
                break

        if i_neg is None:
            if count_total <= 10:
                print(f"[DEBUG] Riga {count_total}: nessun candidato negativo valido (nessun item ha categoria)")
            continue

        cat_neg = category_vocab[i_neg]

        # === Finestra 3h precedenti ===
        valid_indices = [
            i for i, t in enumerate(hist_ts) if ts - 10800 <= t < ts
        ]
        hist_recent_cats = [hist_cats[i] for i in valid_indices]

        m_plus = hist_recent_cats.count(cat_pos)
        m_minus = hist_recent_cats.count(cat_neg)
        m = m_minus - m_plus

        if count_total <= 10:
            print(f"[DEBUG] m = {m} | m^- = {m_minus} | m^+ = {m_plus} | cat^- = {cat_neg} | cat^+ = {cat_pos}")
            print(f"[DEBUG] valid_indices = {valid_indices}")
            print(f"[DEBUG] hist_recent_cats = {hist_recent_cats}")
            print(f"[DEBUG] ts = {ts} | hist_ts = {hist_ts[:5]}...")

        # === Bucketizzazione ===
        if 1 <= m < 3:
            buckets["1-3"].append(row)
            count_valid += 1
            count_bucket["1-3"] += 1
        elif 3 <= m < 5:
            buckets["3-5"].append(row)
            count_valid += 1
            count_bucket["3-5"] += 1
        elif 5 <= m < 7:
            buckets["5-7"].append(row)
            count_valid += 1
            count_bucket["5-7"] += 1
        elif 7 <= m < 9:
            buckets["7-9"].append(row)
            count_valid += 1
            count_bucket["7-9"] += 1

        # [Opzionale] aggiungi m come nuova colonna se vuoi:
        # row["m"] = m

    except Exception as e:
        print(f"[ERRORE] Riga saltata: {e}")
        continue

print(f"Totale righe processate: {count_total}")
print(f"Totale righe valide con 1 ≤ m < 9: {count_valid}")
print("Distribuzione per bucket:", count_bucket)

# === Salvataggio file ===
for key, rows in buckets.items():
    if rows:
        df_bucket = pd.DataFrame(rows)
        output_file = data_path + f"test_data_{key.replace('-', '_')}"
        df_bucket.to_csv(output_file, sep="\t", header=False, index=False)
        print(f"Salvato: {output_file} ({len(rows)} righe)")
