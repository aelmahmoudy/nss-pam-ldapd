
# expr.py - expression handling functions
#
# Copyright (C) 2011, 2012, 2013 Arthur de Jong
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301 USA

"""Module for handling expressions used for LDAP searches.

>>> expr = Expression('foo=$foo')
>>> expr.value(dict(foo='XX'))
'foo=XX'
>>> expr = Expression('foo=${foo:-$bar}')
>>> expr.value(dict(foo='', bar='YY'))
'foo=YY'
>>> expr.value(dict(bar=['YY', 'ZZ']))
'foo=YY'
>>> Expression(r'${passwd#{crypt\}}').value(dict(passwd='{crypt}HASH'))
'HASH'
>>> Expression('${var#trim}').value(dict(var='notrimme'))
'notrimme'
>>> Expression('${var#?trim}').value(dict(var='xtrimme'))
'me'
>>> Expression('${var#*trim}').value(dict(var='xxxtrimme'))
'me'
>>> Expression('${var%.txt}').value(dict(var='foo.txt'))
'foo'
>>> Expression('${x#$y}').value(dict(x='a/b', y='a'))
'/b'
>>> Expression('${var#t*is}').value(dict(var='this is a test'))
' is a test'
>>> Expression('${var##t*is}').value(dict(var='this is a test'))
' a test'
>>> Expression('${var%t*st}').value(dict(var='this is a test'))
'this is a '
>>> Expression('${var%%t*st}').value(dict(var='this is a test'))
''
"""

import fnmatch
import re


# exported names
__all__ = ('Expression', )


# TODO: do more expression validity checking


class MyIter(object):
    """Custom iterator-like class with a back() method."""

    def __init__(self, value):
        self.value = value
        self.pos = 0

    def next(self):
        self.pos += 1
        try:
            return self.value[self.pos - 1]
        except IndexError:
            return None

    def back(self):
        self.pos -= 1

    def __iter__(self):
        return self

    def get_name(self):
        """Read a variable name from the value iterator."""
        name = ''
        for c in self:
            if not c or not c.isalnum():
                self.back()
                return name
            name += c
        return name


class DollarExpression(object):
    """Class for handling a variable $xxx ${xxx}, ${xxx:-yyy} or ${xxx:+yyy}
    expression."""

    def __init__(self, value):
        """Parse the expression as the start of a $-expression."""
        self.op = None
        self.expr = None
        c = value.next()
        if c == '{':
            self.name = value.get_name()
            c = value.next()
            if c == '}':
                return
            elif c == ':':
                self.op = c + value.next()
            elif c in ('#', '%'):
                c2 = value.next()
                if c2 in ('#', '%'):
                    c += c2
                else:
                    value.back()
                self.op = c
            else:
                raise ValueError('Expecting operator')
            self.expr = Expression(value, endat='}')
        elif c == '(':
            self.name = None
            self.op = value.get_name()
            c = value.next()
            if c != '(':
                raise ValueError("Expecting '('")
            self.expr = Expression(value, endat=')')
            c = value.next()
            if c != ')':
                raise ValueError("Expecting ')'")
        else:
            value.back()
            self.name = value.get_name()

    def value(self, variables):
        """Expand the expression using the variables specified."""
        # lookup the value
        value = variables.get(self.name, '')
        if value in (None, [], ()):
            value = ''
        elif isinstance(value, (list, tuple)):
            value = value[0]
        # TODO: try to return multiple values, one for each value of the list
        if self.op == ':-':
            return value if value else self.expr.value(variables)
        elif self.op == ':+':
            return self.expr.value(variables) if value else ''
        elif self.op in ('#', '##', '%', '%%'):
            match = fnmatch.translate(self.expr.value(variables))
            if self.op == '#':
                match = match.replace('*', '*?').replace(r'\Z', r'(?P<replace>.*)\Z')
            elif self.op == '##':
                match = match.replace(r'\Z', r'(?P<replace>.*?)\Z')
            elif self.op == '%':
                match = r'(?P<replace>.*)' + match.replace('*', '*?')
            elif self.op == '%%':
                match = r'(?P<replace>.*?)' + match
            match = re.match(match, value)
            return match.group('replace') if match else value
        elif self.op == 'lower':
            return self.expr.value(variables).lower()
        elif self.op == 'upper':
            return self.expr.value(variables).upper()
        return value

    def variables(self, results):
        """Add the variables used in the expression to results."""
        if self.name:
            results.add(self.name)
        if self.expr:
            self.expr.variables(results)


class Expression(object):
    """Class for parsing and expanding an expression."""

    def __init__(self, value, endat=None):
        """Parse the expression as a string."""
        if not isinstance(value, MyIter):
            self.expression = value
            value = MyIter(value)
        expr = []
        literal = ''
        c = value.next()
        while c != endat:
            if c == '$':
                if literal:
                    expr.append(literal)
                expr.append(DollarExpression(value))
                literal = ''
            elif c == '\\':
                literal += value.next()
            else:
                literal += c
            c = value.next()
        if literal:
            expr.append(literal)
        self.expr = expr

    def value(self, variables):
        """Expand the expression using the variables specified."""
        res = ''
        for x in self.expr:
            if hasattr(x, 'value'):
                res += x.value(variables)
            else:
                res += x
        return res

    def variables(self, results=None):
        """Return the variables defined in the expression."""
        if not results:
            results = set()
        for x in self.expr:
            if hasattr(x, 'variables'):
                x.variables(results)
        return results

    def __str__(self):
        return self.expression

    def __repr__(self):
        return repr(str(self))
