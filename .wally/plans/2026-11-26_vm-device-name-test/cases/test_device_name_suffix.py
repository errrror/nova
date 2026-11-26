# -*- coding: utf-8 -*-
"""隔离式单元测试：创建 VM 时 hypervisor 侧设备名带 -test 后缀。

直接加载 nova/virt/libvirt/config.py 并用 stub 满足其顶层依赖，绕开老版
Nova 在 Python 3.11 上无法完整安装的依赖链。测试真实执行 format_dom/to_xml。
"""
import importlib.util
import sys
import types
import unittest

from lxml import etree

_REPO = '/data/workspace/wally-open-8892/data/cli-workspaces/8c6976e5b5410415/7/nova'
_CONFIG_PATH = _REPO + '/nova/virt/libvirt/config.py'


def _stub(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


class _InternalError(Exception):
    pass


_stub('nova')
_stub('nova.exception', InternalError=_InternalError)
_stub('nova.i18n', _=lambda s: s)
_stub('nova.pci')
_stub('nova.pci.utils')
_stub('nova.virt')
_stub('nova.virt.hardware')

_spec = importlib.util.spec_from_file_location('lvconfig', _CONFIG_PATH)
config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(config)


def target_dev_from(xml_str):
    """提取 XML 中第一个 target 元素的 dev 属性。"""
    root = etree.fromstring(xml_str.encode('utf-8'))
    target = root.find('.//target')
    return None if target is None else target.get('dev')


class DeviceNameSuffixTest(unittest.TestCase):

    def _disk(self, dev):
        obj = config.LibvirtConfigGuestDisk()
        obj.source_type = 'file'
        obj.source_path = '/tmp/hello'
        obj.target_dev = dev
        obj.target_bus = 'virtio'
        return obj.to_xml()

    def _interface(self, dev):
        obj = config.LibvirtConfigGuestInterface()
        obj.net_type = 'bridge'
        obj.source_dev = 'br0'
        obj.mac_addr = '00:11:22:33:44:55'
        obj.target_dev = dev
        return obj.to_xml()

    def _snapshot_disk(self, dev):
        obj = config.LibvirtConfigGuestSnapshotDisk()
        obj.source_type = 'file'
        obj.source_path = '/tmp/hello'
        obj.target_dev = dev
        obj.target_bus = 'virtio'
        return obj.to_xml()

    # —— 正向：三类设备均追加 -test ——
    def test_u1_disk_suffix(self):
        self.assertEqual(target_dev_from(self._disk('vda')), 'vda-test')

    def test_u2_interface_suffix(self):
        self.assertEqual(target_dev_from(self._interface('tap12345678')),
                         'tap12345678-test')

    def test_u3_snapshot_disk_suffix(self):
        self.assertEqual(target_dev_from(self._snapshot_disk('vda')),
                         'vda-test')

    # —— 边界：幂等、空值、Unicode、路径形式 ——
    def test_u5_idempotent(self):
        self.assertEqual(target_dev_from(self._disk('vda-test')), 'vda-test')

    def test_u6_empty_dev(self):
        dev = target_dev_from(self._disk(''))
        self.assertIn(dev, ('', '-test'))

    def test_u7_unicode(self):
        self.assertEqual(target_dev_from(self._disk(u'磁\u76d8')),
                         u'磁\u76d8-test')

    def test_u8_path_form(self):
        self.assertEqual(target_dev_from(self._disk('/dev/hda')),
                         '/dev/hda-test')


if __name__ == '__main__':
    unittest.main(verbosity=2)
