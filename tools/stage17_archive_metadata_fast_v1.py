"""Private cold metadata adapters; original authority and custody checks remain.

No global monkeypatch, ledger cache, skipped replay, or native measurement change.
Cloned callables retain the original code, defaults and closure. A private
physical_accounting override preserves the inventory rules using DirEntry.stat.
"""
from __future__ import annotations

import types

import stage17_archive_canonical_fast_v1 as fast
import stage17_formal_archive_custody_v1 as custody


def _clone(function, scope):
    result = types.FunctionType(function.__code__, scope, function.__name__,
                                function.__defaults__, function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    result.__annotations__ = dict(function.__annotations__)
    result.__dict__.update(function.__dict__)
    result.__qualname__ = function.__qualname__
    result.__module__ = function.__module__
    result.__doc__ = function.__doc__
    if hasattr(function, '__type_params__'):
        result.__type_params__ = function.__type_params__
    return result


def _archive_namespace(original):
    scope = dict(original.parse_json.__globals__)
    scope['canonical'] = fast.canonical
    return types.SimpleNamespace(**{**vars(original), 'canonical': fast.canonical,
                                    'parse_json': _clone(original.parse_json, scope)})


def _physical_accounting(self):
    """Exact custody inventory, with fresh scandir entries on every invocation."""
    self._check()
    total, logical, allocated, count, seen = 0, 0, 0, 0, set()

    def account(st, *, directory=False):
        nonlocal total, logical, allocated
        if not (stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode)):
            raise CustodyError('unexpected physical inventory object')
        identity = (st.st_dev, st.st_ino)
        if identity not in seen:
            seen.add(identity)
            disk = archive.checked_product(st.st_blocks, 512)
            logical = archive.checked_sum(logical, st.st_size)
            allocated = archive.checked_sum(allocated, disk)
            total = archive.checked_sum(total, max(st.st_size, disk))

    account(self.root.stat(follow_symlinks=False), directory=True)
    for name in self.DIRECTORIES:
        account((self.root / name).stat(follow_symlinks=False), directory=True)
    with os.scandir(self.root / 'working') as families:
        for family in families:
            archive.sha(family.name, 'working family namespace')
            account(family.stat(follow_symlinks=False), directory=True)
            with os.scandir(family.path) as children:
                for child in children:
                    count += 1
                    if count > self.limits.max_inventory_files:
                        raise CustodyError('working inventory limit')
                    # Preserve the raw-workspace exemption: every child counts
                    # towards the bound, only native checkpoint/receipt names
                    # are charged and type-checked here, exactly as before.
                    if re.fullmatch(r'formal-capture-[0-9]+-(final-checkpoint|archive-custody)\.json',
                                    child.name):
                        account(child.stat(follow_symlinks=False))
    for path in (self.root / 'scope.json', self.root / 'broker.lock'):
        account(path.stat(follow_symlinks=False))
    for name in ('archives', 'metadata', 'ledger'):
        with os.scandir(self.root / name) as entries:
            for entry in entries:
                count += 1
                if count > self.limits.max_inventory_files:
                    raise CustodyError('physical inventory limit')
                account(entry.stat(follow_symlinks=False))
    for family, name in getattr(self, '_retained_receipts', set()):
        account((self.root / 'working' / family / _name(name)).stat(follow_symlinks=False))
    return PhysicalUsage(logical, allocated, total, len(seen))


def make_store_class(base=custody.ProgramStore):
    """Snapshot a store's methods into one fresh private globals dictionary.

    The default is captured before any caller's test-scoped patch. No shared
    module/class member is written; each call yields an independent subclass.
    """
    scope = dict(base.__init__.__globals__)
    scope['archive'] = _archive_namespace(scope['archive'])
    members = {}
    for owner in reversed(base.__mro__[:-1]):
        for name, value in vars(owner).items():
            if name in ('__dict__', '__weakref__', '__module__', '__doc__'):
                continue
            if isinstance(value, types.FunctionType):
                members[name] = _clone(value, scope)
            elif isinstance(value, staticmethod):
                members[name] = staticmethod(_clone(value.__func__, scope))
            elif isinstance(value, classmethod):
                members[name] = classmethod(_clone(value.__func__, scope))
            elif isinstance(value, property):
                members[name] = property(
                    *(_clone(accessor, scope) if accessor is not None else None
                      for accessor in (value.fget, value.fset, value.fdel)), doc=value.__doc__)
            else:
                members[name] = value
    members.update(__module__=__name__, __doc__=base.__doc__,
                   physical_accounting=_clone(_physical_accounting, scope))
    result = type('MetadataFastProgramStore', (base,), members)
    scope['ProgramStore'] = result
    return result


def make_executor(original_v11_module):
    """Clone the v11 cold executor and its callbacks into one private scope.

    The returned namespace grants no execution authority. Its caller must pass
    the prepared arguments from the unchanged controller admission gates.
    Imported dependencies remain the same objects, except the two private
    archive/custody aliases. No sys.modules registration or mutation occurs.
    """
    scope = dict(vars(original_v11_module))
    scope['archive'] = _archive_namespace(original_v11_module.archive)
    scope['custody'] = types.SimpleNamespace(**{
        **vars(original_v11_module.custody),
        'ProgramStore': make_store_class(base=original_v11_module.custody.ProgramStore)})
    clones = {}
    for name, value in vars(original_v11_module).items():
        if isinstance(value, types.FunctionType) and value.__module__ == original_v11_module.__name__:
            if value not in clones:
                clones[value] = _clone(value, scope)
            scope[name] = clones[value]
    return types.SimpleNamespace(**scope)
