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
        "AUC": 0.8257,
        "GAUC": 0.8327,
        "HR@2": 0.6922,
        "HR@4": 0.8331,
        "NDCG@2": 0.6397,
        "NDCG@4": 0.7061,
        "MRR": 0.6888,
    },
    "sasrec": {
        "AUC": 0.8455,
        "GAUC": 0.843,
        "HR@2": 0.6964,
        "HR@4": 0.846,
        "NDCG@2": 0.6373,
        "NDCG@4": 0.7079,
        "MRR": 0.6851,
    },
    "slirec": {
        "AUC": 0.8333,
        "GAUC": 0.8381,
        "HR@2": 0.6857,
        "HR@4": 0.8464,
        "NDCG@2": 0.6224,
        "NDCG@4": 0.6983,
        "MRR": 0.6723,
    },
    "clsr": {
        "AUC": 0.8527,
        "GAUC": 0.8601,
        "HR@2": 0.7305,
        "HR@4": 0.8667,
        "NDCG@2": 0.6754,
        "NDCG@4": 0.7397,
        "MRR": 0.7177,
    },
    "frec": {
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
frec = [data["frec"][metric] for metric in metrics]
clsr = [data["clsr"][metric] for metric in metrics]
gru4rec = [data["gru4rec"][metric] for metric in metrics]
sasrec = [data["sasrec"][metric] for metric in metrics]
slirec = [data["slirec"][metric] for metric in metrics]


# Creazione del grafico
plt.figure(figsize=(10, 6))
plt.plot(metrics, frec, marker='o', label='FRec', linewidth=2)
plt.plot(metrics, clsr, marker='s', label='CLSR', linewidth=2, linestyle='--')
plt.plot(metrics, gru4rec, marker='o', label='GRU4Rec', linewidth=2)
plt.plot(metrics, sasrec, marker='s', label='SASRec', linewidth=2, linestyle='--')
plt.plot(metrics, slirec, marker='s', label='Sli-Rec', linewidth=2, linestyle='--')

# Personalizzazione
plt.title('Confronto performance Modelli', fontsize=14)
plt.xlabel('Metriche', fontsize=12)
plt.ylabel('Value', fontsize=12)
#plt.ylim(0.705, 0.895)
plt.grid(True, linestyle='--', alpha=0.5)
plt.legend()
plt.tight_layout()

# Mostra il grafico
plt.show()


# Dati della tabella
models = ["GRU4Rec", "SASRec", "SLi-Rec", "CLSR", "FRec"]
paper_times = [18.80, 59.30, 24.10, 21.70, 23.20]
replica_times = [33.40, 51.00, 50.20, 65.30, 25.30]

# Creazione del grafico a barre
x = range(len(models))
bar_width = 0.35

plt.figure(figsize=(10, 6))
plt.bar([i - bar_width/2 for i in x], paper_times, width=bar_width, label='Paper', color='skyblue')
plt.bar([i + bar_width/2 for i in x], replica_times, width=bar_width, label='Replica', color='salmon')

# Etichette e stile
plt.xticks(x, models)
plt.ylabel("Tempo di addestramento (minuti)")
plt.title("Confronto dei tempi di addestramento per modello")
plt.legend()
plt.grid(axis='y', linestyle='--', alpha=0.5)
plt.tight_layout()

# Mostra il grafico
plt.show()
