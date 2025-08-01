# 🔬 Custom Evaluation: Negative Sampling Guided by Fatigue Score `m`

Questo progetto estende il framework originale introducendo una logica personalizzata di **negative sampling basato sulla metrica di fatica utente `m`**, come descritto nel paper *"FRec: Evaluating Recommendation with Frequentist Inference"*.

## 📌 Obiettivo

Durante la **fase di test offline**, vogliamo:
- Controllare il range di `m` dei sample negativi,
- Generare file di test bucketizzati (es. m ∈ [1,3], [3,5], …),
- Misurare le metriche di ranking su ciascun bucket (NDCG@2, AUC, ecc.).

---

## ✅ Modifiche Apportate

Abbiamo modificato la funzione `_convert_data(...)` del dataloader, che ora accetta 3 nuovi argomenti opzionali:

```python
def _convert_data(...,
                  test_on_m=False,
                  m_min=0.0,
                  m_max=9.0)
```

### Significato:
- `test_on_m=True`: attiva il negative sampling guidato dalla metrica `m`;
- `m_min` / `m_max`: definiscono l’intervallo desiderato per `m`.

---

## 🛠️ Istruzioni per l’Uso

### 1. **Assicurati di eseguire l'addestramento**
Perché il sampling negativo viene applicato solo in fase di training (`self.is_train == True`).

Modifica lo script di training per abilitare il sampling pilotato:

```python
dataloader._convert_data(...,
                         test_on_m=True,
                         m_min=1.0,
                         m_max=3.0)
```

Oppure imposta direttamente questi parametri nella classe che gestisce i dati, ad esempio:

```python
self.test_on_m = True
self.m_min = 1.0
self.m_max = 3.0
```

e usa queste variabili nella chiamata a `_convert_data()`.

---

### 2. **Fallback randomico**

Se non viene trovata una categoria negativa che produca un `m` nell'intervallo desiderato, il sistema stampa un log e seleziona un item negativo randomico:

```
[INFO] Nessun negative sample con m ∈ [1.0, 3.0] per istanza 15, uso fallback randomico.
```

---

### 3. **Output di esempio**

Puoi salvare i file bucketizzati direttamente usando lo script `split_by_m.py` (se incluso nel progetto), per poi eseguire test separati su:
- `test_data_1-3`
- `test_data_3-5`
- `test_data_5-7`
- `test_data_7-9`

---

## 📊 Valutazione

Dopo l’addestramento, lancia il modulo di test standard per valutare il modello sui bucket:

```bash
python evaluate.py --test_file test_data_3-5
```

Assicurati che il modello sia stato allenato con lo stesso criterio di negative sampling per una valutazione coerente.

---

## 📁 File Coinvolti

- `dataloader.py` → `_convert_data(...)`
- `gen_fatigue_features(...)` → calcolo di `m` (score di fatica)
- `evaluate.py` o script di training → aggiunta dei parametri per `m`

---

## 👤 Autori delle modifiche

Custom implementation by [TUO NOME], 2025  
Basato sul paper "FRec" (Microsoft Research, 2024)