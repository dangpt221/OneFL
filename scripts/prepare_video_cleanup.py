"""Copy bundled OCR models into OneFL storage; no browser/cloud credentials."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.services.cleanup_ocr import model_directory, prepare_local_models


if __name__ == '__main__':
    print(json.dumps({'prepared': prepare_local_models(), 'directory': str(model_directory())}))
