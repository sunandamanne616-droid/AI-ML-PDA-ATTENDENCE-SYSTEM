from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
KNOWN_FACES_DIR = BASE_DIR / "known_faces"
EMBEDDINGS_FILE = BASE_DIR / "embeddings.npz"
MODEL_NAME = "buffalo_l"
MATCH_THRESHOLD = 0.4
