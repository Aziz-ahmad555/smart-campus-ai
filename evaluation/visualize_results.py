import csv
import matplotlib.pyplot as plt

# ---- Chart 1: Recognition Accuracy by Category ----
categories = {}
with open("evaluation/recognition_results.csv", "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        cat = row["category"]
        correct = row["correct"] == "True"
        if cat not in categories:
            categories[cat] = {"correct": 0, "total": 0}
        categories[cat]["total"] += 1
        if correct:
            categories[cat]["correct"] += 1

cat_names = list(categories.keys())
accuracies = [categories[c]["correct"] / categories[c]["total"] * 100 for c in cat_names]

plt.figure(figsize=(8, 5))
bars = plt.bar(cat_names, accuracies, color="#4CAF50")
plt.ylim(0, 100)
plt.ylabel("Accuracy (%)")
plt.title("Face Recognition Accuracy by Condition")
plt.xticks(rotation=20)
for bar, acc in zip(bars, accuracies):
    plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, f"{acc:.1f}%", ha="center")
plt.tight_layout()
plt.savefig("evaluation/accuracy_by_condition.png")
print("Saved evaluation/accuracy_by_condition.png")
plt.close()

# ---- Chart 2: FPS by Pipeline Stage ----
stages = []
fps_values = []
with open("evaluation/fps_results.csv", "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        stages.append(row["stage"])
        fps_values.append(float(row["fps"]))

plt.figure(figsize=(8, 5))
bars = plt.bar(stages, fps_values, color="#2196F3")
plt.ylabel("Frames Per Second (FPS)")
plt.title("Pipeline Performance on CPU")
for bar, fps in zip(bars, fps_values):
    plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.15, f"{fps:.2f}", ha="center")
plt.tight_layout()
plt.savefig("evaluation/fps_by_stage.png")
print("Saved evaluation/fps_by_stage.png")
plt.close()

print("\nBoth charts generated successfully.")
