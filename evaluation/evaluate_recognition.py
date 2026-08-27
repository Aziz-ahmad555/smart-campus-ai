import os
import time
import csv
from deepface import DeepFace

KNOWN_FACES_DB = "data/known_faces"
TEST_IMAGES_ROOT = "data/test_images"
RESULTS_CSV = "evaluation/recognition_results.csv"

CATEGORY_EXPECTATIONS = {
    "normal": "AzizAhmad",
    "low_light": "AzizAhmad",
    "different_angle": "AzizAhmad",
    "occluded": "AzizAhmad",
    "unknown_person": "Unknown",
}

def recognize_image(image_path):
    start_time = time.time()
    try:
        results = DeepFace.find(
            img_path=image_path,
            db_path=KNOWN_FACES_DB,
            enforce_detection=False,
            silent=True,
            detector_backend="opencv"
        )
        elapsed = time.time() - start_time

        if len(results) > 0 and len(results[0]) > 0:
            best_match_path = results[0].iloc[0]["identity"]
            photo_folder = os.path.basename(os.path.dirname(best_match_path))
            return photo_folder, elapsed
        else:
            return "Unknown", elapsed
    except Exception as e:
        elapsed = time.time() - start_time
        return f"ERROR: {e}", elapsed

def main():
    os.makedirs("evaluation", exist_ok=True)
    rows = []

    for category, expected in CATEGORY_EXPECTATIONS.items():
        folder_path = os.path.join(TEST_IMAGES_ROOT, category)
        if not os.path.exists(folder_path):
            print(f"Skipping missing folder: {folder_path}")
            continue

        image_files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        print(f"\n--- Testing category: {category} ({len(image_files)} images) ---")

        for image_file in image_files:
            image_path = os.path.join(folder_path, image_file)
            predicted, elapsed = recognize_image(image_path)
            is_correct = (predicted == expected)

            print(f"{image_file}: predicted='{predicted}', expected='{expected}', correct={is_correct}, time={elapsed:.2f}s")

            rows.append({
                "category": category,
                "image_file": image_file,
                "expected": expected,
                "predicted": predicted,
                "correct": is_correct,
                "time_seconds": round(elapsed, 3)
            })

    with open(RESULTS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "image_file", "expected", "predicted", "correct", "time_seconds"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nResults saved to {RESULTS_CSV}")

    print("\n=== SUMMARY ===")
    categories = set(row["category"] for row in rows)
    for category in categories:
        cat_rows = [r for r in rows if r["category"] == category]
        correct_count = sum(1 for r in cat_rows if r["correct"])
        total = len(cat_rows)
        accuracy = (correct_count / total * 100) if total > 0 else 0
        avg_time = sum(r["time_seconds"] for r in cat_rows) / total if total > 0 else 0
        print(f"{category}: {correct_count}/{total} correct ({accuracy:.1f}%), avg time {avg_time:.2f}s")

    print("\n=== FALSE ACCEPTANCE / REJECTION RATES ===")
    genuine_rows = [r for r in rows if r["expected"] == "AzizAhmad"]
    impostor_rows = [r for r in rows if r["expected"] == "Unknown"]

    false_rejections = sum(1 for r in genuine_rows if r["predicted"] != "AzizAhmad")
    false_acceptances = sum(1 for r in impostor_rows if r["predicted"] == "AzizAhmad")

    frr = (false_rejections / len(genuine_rows) * 100) if genuine_rows else 0
    far = (false_acceptances / len(impostor_rows) * 100) if impostor_rows else 0

    print(f"Genuine attempts (should recognize AzizAhmad): {len(genuine_rows)}")
    print(f"False Rejections: {false_rejections}")
    print(f"False Rejection Rate (FRR): {frr:.1f}%")
    print()
    print(f"Impostor attempts (should say Unknown): {len(impostor_rows)}")
    print(f"False Acceptances: {false_acceptances}")
    print(f"False Acceptance Rate (FAR): {far:.1f}%")

    overall_correct = sum(1 for r in rows if r["correct"])
    overall_total = len(rows)
    overall_accuracy = (overall_correct / overall_total * 100) if overall_total else 0
    avg_time_all = sum(r["time_seconds"] for r in rows) / overall_total if overall_total else 0
    print(f"\nOverall accuracy: {overall_correct}/{overall_total} ({overall_accuracy:.1f}%)")
    print(f"Overall average recognition time: {avg_time_all:.2f}s")

if __name__ == "__main__":
    main()
