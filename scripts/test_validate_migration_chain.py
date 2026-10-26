import tempfile
import unittest
from pathlib import Path

from validate_migration_chain import validate


class MigrationChainTests(unittest.TestCase):
    def check_chain(self, entries):
        with tempfile.TemporaryDirectory() as temp:
            for index, (revision, parent) in enumerate(entries):
                Path(temp, f'{index:04d}.py').write_text(
                    f'revision={revision!r}\ndown_revision={parent!r}\n')
            return validate(temp)

    def test_current_history(self):
        head, count = validate(Path(__file__).resolve().parents[1] / 'backend/alembic/versions')
        self.assertTrue(head)
        self.assertGreater(count, 0)

    def test_future_migration_is_accepted(self):
        self.assertEqual(self.check_chain([('base', None), ('next', 'base'), ('future', 'next')]), ('future', 3))

    def test_invalid_histories_are_rejected(self):
        for entries in ([], [('a', 'missing')], [('a', None), ('a', None)],
                        [('a', None), ('b', None)], [('a', 'b'), ('b', 'a')],
                        [('a', None), ('b', 'c'), ('c', 'b')]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                self.check_chain(entries)


if __name__ == '__main__':
    unittest.main()
