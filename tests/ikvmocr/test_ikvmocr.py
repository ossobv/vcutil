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
        glyphs = ikvmocr.ConsoleGlyphs()
        glyphs.set_active_size(8, 19)
        glyphs.set((0x704c28c2ca30a356, 0x2a51851661461), 'X')
        self.assertEqual(
            glyphs.get((0x704c28c2ca30a356, 0x2a51851661461)), 'X')


class CharTest(TestCase):
    maxDiff = 8192

    def test_char_open_paren(self):
        glyphs = ikvmocr.ConsoleGlyphs()
        char = ikvmocr.ConsoleChar.from_int63s(
            8, 16, glyphs._str_to_glyph_id('718e3ce3cf3cf3cf:279e09'))
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
        self.assertEqual(glyphs._str_from_glyph_id(char.as_int63s()), '718e3ce3cf3cf3cf:279e09')
