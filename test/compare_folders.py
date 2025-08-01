import filecmp
import os
from pathlib import Path

# PERCORSI da modificare con i tuoi (usa raw string r"" per gli spazi!)
folder_a = r"path\to\folder_a"
folder_b = r"path\to\folder_b"

report_lines = []

for dirpath, dirnames, filenames in os.walk(folder_a):
    rel_path = os.path.relpath(dirpath, folder_a)
    compare_dir_b = os.path.join(folder_b, rel_path)

    for filename in filenames:
        file_a = os.path.join(dirpath, filename)
        file_b = os.path.join(compare_dir_b, filename)

        if not os.path.exists(file_b):
            report_lines.append(f"🆕 File solo in FRec: {os.path.join(rel_path, filename)}")
        elif not filecmp.cmp(file_a, file_b, shallow=False):
            report_lines.append(f"✏️ File modificato:    {os.path.join(rel_path, filename)}")
        else:
            report_lines.append(f"✅ File identico:      {os.path.join(rel_path, filename)}")

# Ora cerchiamo file presenti in B ma assenti in A
for dirpath, dirnames, filenames in os.walk(folder_b):
    rel_path = os.path.relpath(dirpath, folder_b)
    compare_dir_a = os.path.join(folder_a, rel_path)

    for filename in filenames:
        file_b = os.path.join(dirpath, filename)
        file_a = os.path.join(compare_dir_a, filename)

        if not os.path.exists(file_a):
            report_lines.append(f"❌ File rimosso nel progetto FRec: {os.path.join(rel_path, filename)}")

# Salvataggio del report
output_path = Path(__file__).parent / "diff_report.txt"
with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

print(f"✅ Confronto completato. Report salvato in: {output_path}")
