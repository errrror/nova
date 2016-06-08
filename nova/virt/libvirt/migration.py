# Copyright (c) 2016 Red Hat, Inc
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


"""Utility methods to manage guests migration

"""

from lxml import etree
from oslo_log import log as logging

from nova.i18n import _LI
from nova.i18n import _LW

LOG = logging.getLogger(__name__)

# TODO(berrange): hack to avoid a "import libvirt" in this file.
# Remove this and similar hacks in guest.py, driver.py, host.py
# etc in Ocata.
libvirt = None


def graphics_listen_addrs(migrate_data):
    """Returns listen addresses of vnc/spice from a LibvirtLiveMigrateData"""
    listen_addrs = None
    if (migrate_data.obj_attr_is_set('graphics_listen_addr_vnc')
        or migrate_data.obj_attr_is_set('graphics_listen_addr_spice')):
        listen_addrs = {'vnc': None, 'spice': None}
    if migrate_data.obj_attr_is_set('graphics_listen_addr_vnc'):
        listen_addrs['vnc'] = str(migrate_data.graphics_listen_addr_vnc)
    if migrate_data.obj_attr_is_set('graphics_listen_addr_spice'):
        listen_addrs['spice'] = str(
            migrate_data.graphics_listen_addr_spice)
    return listen_addrs


def serial_listen_addr(migrate_data):
    """Returns listen address serial from a LibvirtLiveMigrateData"""
    listen_addr = None
    if migrate_data.obj_attr_is_set('serial_listen_addr'):
        listen_addr = str(migrate_data.serial_listen_addr)
    return listen_addr


def get_updated_guest_xml(guest, migrate_data, get_volume_config):
    xml_doc = etree.fromstring(guest.get_xml_desc(dump_migratable=True))
    xml_doc = _update_graphics_xml(xml_doc, migrate_data)
    xml_doc = _update_serial_xml(xml_doc, migrate_data)
    xml_doc = _update_volume_xml(xml_doc, migrate_data, get_volume_config)
    return etree.tostring(xml_doc)


def _update_graphics_xml(xml_doc, migrate_data):
    listen_addrs = graphics_listen_addrs(migrate_data)

    # change over listen addresses
    for dev in xml_doc.findall('./devices/graphics'):
        gr_type = dev.get('type')
        listen_tag = dev.find('listen')
        if gr_type in ('vnc', 'spice'):
            if listen_tag is not None:
                listen_tag.set('address', listen_addrs[gr_type])
            if dev.get('listen') is not None:
                dev.set('listen', listen_addrs[gr_type])
    return xml_doc


def _update_serial_xml(xml_doc, migrate_data):
    listen_addr = serial_listen_addr(migrate_data)
    for dev in xml_doc.findall("./devices/serial[@type='tcp']/source"):
        if dev.get('host') is not None:
            dev.set('host', listen_addr)
    for dev in xml_doc.findall("./devices/console[@type='tcp']/source"):
        if dev.get('host') is not None:
            dev.set('host', listen_addr)
    return xml_doc


def _update_volume_xml(xml_doc, migrate_data, get_volume_config):
    """Update XML using device information of destination host."""
    migrate_bdm_info = migrate_data.bdms

    # Update volume xml
    parser = etree.XMLParser(remove_blank_text=True)
    disk_nodes = xml_doc.findall('./devices/disk')

    bdm_info_by_serial = {x.serial: x for x in migrate_bdm_info}
    for pos, disk_dev in enumerate(disk_nodes):
        serial_source = disk_dev.findtext('serial')
        bdm_info = bdm_info_by_serial.get(serial_source)
        if (serial_source is None or
            not bdm_info or not bdm_info.connection_info or
            serial_source not in bdm_info_by_serial):
            continue
        conf = get_volume_config(
            bdm_info.connection_info, bdm_info.as_disk_info())
        xml_doc2 = etree.XML(conf.to_xml(), parser)
        serial_dest = xml_doc2.findtext('serial')

        # Compare source serial and destination serial number.
        # If these serial numbers match, continue the process.
        if (serial_dest and (serial_source == serial_dest)):
            LOG.debug("Find same serial number: pos=%(pos)s, "
                      "serial=%(num)s",
                      {'pos': pos, 'num': serial_source})
            for cnt, item_src in enumerate(disk_dev):
                # If source and destination have same item, update
                # the item using destination value.
                for item_dst in xml_doc2.findall(item_src.tag):
                    disk_dev.remove(item_src)
                    item_dst.tail = None
                    disk_dev.insert(cnt, item_dst)

            # If destination has additional items, thses items should be
            # added here.
            for item_dst in list(xml_doc2):
                item_dst.tail = None
                disk_dev.insert(cnt, item_dst)
    return xml_doc


def find_job_type(guest, instance):
    """Determine the (likely) current migration job type

    :param guest: a nova.virt.libvirt.guest.Guest
    :param instance: a nova.objects.Instance

    Annoyingly when job type == NONE and migration is
    no longer running, we don't know whether we stopped
    because of failure or completion. We can distinguish
    these cases by seeing if the VM still exists & is
    running on the current host

    :returns: a libvirt job type constant
    """
    try:
        if guest.is_active():
            LOG.debug("VM running on src, migration failed",
                      instance=instance)
            return libvirt.VIR_DOMAIN_JOB_FAILED
        else:
            LOG.debug("VM is shutoff, migration finished",
                      instance=instance)
            return libvirt.VIR_DOMAIN_JOB_COMPLETED
    except libvirt.libvirtError as ex:
        LOG.debug("Error checking domain status %(ex)s",
                  {"ex": ex}, instance=instance)
        if ex.get_error_code() == libvirt.VIR_ERR_NO_DOMAIN:
            LOG.debug("VM is missing, migration finished",
                      instance=instance)
            return libvirt.VIR_DOMAIN_JOB_COMPLETED
        else:
            LOG.info(_LI("Error %(ex)s, migration failed"),
                     {"ex": ex}, instance=instance)
            return libvirt.VIR_DOMAIN_JOB_FAILED


def should_abort(instance, now,
                 progress_time, progress_timeout,
                 elapsed, completion_timeout):
    """Determine if the migration should be aborted

    :param instance: a nova.objects.Instance
    :param now: current time in secs since epoch
    :param progress_time: when progress was last made in secs since epoch
    :param progress_timeout: time in secs to allow for progress
    :param elapsed: total elapsed time of migration in secs
    :param completion_timeout: time in secs to allow for completion

    Check the progress and completion timeouts to determine if either
    of them have been hit, and should thus cause migration to be aborted

    :returns: True if migration should be aborted, False otherwise
    """
    if (progress_timeout != 0 and
            (now - progress_time) > progress_timeout):
        LOG.warning(_LW("Live migration stuck for %d sec"),
                    (now - progress_time), instance=instance)
        return True

    if (completion_timeout != 0 and
            elapsed > completion_timeout):
        LOG.warning(
            _LW("Live migration not completed after %d sec"),
            completion_timeout, instance=instance)
        return True

    return False


def update_downtime(guest, instance,
                    olddowntime,
                    downtime_steps, elapsed):
    """Update max downtime if needed

    :param guest: a nova.virt.libvirt.guest.Guest to set downtime for
    :param instance: a nova.objects.Instance
    :param olddowntime: current set downtime, or None
    :param downtime_steps: list of downtime steps
    :param elapsed: total time of migration in secs

    Determine if the maximum downtime needs to be increased
    based on the downtime steps. Each element in the downtime
    steps list should be a 2 element tuple. The first element
    contains a time marker and the second element contains
    the downtime value to set when the marker is hit.

    The guest object will be used to change the current
    downtime value on the instance.

    Any errors hit when updating downtime will be ignored

    :returns: the new downtime value
    """
    LOG.debug("Current %(dt)s elapsed %(elapsed)d steps %(steps)s",
              {"dt": olddowntime, "elapsed": elapsed,
               "steps": downtime_steps}, instance=instance)
    thisstep = None
    for step in downtime_steps:
        if elapsed > step[0]:
            thisstep = step

    if thisstep is None:
        LOG.debug("No current step", instance=instance)
        return olddowntime

    if thisstep[1] == olddowntime:
        LOG.debug("Downtime does not need to change",
                  instance=instance)
        return olddowntime

    LOG.info(_LI("Increasing downtime to %(downtime)d ms "
                 "after %(waittime)d sec elapsed time"),
             {"downtime": thisstep[1],
              "waittime": thisstep[0]},
             instance=instance)

    try:
        guest.migrate_configure_max_downtime(thisstep[1])
    except libvirt.libvirtError as e:
        LOG.warning(_LW("Unable to increase max downtime to %(time)d"
                        "ms: %(e)s"),
                    {"time": thisstep[1], "e": e}, instance=instance)
    return thisstep[1]


def save_stats(instance, migration, info, remaining):
    """Save migration stats to the database

    :param instance: a nova.objects.Instance
    :param migration: a nova.objects.Migration
    :param info: a nova.virt.libvirt.guest.JobInfo
    :param remaining: percentage data remaining to transfer

    Update the migration and instance objects with
    the latest available migration stats
    """

    # The fully detailed stats
    migration.memory_total = info.memory_total
    migration.memory_processed = info.memory_processed
    migration.memory_remaining = info.memory_remaining
    migration.disk_total = info.disk_total
    migration.disk_processed = info.disk_processed
    migration.disk_remaining = info.disk_remaining
    migration.save()

    # The coarse % completion stats
    instance.progress = 100 - remaining
    instance.save()
