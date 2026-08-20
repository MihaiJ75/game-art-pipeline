import sys
import unittest
import numpy as np
from pathlib import Path
from PIL import Image

# Add bundle root to sys.path
BUNDLE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BUNDLE_ROOT))

from engine import (
    ArtPipelineConfig,
    extract_chroma,
    make_seamless_blend,
    evaluate_asset,
    check_alpha_and_chroma,
    check_edge_hardness,
    check_perspective,
    check_symmetry,
    check_seamless_tiling,
    check_palette_coherence,
    generate_html_report,
    generate_markdown_report,
    prompt_hash,
    detect_strip_frames
)

class TestGenericPipeline(unittest.TestCase):
    def setUp(self):
        self.config = ArtPipelineConfig()

    def test_chroma_extraction(self):
        im = Image.new("RGB", (100, 100), (255, 0, 255))
        for x in range(30, 70):
            for y in range(30, 70):
                im.putpixel((x, y), (20, 20, 20))
        out = extract_chroma(im, target_rgb=(255, 0, 255), tolerance=30)
        arr = np.array(out)
        self.assertEqual(arr[0, 0, 3], 0)
        self.assertEqual(arr[50, 50, 3], 255)

    def test_seamless_tiling_cross_blend(self):
        im = Image.new("RGB", (128, 128), (40, 40, 40))
        out = make_seamless_blend(im, margin=16)
        arr = np.array(out)
        self.assertEqual(arr.shape, (128, 128, 3))

    def test_cv_perspective_qa(self):
        arr = np.zeros((100, 100, 4), dtype=np.uint8)
        arr[20:80, 20:80, :3] = 40
        arr[20:80, 20:80, 3] = 255
        res = check_perspective(arr, self.config, "test_sprite.png")
        self.assertTrue(res.passed)

    def test_cv_symmetry_qa(self):
        arr = np.zeros((100, 100, 4), dtype=np.uint8)
        arr[20:80, 30:70, :3] = 40
        arr[20:80, 30:70, 3] = 255
        res = check_symmetry(arr, self.config, "test_sprite.png")
        self.assertTrue(res.passed)

    def test_prompt_hashing(self):
        h = prompt_hash("Test prompt text")
        self.assertEqual(len(h), 12)

if __name__ == "__main__":
    unittest.main()
