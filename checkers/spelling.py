# Copyright 2014 Michal Nowikowski.
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""Checker for spelling errors in comments and docstrings.
"""

import sys
import tokenize
import string
import re

if sys.version_info[0] >= 3:
    maketrans = str.maketrans
else:
    maketrans = string.maketrans

import astroid

from pylint.interfaces import ITokenChecker, IAstroidChecker, IRawChecker
from pylint.checkers import BaseChecker, BaseTokenChecker
from pylint.checkers import utils
from pylint.checkers.utils import check_messages

try:
    import enchant
except ImportError:
    enchant = None

if enchant is not None:
    br = enchant.Broker()
    dicts = br.list_dicts()
    dict_choices = [''] + [d[0] for d in dicts]
    dicts = ["%s (%s)" % (d[0], d[1].name) for d in dicts]
    dicts = ", ".join(dicts)
    instr = ""
else:
    dicts = "none"
    dict_choices = ['']
    instr = " To make it working install python-enchant package."

table = maketrans("", "")

class SpellingChecker(BaseTokenChecker):
    """Check spelling in comments and docstrings"""
    __implements__ = (ITokenChecker, IAstroidChecker)
    name = 'spelling'
    msgs = {
        'C0401': ('Wrong spelling of a word \'%s\' in a comment:\n%s\n%s\nDid you mean: \'%s\'?',
                  'wrong-spelling-in-comment',
                  'Used when a word in comment is not spelled correctly.'),
        'C0402': ('Wrong spelling of a word \'%s\' in a docstring:\n%s\n%s\nDid you mean: \'%s\'?',
                  'wrong-spelling-in-docstring',
                  'Used when a word in docstring is not spelled correctly.'),
        }
    options = (('spelling-dict',
                {'default' : '', 'type' : 'choice', 'metavar' : '<dict name>',
                 'choices': dict_choices,
                 'help' : 'Spelling dictionary name. Available dictionaries: %s.%s' % (dicts, instr)}),
               ('spelling-ignore-words',
                {'default' : '', 'type' : 'string', 'metavar' : '<comma separated words>',
                 'help' : 'List of comma separated words that should not be checked.'}),
               ('spelling-private-dict-file',
                {'default' : '', 'type' : 'string', 'metavar' : '<path to file>',
                 'help' : 'A path to a file that contains private dictionary; one word per line.'}),
               ('spelling-store-unknown-words',
                {'default' : 'n', 'type' : 'yn', 'metavar' : '<y_or_n>',
                 'help' : 'Tells whether to store unknown words to indicated private dictionary'
                 ' in --spelling-private-dict-file option instead of raising a message.'}),
                 )

    def open(self):
        self.initialized = False
        self.private_dict_file = None

        if enchant is None:
            return

        dict_name = self.config.spelling_dict
        if not dict_name:
            return

        self.ignore_list = self.config.spelling_ignore_words.split(",")
        self.ignore_list.extend(["param",   # appears in docstring in param description
                                 "pylint",  # appears in comments in pylint pragmas
                                 ])

        if self.config.spelling_private_dict_file:
            self.spelling_dict = enchant.DictWithPWL(dict_name, self.config.spelling_private_dict_file)
            self.private_dict_file = open(self.config.spelling_private_dict_file, "a")
        else:
            self.spelling_dict = enchant.Dict(dict_name)

        if self.config.spelling_store_unknown_words:
            self.unknown_words = set()

        # prepare regex for stripping punctuation signs from text
        puncts = string.punctuation.replace("'", "").replace("_", "")  # ' and _ are treated in a special way
        self.punctuation_regex = re.compile('[%s]' % re.escape(puncts))

        self.initialized = True

    def close(self):
        if self.private_dict_file:
            self.private_dict_file.close()

    def _check_spelling(self, msgid, line, line_num):
        line2 = line.strip()
        line2 = re.sub("'([^a-zA-Z]|$)", " ", line2)  # replace ['afadf with afadf (but preserve don't)
        line2 = re.sub("([^a-zA-Z]|^)'", " ", line2)  # replace afadf'] with afadf (but preserve don't)
        line2 = self.punctuation_regex.sub(' ', line2)  # replace punctuation signs with space e.g. and/or -> and or

        words = []
        for word in line2.split():
            # skip words with digits
            if len(re.findall("\d", word)) > 0:
                continue

            # skip words with mixed big and small letters - they are probaly class names
            if len(re.findall("[A-Z]", word)) > 0 and len(re.findall("[a-z]", word)) > 0 and len(word) > 2:
                continue

            # skip words with _ - they are probably function parameter names
            if word.count('_') > 0:
                continue

            words.append(word)

        # go through words and check them
        for word in words:
            # skip words from ignore list
            if word in self.ignore_list:
                continue

            orig_word = word
            word = word.lower()

            # strip starting u' from unicode literals and r' from raw strings
            if (word.startswith("u'") or word.startswith('u"') or
                word.startswith("r'") or word.startswith('r"')) and len(word) > 2:
                word = word[2:]

            # if known word then continue
            if self.spelling_dict.check(word):
                continue

            # otherwise either store word to private dict or raise a message
            if self.config.spelling_store_unknown_words:
                if word not in self.unknown_words:
                    self.private_dict_file.write("%s\n" % word)
                    self.unknown_words.add(word)
            else:
                suggestions = self.spelling_dict.suggest(word)[:4]  # present upto 4 suggestions

                m = re.search("(\W|^)(%s)(\W|$)" % word, line.lower())
                if m:
                    col = m.regs[2][0]  # start position of second group in regex
                else:
                    col = line.lower().index(word)
                indicator = (" " * col) + ("^" * len(word))

                self.add_message(msgid, line=line_num,
                                 args=(orig_word, line, indicator, "' or '".join(suggestions)))

    def process_tokens(self, tokens):
        if not self.initialized:
            return

        # process tokens and look for comments
        for (tok_type, token, (start_row, start_col), _, _) in tokens:
            if tok_type == tokenize.COMMENT:
                self._check_spelling('wrong-spelling-in-comment', token, start_row)

    @check_messages('wrong-spelling-in-docstring')
    def visit_module(self, node):
        if not self.initialized:
            return
        self._check_docstring(node)

    @check_messages('wrong-spelling-in-docstring')
    def visit_class(self, node):
        if not self.initialized:
            return
        self._check_docstring(node)

    @check_messages('wrong-spelling-in-docstring')
    def visit_function(self, node):
        if not self.initialized:
            return
        self._check_docstring(node)

    def _check_docstring(self, node):
        """check the node has any spelling errors"""
        docstring = node.doc
        if not docstring:
            return

        start_line = node.lineno + 1

        # go through lines of docstring
        for idx, line in enumerate(docstring.splitlines()):
            self._check_spelling('wrong-spelling-in-docstring', line, start_line + idx)


def register(linter):
    """required method to auto register this checker """
    linter.register_checker(SpellingChecker(linter))