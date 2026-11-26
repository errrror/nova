# -*- coding: utf-8 -*-
"""隔离运行器：在缺少完整 Nova 依赖的环境里加载真实 test_config.py。

通过 stub 满足 nova.test / nova.tests.unit.matchers / nova 顶层依赖，
用 lxml C14N 规范化做 XML 等价比较（覆盖 test_config.py 的 assertXmlEqual）。
仅用于本地验证，不作为源码提交。
"""
import importlib.util
import io
import os
import sys
import types
import unittest

from lxml import etree

_REPO = '/data/workspace/wally-open-8892/data/cli-workspaces/8c6976e5b5410415/7/nova'


def _stub(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


class _InternalError(Exception):
    pass


# --- stub nova 顶层与 config.py 的直接依赖 ---
_nova = _stub('nova')
_nova.__path__ = []
_stub('nova.exception', InternalError=_InternalError)
_stub('nova.i18n', _=lambda s: s)
_pci = _stub('nova.pci')
_pci.__path__ = []
_stub('nova.pci.utils')
_virt = _stub('nova.virt')
_virt.__path__ = []
_libvirt = _stub('nova.virt.libvirt')
_libvirt.__path__ = []
_stub('nova.virt.hardware')
_nova.pci = _pci
_nova.virt = _virt
_virt.libvirt = _libvirt

# --- stub oslo_utils.units（test_config.py 用到）---
# 真实 oslo_utils 已安装，保留。

# --- stub nova.objects.fields ---
_objects = _stub('nova.objects')
_objects.__path__ = []
_fields = _stub('nova.objects.fields')
_objects.fields = _fields
sys.modules['nova'].objects = _objects


def _canonical(xml_str):
    if isinstance(xml_str, str):
        xml_str = xml_str.encode('utf-8')
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_str, parser)
    return etree.tostring(root, method='c14n2')


class _XMLMatches(object):
    def __init__(self, expected):
        self.expected = expected

    def match(self, actual):
        try:
            return _canonical(self.expected) == _canonical(actual)
        except Exception:
            return False


def _assert_xml_equal(self, expected, actual):
    if _canonical(expected) != _canonical(actual):
        raise AssertionError(
            'XML mismatch.\nExpected:\n%s\nActual:\n%s' % (expected, actual))


class _NoDBTestCase(unittest.TestCase):
    def assertXmlEqual(self, expected, actual):
        _assert_xml_equal(self, expected, actual)

    def assertThat(self, value, matcher):
        result = matcher.match(value)
        if result is not None and result is not True:
            raise AssertionError('matcher failed: %s' % (result,))


_test_mod = _stub('nova.test', NoDBTestCase=_NoDBTestCase)
_matchers_mod = _stub('nova.tests.unit.matchers', XMLMatches=_XMLMatches)
_stub('nova.tests')
_stub('nova.tests.unit')
sys.modules['nova.tests'].unit = _matchers_mod
sys.modules['nova.tests.unit'].matchers = _matchers_mod
sys.modules['nova.test'] = _test_mod


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- 加载真实 config.py（被测代码）---
_config_path = os.environ.get('CONFIG_PATH',
                              _REPO + '/nova/virt/libvirt/config.py')
_real_config = _load('nova.virt.libvirt.config', _config_path)
sys.modules['nova.virt.libvirt.config'] = _real_config
_libvirt.config = _real_config

# --- 加载真实 test_config.py ---
_test_path = os.environ.get('TEST_PATH',
                            _REPO + '/nova/tests/unit/virt/libvirt/test_config.py')
_real_test = _load('real_test_config', _test_path)

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromModule(_real_test)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print('\nTOTAL=%d FAIL=%d ERROR=%d' %
          (result.testsRun, len(result.failures), len(result.errors)))
    sys.exit(0 if result.wasSuccessful() else 1)
