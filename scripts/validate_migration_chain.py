#!/usr/bin/env python3
"""Validate the checked-out linear Alembic history without a hard-coded last revision."""
import ast
from pathlib import Path


def validate(directory):
    revisions = {}
    for path in sorted(Path(directory).glob('*.py')):
        if path.name == '__init__.py':
            continue
        values = {}
        for node in ast.parse(path.read_text(encoding='utf-8')).body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                name = node.targets[0]
                if isinstance(name, ast.Name) and name.id in ('revision', 'down_revision'):
                    values[name.id] = ast.literal_eval(node.value)
        revision = values.get('revision')
        if not isinstance(revision, str) or not revision or revision in revisions:
            raise ValueError(f'Invalid or duplicate revision in {path.name}')
        if 'down_revision' not in values:
            raise ValueError(f'Missing down_revision in {path.name}')
        parent = values['down_revision']
        if parent is not None and not isinstance(parent, str):
            raise ValueError(f'Expected linear history in {path.name}')
        revisions[revision] = parent
    if not revisions:
        raise ValueError('No Alembic revisions found')
    missing = set(revisions.values()) - set(revisions) - {None}
    if missing:
        raise ValueError(f'Missing parent revisions: {sorted(missing)}')
    heads = set(revisions) - set(revisions.values())
    if len(heads) != 1:
        raise ValueError(f'Expected one Alembic head, found {len(heads)}')
    head = next(iter(heads))
    visited = set()
    current = head
    while current is not None:
        if current in visited:
            raise ValueError('Cycle in Alembic revision history')
        visited.add(current)
        current = revisions[current]
    if visited != set(revisions):
        raise ValueError('Disconnected or cyclic Alembic revisions')
    return head, len(revisions)


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    head, count = validate(root / 'backend/alembic/versions')
    print('FULL_SOURCE_PREFLIGHT_SUCCESS', count, 'migrations; head:', head)
