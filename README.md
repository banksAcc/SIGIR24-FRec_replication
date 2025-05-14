
# Official Implementation of FRec
SIGIR'24 Paper: Modeling User Fatigue for Sequential Recommendation

This project is based on [Microsoft Recommender](https://github.com/microsoft/recommenders) and was originally designed for TensorFlow 2.1.  
However, to run the model on modern hardware (e.g., RTX 30xx GPUs), we recommend upgrading to **TensorFlow 2.4.1** due to compatibility with CUDA 11.0 and cuDNN 8.x.

---

## 🔧 Environment Setup (Python 3.8 + TensorFlow 2.4.1)

### ✅ 1. Install Python 3.8.10
Download from: https://www.python.org/downloads/release/python-3810/

### ✅ 2. Create a virtual environment

```powershell
& "C:\Users\<your_username>\AppData\Local\Programs\Python\Python38\python.exe" -m venv frec-tf24-env
.frec-tf24-env\Scripts\activate
```

### ✅ 3. Install dependencies

Create a file `requirements_tf24.txt` with:

```
numpy
pandas
scikit-learn
PyYAML
tqdm
absl-py~=0.10
setproctitle==1.1.10
tensorflow==2.4.1
protobuf==3.19.6
retrying==1.3.3
```

Then run:

```bash
pip install -r requirements_tf24.txt
```

> ⚠️ Make sure you have installed [CUDA 11.0](https://developer.nvidia.com/cuda-11.0-download-archive) and cuDNN 8.x.

---

## 🧪 Running the Model

```bash
python run.py --model model --name trial
```

Other baselines:

```bash
python run.py --model clsr --name trial
python run.py --model slirec --name trial
```

---

## 🛠 Common Fixes

If you see `ModuleNotFoundError: No module named 'sli_rec'`, add this at the top of `run.py`:

```python
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
```

To run on CPU only:

```python
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
```

---

## 🗑 Deactivate and Remove Virtual Environment

To deactivate:

```bash
deactivate
```

To delete the virtual environment (PowerShell):

```bash
Remove-Item -Recurse -Force .\frec-tf24-env
```

Or manually delete the folder `frec-tf24-env` from File Explorer.

---

## 📁 Data

We provide a processed Taobao dataset. To extract:

```bash
unzip data.zip
```

Data format follows standard sequential input from the [Microsoft Recommender](https://github.com/microsoft/recommenders/blob/main/examples/00_quick_start/sequential_recsys_amazondataset.ipynb).

---

## 📌 Important Hyperparameters

- `num_cross_layers`: number of cross layers
- `recent_k`: truncated sequence length
- `num_interests`: number of latent interests
- `k_size`: convolutional kernel size
- `alpha`: contrastive learning weight
