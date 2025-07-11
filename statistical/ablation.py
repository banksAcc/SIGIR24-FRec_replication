import json
import matplotlib.pyplot as plt
import numpy as np

# === 1. Caricamento del JSON ===
with open("output/Ablation/all_data.json", "r") as f:  # Cambia nome file se diverso
    data = json.load(f)

# === 2. Mappatura etichette per asse X ===
label_map = {
    "wo_FUSION": "w/o Fusion",
    "wo_FRU": "w/o FRU",
    "wo_CROSS": "w/o Cross",
    "wo_CONTRASTIVE_LEARNING": "w/o CL",
    "frec_complete": "FRec"
}

# === 3. Funzione per calcolo media, min, max ===
def estrai_stats(data, metrica):
    nomi_modelli = []
    medie = []
    err_basso = []
    err_alto = []

    for chiave in label_map.keys():
        valori = [run[metrica] for run in data[chiave]]
        media = np.mean(valori)
        minimo = np.min(valori)
        massimo = np.max(valori)

        nomi_modelli.append(label_map[chiave])
        medie.append(media)
        err_basso.append(media - minimo)
        err_alto.append(massimo - media)

    return nomi_modelli, medie, err_basso, err_alto

# === 4. Plot grafico barplot con errori ===
def plot_bar(metrica, titolo, ylabel, nome_file):
    labels, y, yerr_low, yerr_high = estrai_stats(data, metrica)
    x = np.arange(len(labels))
    width = 0.6

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(x, y, width, color=["#88BDE6", "#FBC15E", "#90CD97", "#F5979A", "#D4A6C8"],
                  yerr=[yerr_low, yerr_high], capsize=6, error_kw={"elinewidth": 2, "alpha": 0.6})

    ax.set_title(titolo)
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20)
    ax.set_ylim([min(y) - 0.01, max(y) + 0.01])
    ax.grid(axis='y')
    plt.tight_layout()
    #plt.savefig(nome_file)
    plt.show()

# === 5. Esecuzione per AUC e NDCG@2 ===
plot_bar("auc", "AUC on Dataset", "AUC", "ablazione_auc.png")
plot_bar("ndcg@2", "NDCG@2 on Dataset", "NDCG@2", "ablazione_ndcg2.png")
