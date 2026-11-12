import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/convert-runtime-to-c.py'

class IotPreservationTests(unittest.TestCase):
    def test_clean_keeps_runtime_support_and_prefers_manual(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'st'; target=root/'target'; manual=root/'manual'
            source.mkdir(); target.mkdir(); manual.mkdir()
            (source/'Block.st').write_text('FUNCTION_BLOCK Block\nEND_FUNCTION_BLOCK\n')
            (target/'Block.c').write_text('old implementation\n')
            (manual/'Block.c').write_text('correct implementation\n')
            (target/'Block.h').write_text('existing header\n')
            (manual/'Support.c').write_text('support without ST\n')
            (target/'CMakeLists.txt').write_text('build files\n')
            subprocess.run([sys.executable,str(SCRIPT),'--source-dir',str(source),
                '--target-dir',str(target),'--manual-preserve-root',str(manual),'--clean'],
                check=True,stdout=subprocess.PIPE)
            self.assertEqual((target/'Block.c').read_text(),'correct implementation\n')
            self.assertEqual((target/'Block.h').read_text(),'existing header\n')
            self.assertEqual((target/'Support.c').read_text(),'support without ST\n')
            self.assertEqual((target/'CMakeLists.txt').read_text(),'build files\n')

    def test_authoritative_corrections_match_compiled_files(self):
        component=ROOT/'iot-firmware/components/moqui'
        manual=ROOT/'iot-firmware/src-manual'
        for path in manual.rglob('*'):
            if path.suffix not in ('.c','.h'): continue
            compiled=component/path.relative_to(manual)
            if compiled.exists():
                self.assertEqual(path.read_text(encoding='utf-8-sig'), compiled.read_text(encoding='utf-8-sig'), str(path))
