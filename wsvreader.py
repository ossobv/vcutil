# vim: set ts=8 sw=4 sts=4 et ai tw=79:
# WJD/2013,2019
# WSV = Whitespace Separated Values
# TODO: add docs here
# TODO: replace "extra0" column name with "_columnN" where N is the Nth
# column. that makes more sense.
from __future__ import print_function, unicode_literals
import re
import unittest


class WsvReader(object):
    '''
    Whitespace-separated values reader.

    Usage::

        file = StringIO(
            '# This is a comment\\n'
            'column_name1    column_name2    optional_column\\n'
            'data1a          data1b\\n'
            '"data2a"        "data2b"        "data2c"\\n'
            '#"data3a"        "data3b"        "data23" commented out column\\n'
            '"" "column1 is empty, column2 has spaces and """\\n'
            'data4a data4b data4c data4d "column_names expand as necessary"\\n'
        )
        reader = WsvReader(file)
        for row in reader:
            print(row)

        # Yields this:

        # {'column_name1': 'data1a',
        #  'column_name2': 'data1b'}

        # {'column_name1': 'data2a',
        #  'column_name2': 'data2b',
        #  'optional_column': 'data2c'}

        # {'column_name1': '',
        #  'column_name2': 'column1 is empty, column2 has spaces and "'}

        # {'column_name1': 'data4a',
        #  'column_name2': 'data4b',
        #  'optional_column': 'data4c',
        #  'extra0': 'data4d',
        #  'extra1': 'column_names expand as necessary'}
    '''

    def __init__(self, file, dict=dict):
        self.file = file
        self.need_seek = False
        self.dict = dict
        self.findre = re.compile(r'\s([^"\s]*|"([^"]|"")*")\s')

    def __iter__(self):
        if self.need_seek:
            # Don't seek the first time. If we did, we couldn't read
            # unbuffered pipes.
            self.file.seek(0)
        else:
            self.need_seek = True

        self.fileiter = iter(self.file)
        self.read_header()
        return self

    def __next__(self):
        columns = self.split_line(self.get_line())

        # Ensure that the header is long enough.
        i = 0
        while len(columns) > len(self.columnnames):
            extra_columnname = 'extra%d' % (i,)
            if extra_columnname not in self.columnnames:
                self.columnnames.append(extra_columnname)
            i += 1

        return self.dict(zip(self.columnnames, columns))
    next = __next__  # py2 compat

    def read_header(self):
        self.columnnames = self.split_line(self.get_line())
        if len(self.columnnames) != len(set(self.columnnames)):
            raise ValueError('duplicate column names!')

    def get_line(self):
        # Fetch a new line. Skip all blank lines and comments.
        for line in self.fileiter:
            line = line.strip()
            if not line:
                continue
            if line[0] == '#':
                continue
            return line
        raise StopIteration()

    def unquote(self, column):
        # The column is never empty. Empty values should be enclosed
        # in double quotes.
        if column[0] == '"':
            assert column[-1] == '"'
            column = column[1:-1].replace('""', '"')
        return column

    def split_line(self, line):
        # We add space to both ends as sentinels.
        line = ' ' + line + ' '
        # Find the columns.
        columns = []
        pos = 0
        while True:
            match = self.findre.search(line, pos=pos)
            if not match:
                break
            value = match.groups()[0]
            if value:
                columns.append(self.unquote(value))
            pos = match.end() - 1
        return columns


class TestCase(unittest.TestCase):
    def test_init_0(self):
        "Require a single argument."
        self.assertRaises(TypeError, WsvReader)

    def test_init_1(self):
        "The most basic single argument example."
        from collections import OrderedDict
        file = self.get_file('col1 col2\ndata1 data2\n')

        # Pass only file, we get a regular dict as default.
        reader = WsvReader(file)

        data = [i for i in reader]
        self.assertEqual(data, [{'col1': 'data1', 'col2': 'data2'}])

        self.assertTrue(isinstance(data[0], dict))
        self.assertFalse(isinstance(data[0], OrderedDict))

    def test_init_2(self):
        "Supply a different dictionary type."
        from collections import OrderedDict
        file = self.get_file('col1 col2\ndata1 data2\n')

        # Pass file and dictionary type.
        reader = WsvReader(file, dict=OrderedDict)

        data = [i for i in reader]
        self.assertEqual(data, [{'col1': 'data1', 'col2': 'data2'}])

        self.assertTrue(isinstance(data[0], OrderedDict))

    def test_reiteration(self):
        "Iterate over the reader more than once."
        file = self.get_file('col1 col2\ndata1 data2\n')
        reader = WsvReader(file)

        data = [i for i in reader]
        self.assertEqual(data, [{'col1': 'data1', 'col2': 'data2'}])

        data2 = [i for i in reader]
        self.assertEqual(data, data2)

    def test_illegal_seek(self):
        "It works for the first run over a non-seekable file."
        file = self.get_file('col1 col2\ndata1 data2\n', seekable=False)
        reader = WsvReader(file)

        data = [i for i in reader]
        self.assertEqual(data, [{'col1': 'data1', 'col2': 'data2'}])

        try:
            data2 = [i for i in reader]
        except IOError:
            pass
        else:
            self.assertFalse('expected an Illegal seek, got %r' % (data2,))

    def test_spaces(self):
        "Spaces do not matter."
        self.compare_output(
            '''
                1st\t2nd     3rd
                data1   data2   \tdata3\t
                more data ok
            ''',
            [{'1st': 'data1', '2nd': 'data2', '3rd': 'data3'},
             {'1st': 'more', '2nd': 'data', '3rd': 'ok'}]
        )

    def test_blanks_and_comments(self):
        "Blanks and comments are ignored."
        self.compare_output(
            '''
                1st 2nd 3rd

                # this is a comment
                more #data #ok

                "#more" data #ok
            ''',
            [{'1st': 'more', '2nd': '#data', '3rd': '#ok'},
             {'1st': '#more', '2nd': 'data', '3rd': '#ok'}]
        )

    def test_double_quotes(self):
        "Double quotes can be used if values need spaces."
        self.compare_output(
            '''
                1st "2nd column" 3rd
                "" "data1 data2" "data3"
                """special"" data" is ok
            ''',
            [{'1st': '', '2nd column': 'data1 data2', '3rd': 'data3'},
             {'1st': '"special" data', '2nd column': 'is', '3rd': 'ok'}]
        )

    def test_too_few_values(self):
        "Missing columns aren't added in the dict."
        self.compare_output(
            '''
                1st "2nd column" 3rd
                only_first
                first "and second"
            ''',
            [{'1st': 'only_first'},
             {'1st': 'first', '2nd column': 'and second'}]
        )

    def test_too_many_values(self):
        "Extra columns are added as needed."
        self.compare_output(
            '''
                col1 extra1 col3
                d1 d2 d3
                d1 d2 d3 d4 d5 d6
                d1 d2 d3 d4
            ''',
            [{'col1': 'd1', 'extra1': 'd2', 'col3': 'd3'},
             {'col1': 'd1', 'extra1': 'd2', 'col3': 'd3',
              'extra0': 'd4', 'extra2': 'd5', 'extra3': 'd6'},
             {'col1': 'd1', 'extra1': 'd2', 'col3': 'd3',
              'extra0': 'd4'}]
        )

    def get_file(self, string, seekable=True):
        try:
            from io import StringIO
        except ImportError:
            from StringIO import StringIO

        if seekable:
            return StringIO(string)

        class NoSeekStringIO(StringIO):
            def seek(self, *args):
                raise IOError(29, 'Illegal seek')

        return NoSeekStringIO(string)

    def compare_output(self, string, dict_list):
        file = self.get_file(string)
        reader = WsvReader(file)
        data = [i for i in reader]
        return self.assertEqual(data, dict_list)


if __name__ == '__main__':
    from collections import OrderedDict
    import sys

    if len(sys.argv) == 1:
        files = [sys.stdin]

    elif sys.argv[1:] == ['TestCase']:
        unittest.main()

    else:
        files = [open(filename) for filename in sys.argv[1:]]

    for file in files:
        reader = WsvReader(file, dict=OrderedDict)
        if len(files) > 1:
            print('\n==> %s' % (file.name,))
        for row in reader:
            print(row)
        file.close()
