# Face data (kept local, never committed)

Face photos are biometric data, so this repository doesn't ship any real photos for new identities or evaluation. The folders below are ignored by git. Create them on your own machine.

```
data/
├── known_faces/
│   └── <PhotoFolder>/        # one folder per person, e.g. JaneDoe/
│       ├── 01.jpg            # 10–25 clear photos of that person's face
│       └── ...
└── test_images/              # only needed to run evaluation/evaluate_recognition.py
    ├── normal/
    ├── low_light/
    ├── different_angle/
    ├── occluded/
    └── unknown_person/       # people who are NOT in known_faces/
```

- The folder name under `known_faces/` must match the **Photo folder** you enter for that student or staff member in the dashboard.
- Only use photos of people who have agreed to it. For a demo, use your own face.
- Reference embeddings are rebuilt when the backend starts, so restart it after adding photos.
- Webcam photos can be added with `python evaluation/enroll_webcam.py --person <PhotoFolder>` (see the main README, Setup step 6).
- More reference photos from different angles and lighting improve recognition. The evaluation results in the main README used 22 reference photos of one person.
