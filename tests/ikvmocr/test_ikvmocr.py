from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader
from unittest import TestCase
from pathlib import Path


TEST_DIR = Path(__file__).parent
BIN_DIR = DATA_DIR = TEST_DIR / '..' / '..'


def load_script_as_module(path, module_name=None):
    if module_name is None:
        module_name = Path(path).name
    loader = SourceFileLoader(module_name, str(path))
    spec = spec_from_loader(module_name, loader)
    mod = module_from_spec(spec)
    # sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


ikvmocr = load_script_as_module(BIN_DIR / 'ikvmocr')


class GlyphTest(TestCase):
    def test_letter_X(self):
        glyph_id = (0x528c28b30a30b1c7, 0x61461651851ab2)
        glyphs = ikvmocr.ConsoleGlyphs()
        glyphs.set_active_size(8, 19)
        glyphs.set(glyph_id, 'X')
        self.assertEqual(glyphs.get(glyph_id), 'X')


class CharTest(TestCase):
    maxDiff = 8192

    def test_char_open_paren(self):
        glyph_id_str = '73cf3cf3ce3ce387:1239e48'
        glyphs = ikvmocr.ConsoleGlyphs()
        glyph_id = glyphs._str_to_glyph_id(glyph_id_str)
        char = ikvmocr.ConsoleChar.from_int63s(8, 16, glyph_id)
        self.assertEqual(char.as_string(), '''\
 -  -  -  -  -  -  -  - |
 -  -  -  -  - [X] -  - |
 -  -  -  - [X] -  -  - |
 -  -  -  - [X] -  -  - |
 -  -  - [X] -  -  -  - |
 -  -  - [X] -  -  -  - |
 -  -  - [X] -  -  -  - |
 -  -  - [X] -  -  -  - |
 -  -  - [X] -  -  -  - |
 -  -  - [X] -  -  -  - |
 -  -  -  - [X] -  -  - |
 -  -  -  - [X] -  -  - |
 -  -  -  -  - [X] -  - |
 -  -  -  -  -  -  -  - |
 -  -  -  -  -  -  -  - |
 -  -  -  -  -  -  -  - |''')
        self.assertEqual(char.as_int63s(), glyph_id)
