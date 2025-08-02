import matplotlib.pyplot as plt

# Dati
data = {
    "frec_original": {
        "AUC": 0.8795,
        "MRR": 0.7501,
        "NDCG@2": 0.7143,
        "NDCG@4": 0.7716,
        "HR@2": 0.766,
        "HR@4": 0.8873,
        "GAUC": 0.8792
    },
    "frec_replica": {
        "AUC": 0.8817,
        "MRR": 0.749,
        "NDCG@2": 0.7127,
        "NDCG@4": 0.7707,
        "HR@2": 0.7644,
        "HR@4": 0.8872,
        "GAUC": 0.8809
    },
}

# Metriche da confrontare
metrics = ["AUC", "GAUC", "HR@2", "HR@4", "NDCG@2", "NDCG@4",  "MRR"]

# Estrazione dei valori
original_values = [data["frec_original"][metric] for metric in metrics]
replica_values = [data["frec_replica"][metric] for metric in metrics]

# Creazione del grafico
plt.figure(figsize=(10, 6))
plt.plot(metrics, original_values, marker='o', label='FRec (paper)', linewidth=2)
plt.plot(metrics, replica_values, marker='s', label='FRec (replica)', linewidth=2, linestyle='--')

# Personalizzazione
plt.title('Confronto performance FRec - Paper vs Replica', fontsize=14)
plt.xlabel('Metriche', fontsize=12)
plt.ylabel('Value', fontsize=12)
plt.ylim(0.705, 0.895)
plt.grid(True, linestyle='--', alpha=0.5)
plt.legend()
plt.tight_layout()

# Mostra il grafico
plt.show()


# Dati
data = {
    "gru4rec": {
        "AUC": 0.8247,
        "GAUC": 0.8313,
        "HR@2": 0.6925,
        "HR@4": 0.8324,
        "NDCG@2": 0.6386,
        "NDCG@4": 0.7041,
        "MRR": 0.6872
    },
    "sasrec": {
        "AUC": 0.8433,
        "GAUC": 0.8413,
        "HR@2": 0.6922,
        "HR@4": 0.8442,
        "NDCG@2": 0.6329,
        "NDCG@4": 0.7047,
        "MRR": 0.6816
    },
    "slirec": {
        "AUC": 0.827,
        "GAUC": 0.842,
        "HR@2": 0.687,
        "HR@4": 0.8472,
        "NDCG@2": 0.624,
        "NDCG@4": 0.6997,
        "MRR": 0.6739
    },
    "clsr": {
        "AUC": 0.8484,
        "GAUC": 0.8621,
        "HR@2": 0.7286,
        "HR@4": 0.8675,
        "NDCG@2": 0.6723,
        "NDCG@4": 0.7379,
        "MRR": 0.7148
    },
    "caser": {
        "AUC": 0.8279,
        "GAUC": 0.8411,
        "HR@2": 0.6852,
        "HR@4": 0.8416,
        "NDCG@2": 0.6281,
        "NDCG@4": 0.702,
        "MRR": 0.6797
    },
    "comirec-dr": {
        "AUC": 0.7773,
        "GAUC": 0.7792,
        "HR@2": 0.5659,
        "HR@4": 0.7733,
        "NDCG@2": 0.4994,
        "NDCG@4": 0.5971,
        "MRR": 0.573
    },
    "comirec-sa": {
        "AUC": 0.8351,
        "GAUC": 0.8336,
        "HR@2": 0.6672,
        "HR@4": 0.8372,
        "NDCG@2": 0.6046,
        "NDCG@4": 0.6848,
        "MRR": 0.659
    },
    "dfn": {
        "AUC": 0.7768,
        "GAUC": 0.8511,
        "HR@2": 0.7171,
        "HR@4": 0.8496,
        "NDCG@2": 0.665,
        "NDCG@4": 0.7274,
        "MRR": 0.7093
    },
    "dien": {
        "AUC": 0.7614,
        "GAUC": 0.8328,
        "HR@2": 0.6685,
        "HR@4": 0.8384,
        "NDCG@2": 0.6046,
        "NDCG@4": 0.6847,
        "MRR": 0.6581
    },
    "din": {
        "AUC": 0.6614,
        "GAUC": 0.8478,
        "HR@2": 0.6929,
        "HR@4": 0.8453,
        "NDCG@2": 0.6309,
        "NDCG@4": 0.703,
        "MRR": 0.6785
    },
    "sum": {
        "AUC": 0.829,
        "GAUC": 0.8353,
        "HR@2": 0.6864,
        "HR@4": 0.8324,
        "NDCG@2": 0.6305,
        "NDCG@4": 0.6993,
        "MRR": 0.6802
    },
    "frec": {
        "AUC": 0.8817,
        "GAUC": 0.8809,
        "HR@2": 0.7644,
        "HR@4": 0.8872,
        "NDCG@2": 0.7127,
        "NDCG@4": 0.7707,
        "MRR": 0.749
    }
}

# Metriche da confrontare
metrics = ["AUC", "GAUC", "HR@2", "HR@4", "NDCG@2", "NDCG@4", "MRR"]

# Estrazione dei valori
model_names = ["frec", "clsr", "gru4rec", "sasrec", "slirec", "caser", "comirec-dr", "comirec-sa", "dfn", "dien", "din", "sum"]
model_labels = {
    "frec": "FRec",
    "clsr": "CLSR",
    "gru4rec": "GRU4Rec",
    "sasrec": "SASRec",
    "slirec": "Sli-Rec",
    "caser": "Caser",
    "comirec-dr": "ComiRec-DR",
    "comirec-sa": "ComiRec-SA",
    "dfn": "DFN",
    "dien": "DIEN",
    "din": "DIN",
    "sum": "SUM"
}

# Colori e stili opzionali per differenziare meglio
styles = ['-', '--', '-.', ':'] * 4
markers = ['o', 's', 'D', '^', 'v', '<', '>', 'p', '*', 'X', 'h', 'H']

plt.figure(figsize=(12, 7))

for i, model in enumerate(model_names):
    values = [data[model][metric] for metric in metrics]
    plt.plot(metrics, values, marker=markers[i % len(markers)], linestyle=styles[i % len(styles)],
             linewidth=2, label=model_labels[model])

# Personalizzazione
plt.title('Confronto performance modelli (Replica Taobao)', fontsize=14)
plt.xlabel('Metriche', fontsize=12)
plt.ylabel('Valore', fontsize=12)
plt.grid(True, linestyle='--', alpha=0.5)
plt.xticks(rotation=45)
plt.legend(loc='lower right', fontsize=9)
plt.tight_layout()
plt.show()


# Dati aggiornati dalla tabella dell'immagine
models = [
    "GRU4Rec", "SASRec", "Sli-Rec", "CLSR", "Caser",
    "ComiRec-DR", "ComiRec-SA", "DFN", "DIEN", "DIN", "SUM", "FRec"
]

paper_times = [9.80, 14.00, 11.10, 11.30, 13.40, 7.90, 7.90, 10.00, 8.50, 7.80, 35.30, 12.70]
replica_times = [33.40, 51.00, 50.20, 65.30, 35.44, 17.75, 17.75, 25.52, 24.55, 18.12, 107.39, 25.30]


# Creazione del grafico a barre
x = range(len(models))
bar_width = 0.35

plt.figure(figsize=(12, 6))
plt.bar([i - bar_width/2 for i in x], paper_times, width=bar_width, label='Paper', color='skyblue')
plt.bar([i + bar_width/2 for i in x], replica_times, width=bar_width, label='Replica', color='salmon')

# Etichette e stile
plt.xticks(x, models, rotation=45)
plt.ylabel("Tempo di inferenza (ms/item)")
plt.title("Confronto dei tempi di inferenza per modello")
plt.legend()
plt.grid(axis='y', linestyle='--', alpha=0.5)
plt.tight_layout()

# Mostra il grafico
plt.show()
