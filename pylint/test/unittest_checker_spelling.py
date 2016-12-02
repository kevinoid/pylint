# Copyright (c) 2014-2016 Claudiu Popa <pcmanticore@gmail.com>

# Licensed under the GPL: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
# For details: https://github.com/PyCQA/pylint/blob/master/COPYING

"""Unittest for the spelling checker."""

import os.path
import unittest

import astroid

from pylint.checkers import spelling
from pylint.testutils import (
    CheckerTestCase, Message, set_config, tokenize_str,
)

try:
    import enchant
except ImportError:
    enchant = None

private_dict = os.path.join(os.path.dirname(__file__), 'data', 'wordlist.txt')


class SpellingCheckerTest(CheckerTestCase):
    CHECKER_CLASS = spelling.SpellingChecker

    @unittest.skipIf(enchant is None, "missing python-enchant package")
    @set_config(spelling_private_dict_file=private_dict)
    def test_check_bad_coment(self):
        with self.assertAddsMessages(
            Message('wrong-spelling-in-comment', line=1,
                    args=('coment', '# bad coment',
                          '      ^^^^^^',
                          "comment' or 'moment"))):
            self.checker.process_tokens(tokenize_str("# bad coment"))

    @unittest.skipIf(enchant is None, "missing python-enchant package")
    @set_config(spelling_private_dict_file=private_dict)
    def test_check_bad_docstring(self):
        stmt = astroid.extract_node(
            'def fff():\n   """bad coment"""\n   pass')
        with self.assertAddsMessages(
            Message('wrong-spelling-in-docstring', line=2,
                    args=('coment', 'bad coment',
                          '    ^^^^^^',
                          "comment' or 'moment"))):
            self.checker.visit_functiondef(stmt)

        stmt = astroid.extract_node(
            'class Abc(object):\n   """bad coment"""\n   pass')
        with self.assertAddsMessages(
            Message('wrong-spelling-in-docstring', line=2,
                    args=('coment', 'bad coment',
                          '    ^^^^^^',
                          "comment' or 'moment"))):
            self.checker.visit_classdef(stmt)

    @unittest.skipIf(enchant is None, "missing python-enchant package")
    @set_config(spelling_private_dict_file=private_dict)
    def test_invalid_docstring_characters(self):
        stmt = astroid.extract_node(
            'def fff():\n   """test\\x00"""\n   pass')
        with self.assertAddsMessages(
            Message('invalid-characters-in-docstring', line=2,
                    args=('test\x00',))):
            self.checker.visit_functiondef(stmt)


if __name__ == '__main__':
    unittest.main()
