"""Filler-word suggestions (P4 task 5b): shared/languages.filler_spans. Run: python -m unittest tests.test_fillers"""

import unittest

from shared import languages as L


def words(*toks):
    return [{"text": t, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, t in enumerate(toks)]


class Fillers(unittest.TestCase):
    def test_indonesian_incl_stretched_and_multiword(self):
        w = words("Eeeh,", "jadi", "anu", "itu", "apa", "namanya", "keren", "gitu.")
        spans = L.filler_spans(w, "id")
        self.assertEqual([(s["i0"], s["i1"], s["text"]) for s in spans],
                         [(0, 0, "Eeeh,"), (2, 2, "anu"), (4, 5, "apa namanya"), (7, 7, "gitu.")])
        self.assertEqual((spans[2]["start"], spans[2]["end"]), (2.0, 2.9))

    def test_english_multiword_longest_first(self):
        w = words("Um", "you", "know", "it's", "like", "I", "mean", "uhh")
        self.assertEqual([(s["i0"], s["i1"]) for s in L.filler_spans(w, "en")], [(0, 0), (1, 2), (4, 4), (5, 6), (7, 7)])

    def test_language_scoping_and_no_false_hits(self):
        w = words("you", "know", "gitu")
        self.assertEqual([s["text"] for s in L.filler_spans(w, "id")], ["gitu"])        # EN list not used
        self.assertEqual([s["text"] for s in L.filler_spans(w, "en")], ["you know"])
        self.assertEqual(len(L.filler_spans(w, None)), 2)                                 # unknown: both lists
        self.assertEqual(L.filler_spans(words("ehem", "mean", "known", "likely"), "en"), [])
        self.assertEqual(L.filler_spans([], "id"), [])

    def test_accepts_whisper_word_key(self):
        w = [{"word": " uh", "start": 1.0, "end": 1.2}]
        self.assertEqual(L.filler_spans(w, "en")[0]["text"], " uh")


if __name__ == "__main__":
    unittest.main()
