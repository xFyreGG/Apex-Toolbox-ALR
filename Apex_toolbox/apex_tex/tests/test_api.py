# -*- coding: utf-8 -*-
"""The add-on's calls into ``apex_tex`` must match what ``apex_tex`` accepts.

v3.7 beta 4 shipped with ``BUTTON_CUSTOM.execute`` passing
``remembered_roots=`` to ``apex_tex.autotex.run``.  The source tree, the ZIP
and the installed files all agreed -- but upgrading over a running older
install left the *old* ``autotex`` module in ``sys.modules``, so the new caller
reached an old callee and Blender raised::

    TypeError: run() got an unexpected keyword argument 'remembered_roots'

Two things guard against a repeat.  The add-on reloads its submodules on
re-enable and refuses to run when they still disagree (see
``APEX_TEX_API_VERSION``).  And this test statically checks every
``apex_<module>.<function>(...)`` call in ``Apex_toolbox/__init__.py`` against
the real signature, so a mismatch fails the suite rather than a user's click.

``__init__.py`` imports ``bpy``, so it is parsed with ``ast`` rather than
imported; the callees are imported normally because they are ``bpy``-free or
are only introspected.
"""

import ast
import inspect
import io
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)                 # .../Apex_toolbox/apex_tex
ADDON = os.path.dirname(PACKAGE)                # .../Apex_toolbox
sys.path.insert(0, ADDON)

#: ``alias used in __init__.py -> module name inside apex_tex``
ALIASES = {
    "apex_autotex": "autotex",
    "apex_roles": "roles",
    "apex_shaders": "shaders",
    "apex_resolver": "resolver",
}

#: Modules that import ``bpy`` and so cannot be imported by a plain CPython
#: test run.  Their signatures are read from the source instead.
BPY_MODULES = ("autotex", "shaders", "graph")


def _addon_source():
    with io.open(os.path.join(ADDON, "__init__.py"),
                 encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _module_source(name):
    with io.open(os.path.join(PACKAGE, name + ".py"),
                 encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _signatures(module_name):
    """``{function name: (positional names, keyword names, accepts **kwargs)}``.

    Read from source with ``ast`` for modules that need ``bpy``, and from the
    live object otherwise, so both paths are covered.
    """
    found = {}
    if module_name in BPY_MODULES:
        tree = ast.parse(_module_source(module_name))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            args = node.args
            names = [a.arg for a in list(args.posonlyargs) + list(args.args)]
            names += [a.arg for a in args.kwonlyargs]
            found[node.name] = (names, bool(args.kwarg))
    else:
        module = __import__("apex_tex." + module_name, fromlist=[module_name])
        for name, value in vars(module).items():
            if inspect.isfunction(value):
                parameters = inspect.signature(value).parameters
                names = [p for p in parameters]
                has_kwargs = any(
                    p.kind is inspect.Parameter.VAR_KEYWORD
                    for p in parameters.values())
                found[name] = (names, has_kwargs)
    return found


def _calls_into_apex_tex():
    """Every ``apex_<alias>.<attr>(...)`` call site in the add-on."""
    tree = ast.parse(_addon_source())
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        owner = func.value
        if not isinstance(owner, ast.Name) or owner.id not in ALIASES:
            continue
        keywords = [k.arg for k in node.keywords if k.arg is not None]
        positional = len(node.args)
        calls.append((ALIASES[owner.id], func.attr, positional, keywords,
                      node.lineno))
    return calls


class ApiContractTest(unittest.TestCase):

    def test_the_addon_calls_something(self):
        calls = _calls_into_apex_tex()
        self.assertTrue(calls, "no apex_tex calls found in __init__.py")
        self.assertIn(("autotex", "run"),
                      [(m, f) for m, f, _p, _k, _l in calls],
                      "the Auto Texture delegate is missing")

    def test_every_call_matches_its_callee(self):
        cache = {}
        for module_name, attr, positional, keywords, lineno in \
                _calls_into_apex_tex():
            if module_name not in cache:
                cache[module_name] = _signatures(module_name)
            signatures = cache[module_name]
            where = "__init__.py:%d -> apex_tex.%s.%s" % (
                lineno, module_name, attr)

            if attr not in signatures:
                # Constants and classes are addressed through the same alias.
                continue
            names, has_kwargs = signatures[attr]

            for keyword in keywords:
                self.assertTrue(
                    has_kwargs or keyword in names,
                    "%s passes %r, which the function does not accept "
                    "(accepts: %s)" % (where, keyword, ", ".join(names)))

            self.assertLessEqual(
                positional, len(names),
                "%s passes %d positional arguments but the function takes "
                "%d" % (where, positional, len(names)))

    def test_run_still_takes_the_beta4_discovery_arguments(self):
        """The arguments the beta 4 automatic discovery design relies on."""
        names, _ = _signatures("autotex")["run"]
        for required in ("texture_folder", "search_subfolders",
                         "remembered_roots", "remember_callback"):
            self.assertIn(required, names)

    def test_no_mutable_default_arguments(self):
        for module_name in ("roles", "naming", "paths", "roots", "resolver",
                            "autotex", "shaders", "graph"):
            tree = ast.parse(_module_source(module_name))
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                defaults = list(node.args.defaults) + [
                    d for d in node.args.kw_defaults if d is not None]
                for default in defaults:
                    self.assertNotIsInstance(
                        default, (ast.List, ast.Dict, ast.Set),
                        "%s.%s has a mutable default argument"
                        % (module_name, node.name))


class ApiVersionTest(unittest.TestCase):
    """The add-on and the package must agree on the internal API revision."""

    def test_package_declares_an_api_version(self):
        import apex_tex
        self.assertIsInstance(apex_tex.API_VERSION, int)

    def test_addon_expects_the_same_version(self):
        import apex_tex
        tree = ast.parse(_addon_source())
        expected = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) \
                            and target.id == "APEX_TEX_API_VERSION":
                        expected = node.value.value
        self.assertIsNotNone(
            expected, "__init__.py does not declare APEX_TEX_API_VERSION")
        self.assertEqual(
            expected, apex_tex.API_VERSION,
            "bump apex_tex.API_VERSION and APEX_TEX_API_VERSION together")

    def test_reload_order_covers_every_module(self):
        import apex_tex
        on_disk = set(
            name[:-3] for name in os.listdir(PACKAGE)
            if name.endswith(".py") and name != "__init__.py")
        self.assertEqual(
            set(apex_tex.RELOAD_ORDER), on_disk,
            "RELOAD_ORDER must list every apex_tex module so that a hot "
            "upgrade cannot leave a stale one behind")

    def test_reload_order_puts_dependencies_first(self):
        import apex_tex
        order = list(apex_tex.RELOAD_ORDER)
        for position, name in enumerate(order):
            tree = ast.parse(_module_source(name))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.level != 1:
                    continue
                for alias in node.names:
                    if alias.name in order:
                        self.assertLess(
                            order.index(alias.name), position,
                            "%s imports %s, so %s must be reloaded first"
                            % (name, alias.name, alias.name))


if __name__ == "__main__":
    unittest.main()
