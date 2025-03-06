import unittest
import bibtexparser
from bibtex2dblp import DBLPSearcher


class TestBibtex2DBLP(unittest.TestCase):
    def setUp(self):
        self.searcher = DBLPSearcher()

        # Reference DBLP entry
        self.dblp_reference = {
            "title": "PyTorch: An Imperative Style, High-Performance Deep Learning Library",
            "authors": [
                "Adam Paszke",
                "Sam Gross",
                "Francisco Massa",
                "Adam Lerer",
                "James Bradbury",
                "Gregory Chanan",
                "Trevor Killeen",
                "Zeming Lin",
                "Natalia Gimelshein",
                "Luca Antiga",
                "Alban Desmaison",
                "Andreas Köpf",
                "Edward Z. Yang",
                "Zachary DeVito",
                "Martin Raison",
                "Alykhan Tejani",
                "Sasank Chilamkurthy",
                "Benoit Steiner",
                "Lu Fang",
                "Junjie Bai",
                "Soumith Chintala",
            ],
            "year": "2019",
            "venue": "NeurIPS",
            "booktitle": "Advances in Neural Information Processing Systems 32: Annual Conference on Neural Information Processing Systems 2019, NeurIPS 2019, December 8-14, 2019, Vancouver, BC, Canada",
            "pages": "8024-8035",
            "ee": "https://proceedings.neurips.cc/paper/2019/hash/bdbca288fee7f92f2bfa9f7012727740-Abstract.html",
            "key": "conf/nips/PaszkeGMLBCKLGA19",
        }

    def test_title_matching(self):
        """Test if title matching works correctly"""
        title = "PyTorch: An Imperative Style, High-Performance Deep Learning Library"
        similarity = self.searcher._compare_titles(title, self.dblp_reference["title"])
        self.assertGreaterEqual(similarity, 0.7)

    def test_author_matching(self):
        """Test if author matching works correctly"""
        authors = [
            "Adam Paszke",
            "Sam Gross",
            "Francisco Massa",
            "Adam Lerer",
            "James Bradbury",
            "Gregory Chanan",
            "Trevor Killeen",
            "Zeming Lin",
            "Natalia Gimelshein",
            "Luca Antiga",
            "Alban Desmaison",
            "Andreas Köpf",
            "Edward Yang",
            "Zach DeVito",
            "Martin Raison",
            "Alykhan Tejani",
            "Sasank Chilamkurthy",
            "Benoit Steiner",
            "Lu Fang",
            "Junjie Bai",
            "Soumith Chintala",
        ]
        similarity = self.searcher._compare_authors(
            authors, self.dblp_reference["authors"]
        )
        self.assertGreaterEqual(similarity, 0.4)

    def test_name_normalization(self):
        """Test if name normalization works correctly"""
        # Test various name formats
        test_cases = [
            ("Edward Z. Yang", "Edward Z Yang"),  # Remove period after initial
            ("Edward Yang", "Edward Yang"),
            ("Yang, Edward", "Edward Yang"),
            ("Yang, Edward Z.", "Edward Z Yang"),  # Remove period after initial
            ("Edward Z Yang", "Edward Z Yang"),
        ]

        for input_name, expected in test_cases:
            normalized = self.searcher._normalize_name(input_name)
            self.assertEqual(normalized, expected.lower())

    def test_full_conversion(self):
        """Test the full conversion process"""
        # Create a test BibTeX entry
        test_entry = {
            "ID": "paszke2019pytorchimperativestylehighperformance",
            "ENTRYTYPE": "misc",
            "title": "PyTorch: An Imperative Style, High-Performance Deep Learning Library",
            "author": "Adam Paszke and Sam Gross and Francisco Massa and Adam Lerer and James Bradbury and Gregory Chanan and Trevor Killeen and Zeming Lin and Natalia Gimelshein and Luca Antiga and Alban Desmaison and Andreas Köpf and Edward Yang and Zach DeVito and Martin Raison and Alykhan Tejani and Sasank Chilamkurthy and Benoit Steiner and Lu Fang and Junjie Bai and Soumith Chintala",
            "year": "2019",
            "eprint": "1912.01703",
            "archivePrefix": "arXiv",
            "primaryClass": "cs.LG",
            "url": "https://arxiv.org/abs/1912.01703",
        }

        # Search for DBLP entry
        dblp_info = self.searcher.search_publication(
            test_entry["title"], test_entry["author"].split(" and ")
        )

        # Verify the conversion
        self.assertIsNotNone(dblp_info)
        # Strip any trailing periods for comparison
        self.assertEqual(dblp_info["title"].rstrip("."), self.dblp_reference["title"])
        self.assertEqual(dblp_info["year"], self.dblp_reference["year"])
        self.assertEqual(dblp_info["venue"], self.dblp_reference["venue"])
        self.assertEqual(dblp_info["pages"], self.dblp_reference["pages"])
        self.assertEqual(dblp_info["ee"], self.dblp_reference["ee"])
        self.assertEqual(dblp_info["key"], self.dblp_reference["key"])

    def test_error_handling(self):
        """Test error handling for various edge cases"""
        # Test with empty title
        result = self.searcher.search_publication("", ["Adam Paszke"])
        self.assertIsNone(result)

        # Test with empty authors
        result = self.searcher.search_publication("PyTorch", [])
        self.assertIsNone(result)

        # Test with completely different title
        result = self.searcher.search_publication(
            "Completely Different Title", self.dblp_reference["authors"]
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
