import unittest

from features.gamma_ppt.gamma_client import build_gamma_payload, find_pptx_urls
from features.gamma_ppt.pipeline import (
    _clean_deck_text,
    _has_image_error_text,
    _balance_density,
    DEFAULT_IMAGE_STYLE,
    _slides_to_deck_text,
    MAX_BULLET_CHARS,
)


class GammaUtilsTests(unittest.TestCase):
    def test_find_pptx_urls_nested(self):
        data = {
            "files": [
                {"type": "pptx", "url": "https://example.com/a.pptx"},
                {"type": "pdf", "url": "https://example.com/a.pdf"},
            ],
            "other": {"url": "https://example.com/slide?p=pptx"},
        }
        urls = find_pptx_urls(data)
        self.assertIn("https://example.com/a.pptx", urls)
        self.assertIn("https://example.com/slide?p=pptx", urls)

    def test_find_pptx_urls_ignores_non(self):
        data = {"url": "https://example.com/a.pdf"}
        urls = find_pptx_urls(data)
        self.assertEqual(urls, [])

    def test_build_gamma_payload_numcards(self):
        payload = build_gamma_payload(
            input_text="test",
            card_split="inputTextBreaks",
            num_cards=18,
        )
        self.assertNotIn("numCards", payload)

        payload_auto = build_gamma_payload(
            input_text="test",
            card_split="auto",
            num_cards=18,
        )
        self.assertEqual(payload_auto.get("numCards"), 18)

    def test_build_gamma_payload_header_footer(self):
        payload = build_gamma_payload(
            input_text="test",
            card_split="inputTextBreaks",
            num_cards=18,
        )
        card_opts = payload.get("cardOptions", {})
        header_footer = card_opts.get("headerFooter", {})
        bottom_right = header_footer.get("bottomRight", {})
        self.assertEqual(bottom_right.get("type"), "cardNumber")
        self.assertTrue(header_footer.get("hideFromFirstCard"))

    def test_build_gamma_payload_default_image_source(self):
        payload = build_gamma_payload(
            input_text="test",
            card_split="inputTextBreaks",
            num_cards=18,
        )
        img_opts = payload.get("imageOptions", {})
        self.assertEqual(img_opts.get("source"), "aiGenerated")

    def test_build_gamma_payload_image_style(self):
        payload = build_gamma_payload(
            input_text="test",
            card_split="inputTextBreaks",
            num_cards=18,
            image_style="technical diagram",
        )
        img_opts = payload.get("imageOptions", {})
        self.assertEqual(img_opts.get("style"), "technical diagram")
        self.assertIn("technical diagram", DEFAULT_IMAGE_STYLE)

    def test_min_bullets_enforced(self):
        raw = "# 제목\n- 항목1\n- 항목2"
        cleaned = _clean_deck_text(raw)
        lines = [ln for ln in cleaned.splitlines() if ln.startswith("-")]
        self.assertGreaterEqual(len(lines), 3)

    def test_bullet_trim_length(self):
        long_text = "A" * (MAX_BULLET_CHARS + 20)
        raw = f"# 제목\n- {long_text}\n- 항목2\n- 항목3"
        cleaned = _clean_deck_text(raw)
        bullets = [ln for ln in cleaned.splitlines() if ln.startswith("-")]
        self.assertTrue(any(len(b.replace('- ', '')) <= MAX_BULLET_CHARS + 3 for b in bullets))

    def test_image_error_detection(self):
        self.assertTrue(_has_image_error_text("이미지를 생성하는 중 오류"))

    def test_balance_density_split(self):
        blocks = [
            {"title": "A", "bullets": ["- a", "- b", "- c", "- d", "- e", "- f"]}
        ]
        out = _balance_density(blocks)
        self.assertEqual(len(out), 2)

    def test_balance_density_merge(self):
        blocks = [
            {"title": "A", "bullets": ["- a"]},
            {"title": "B", "bullets": ["- b", "- c"]},
        ]
        out = _balance_density(blocks)
        self.assertEqual(len(out), 1)

    def test_slides_to_deck_text(self):
        slides = [{"title": "표지", "bullets": ["- 과제명: ...", "- 부처: ...", "- 주관기관: ..."]}]
        deck = _slides_to_deck_text(slides)
        self.assertIn("# 표지", deck)
        self.assertIn("- 과제명: ...", deck)


if __name__ == "__main__":
    unittest.main()
