"""Keyword highlight stoplist (owner 2026-10-14). Run: python -m unittest tests.test_keyword_stopwords"""
import unittest

from shared import languages


class KeywordStopwords(unittest.TestCase):
    def test_owner_examples_and_both_languages(self):
        stop = languages.keyword_stopwords()
        for w in ("yang", "ya", "si", "itu", "ah", "gak", "ini", "the", "and", "like", "astaga", "wkwk", "guys"):
            self.assertIn(w, stop, w)

    def test_content_words_stay(self):
        stop = languages.keyword_stopwords()
        for w in ("molotov", "kekuatan", "polisi", "money", "jatuh", "turun"):
            self.assertNotIn(w, stop, w)

    def test_union_covers_each_language_list(self):
        stop = languages.keyword_stopwords()
        for code in languages.STOPWORDS:
            self.assertTrue(languages.stopwords_for(code) <= stop)


if __name__ == "__main__":
    unittest.main()
