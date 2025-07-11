import json
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict

# --------- FUNZIONI UTILI ---------
def raggruppa_per_valore(lista, chiave_raggruppamento):
    gruppi = defaultdict(list)
    for entry in lista:
        key = entry[chiave_raggruppamento]
        gruppi[key].append(entry["ndcg@2"])
    return gruppi

def calcola_media_min_max(gruppi):
    x_vals = []
    y_media = []
    y_err_basso = []
    y_err_alto = []

    for key in sorted(gruppi.keys()):
        valori = gruppi[key]
        media = np.mean(valori)
        minimo = np.min(valori)
        massimo = np.max(valori)
        x_vals.append(key)
        y_media.append(media)
        y_err_basso.append(media - minimo)
        y_err_alto.append(massimo - media)

    return x_vals, y_media, y_err_basso, y_err_alto

# --------- CARICAMENTO JSON ---------
with open("output/Iperparameter/all_data.json", "r") as f:  # Adatta il nome se diverso
    data = json.load(f)

# --------- GRAFICO A: kernel size ---------
gruppi_k = raggruppa_per_valore(data["k_size"], "k_size")
x_k, y_k, y_k_err_low, y_k_err_high = calcola_media_min_max(gruppi_k)

plt.figure(figsize=(8, 4))
plt.errorbar(
    x_k, y_k,
    yerr=[y_k_err_low, y_k_err_high],
    fmt='o-',
    capsize=0,
    label="ndcg@2",
    linewidth=2,            # Aumenta lo spessore della linea
    alpha=0.8,              # Rende semitrasparenti error bar + linea
    ecolor='blue',          # Colore delle barre di errore
    elinewidth=1.5          # Spessore delle barre di errore
)

plt.title("Grafico a: ndcg@2 in funzione del Kernel Size")
plt.xlabel("Kernel Size")
plt.ylabel("ndcg@2")
plt.grid(axis='y')
plt.xticks(x_k)  # nel grafico a
plt.tight_layout()
#plt.savefig("grafico_a_ndcg_vs_k_size_con_errorbar.png")
plt.show()

# --------- GRAFICO B: threshold / recent ---------
gruppi_recent = raggruppa_per_valore(data["recent_lenght"], "recent")
x_r, y_r, y_r_err_low, y_r_err_high = calcola_media_min_max(gruppi_recent)

plt.figure(figsize=(8, 4))
plt.errorbar(
    x_r, y_r,
    yerr=[y_r_err_low, y_r_err_high],
    fmt='o-',
    capsize=5,
    color="orange",
    label="ndcg@2",
    linewidth=2,
    alpha=0.8,
    ecolor='orange',
    elinewidth=1.5
)

plt.title("Grafico b: ndcg@2 in funzione del Threshold (Recent Length)")
plt.xlabel("Threshold (Recent Length)")
plt.ylabel("ndcg@2")
plt.grid(axis='y')
plt.xticks(x_r)  # nel grafico b
plt.tight_layout()
#plt.savefig("grafico_b_ndcg_vs_threshold_con_errorbar.png")
plt.show()
