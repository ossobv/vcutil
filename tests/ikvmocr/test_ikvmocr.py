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


class IkvmOcrTest(TestCase):
    maxDiff = 16384

    def check_equal(self, screenshot_path, expected_text):
        glyphs = ikvmocr.ConsoleGlyphs()
        with open(DATA_DIR / 'ikvmocr.js') as fp:
            glyphs.load_from_file(fp)

        detected_text = ikvmocr.read_screenshot(screenshot_path, glyphs)
        formatted_text = '$\n'.join(detected_text.split('\n'))
        self.assertEqual(formatted_text, expected_text)

    def test_ikvmocr_1(self):
        self.check_equal(TEST_DIR / 'ikvmocr-1.png', '''\
Mapping table                                                                                       $
      FS1: Alias(s):CD2m0c0b:;BLK12:                                                                $
          PciRoot(0x0)/Pci(0x14,0x0)/USB(0xC,0x0)/USB(0x2,0x0)/CDROM(0x1,0xA6,0x5000)               $
      FS0: Alias(s):HD0c:;BLK2:                                                                     $
          PciRoot(0x0)/Pci(0x1,0x1)/Pci(0x0,0x0)/NVMe(0x1,00-01-0D-91-FD-E4-D2-5C)/HD(2,GPT,DFE346BA$
-05A8-4B9C-A6D2-6AB46D5FA0DF,0x1000,0xFF000)                                                        $
    BLK10: Alias(s):                                                                                $
          PciRoot(0x0)/Pci(0x14,0x0)/USB(0xC,0x0)/USB(0x2,0x0)                                      $
    BLK11: Alias(s):                                                                                $
          PciRoot(0x0)/Pci(0x14,0x0)/USB(0xC,0x0)/USB(0x2,0x0)/CDROM(0x0,0x32,0x4)                  $
     BLK0: Alias(s):                                                                                $
          PciRoot(0x0)/Pci(0x1,0x1)/Pci(0x0,0x0)/NVMe(0x1,00-01-0D-91-FD-E4-D2-5C)                  $
     BLK1: Alias(s):                                                                                $
          PciRoot(0x0)/Pci(0x1,0x1)/Pci(0x0,0x0)/NVMe(0x1,00-01-0D-91-FD-E4-D2-5C)/HD(1,GPT,C5F2CAD3$
-A55B-4A46-9393-21E767EF66E1,0x800,0x800)                                                           $
     BLK3: Alias(s):                                                                                $
          PciRoot(0x0)/Pci(0x1,0x1)/Pci(0x0,0x0)/NVMe(0x1,00-01-0D-91-FD-E4-D2-5C)/HD(3,GPT,95FE2216$
-4D13-410F-9860-89F19E431887,0x100000,0x200000)                                                     $
     BLK4: Alias(s):                                                                                $
          PciRoot(0x0)/Pci(0x1,0x1)/Pci(0x0,0x0)/NVMe(0x1,00-01-0D-91-FD-E4-D2-5C)/HD(4,GPT,DC32834D$
-8004-4B27-8562-BC02ED015794,0x300000,0x1D190BE8F)                                                  $
     BLK5: Alias(s):                                                                                $
          PciRoot(0x0)/Pci(0x1,0x2)/Pci(0x0,0x0)/NVMe(0x1,00-01-0D-92-12-E4-D2-5C)                  $
     BLK6: Alias(s):                                                                                $
          PciRoot(0x0)/Pci(0x1,0x2)/Pci(0x0,0x0)/NVMe(0x1,00-01-0D-92-12-E4-D2-5C)/HD(1,GPT,B8D1C30C$
-FDE5-403A-B87B-F4814BCE84C5,0x100,0x100)                                                           $
     BLK7: Alias(s):                                                                                $
          PciRoot(0x0)/Pci(0x1,0x2)/Pci(0x0,0x0)/NVMe(0x1,00-01-0D-92-12-E4-D2-5C)/HD(2,GPT,A1D16764$
-F97C-4E20-B3D1-B63DFC0092F6,0x200,0x1FE00)                                                         $
     BLK8: Alias(s):                                                                                $
Press ENTER to continue or 'Q' break:_                                                              $
''')

    def test_ikvmocr_2(self):
        self.check_equal(TEST_DIR / 'ikvmocr-2.png', '''\
Version 2.20.1276. Copyright (C) 2021 American Megatrends, Inc.                $
Supermicro X11SCE-F BIOS Date:06/01/2021 Rev:1.6                               $
                                                                               $
CPU : Intel(R) Xeon(R) E-2236 CPU @ 3.40GHz                                    $
 Speed : 3.40 GHz                                                              $
The IMC is operating with DDR4 2667 MHz                                        $
  Invoking Boot Menu                                                           $
                                                                               $
                                                                               $
                                                                               $
                                                                               $
                                                                               $
                                                                               $
                                                                               $
                                                                               $
                                                                               $
                                                                               $
                                                                               $
                                                                               $
Press DEL to run Setup                                                         $
Press F11 to invoke Boot Menu                                                  $
Press F12 to boot from PXE/LAN                                                 $
  DXE--SuperIO Initialization..                                                $
                                                                             99$
''')

    def test_ikvmocr_3(self):
        self.check_equal(TEST_DIR / 'ikvmocr-3.png', '''\
Ubuntu 22.04.5 LTS node1.dr.io.osso.cloud tty1                                                                                  $
                                                                                                                                $
node1 login: [27812653.946938] Memory cgroup out of memory: Killed process 3561120 (apt-cacher-ng) total-vm:10552492kB, anon-rss$
:1044464kB, file-rss:0kB, shmem-rss:0kB, UID:101 pgtables:2808kB oom_score_adj:996                                              $
[29555029.026327] Memory cgroup out of memory: Killed process 2544256 (beam.smp) total-vm:17168796kB, anon-rss:8332664kB, file-r$
ss:0kB, shmem-rss:61004kB, UID:1001 pgtables:17824kB oom_score_adj:-997                                                         $
''')

    def test_ikvmocr_4(self):
        self.check_equal(TEST_DIR / 'ikvmocr-4.png', '''\
Ubuntu 22.04.5 LTS node1.dr.io.osso.cloud tty1                                                                                  $
                                                                                                                                $
node1 login: [27812653.946938] Memory cgroup out of memory: Killed process 3561120 (apt-cacher-ng) total-vm:10552492kB, anon-rss$
:1044464kB, file-rss:0kB, shmem-rss:0kB, UID:101 pgtables:2808kB oom_score_adj:996                                              $
[29555029.026327] Memory cgroup out of memory: Killed process 2544256 (beam.smp) total-vm:17168796kB, anon-rss:8332664kB, file-r$
ss:0kB, shmem-rss:61004kB, UID:1001 pgtables:17824kB oom_score_adj:-997                                                         $
''')
