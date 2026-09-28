from contextlib import redirect_stderr, redirect_stdout
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from io import StringIO
from pathlib import Path
from unittest import TestCase, mock
import os
import time

BIN_DIR = Path(__file__).parent / '..' / '..'


def load_script_as_module(path, module_name=None):
    if module_name is None:
        module_name = Path(path).name
    loader = SourceFileLoader(module_name, str(path))
    spec = spec_from_loader(module_name, loader)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


zabdig = load_script_as_module(BIN_DIR / 'zabdig')


def make_host(hostid, name, ip, proxyid='0', available='1', status='0'):
    "A host.get result, the way zabbix 7 returns it."
    return {
        'hostid': hostid,
        'name': name,
        'host': name,
        'status': status,
        'proxyid': proxyid,
        'available': available,
        'inventory': {},
        'groups': [],
        'interfaces': [{
            'type': '1', 'useip': '1', 'ip': ip, 'dns': '',
            'available': available}],
    }


HOSTS = [
    make_host('101', 'walter.internal.lan', '10.32.1.5', proxyid='1'),
    make_host('102', 'walterdev.example.com', '192.0.2.9'),
    make_host('103', 'pve1', '10.0.0.1'),
    make_host('104', 'pve1.dr', '10.0.1.1'),
]
PROXIES = [{'proxyid': '1', 'name': 'zabbix-proxy-lan'}]


class FakeZabbix(object):
    """
    Stands in for the network: answers the API calls with canned data and
    records them, so tests can check what was asked.
    """
    def __init__(self, **responses):
        self.responses = {
            'apiinfo.version': '7.0.5',
            'user.login': 'TOKEN',
            'host.get': HOSTS,
            'proxy.get': PROXIES,
        }
        self.responses.update(responses)
        self.calls = []

    def post(self, zinterface, url, data):
        self.calls.append((data['method'], data['params']))
        response = self.responses[data['method']]
        return response(data['params']) if callable(response) else response

    def params_of(self, method):
        return [params for meth, params in self.calls if meth == method]


class ZabdigTestCase(TestCase):
    def setUp(self):
        # Never read the real ~/.zabbixrc or the keyring.
        patcher = mock.patch.object(zabdig, 'CONF_FILE', '/nonexistent/rc')
        patcher.start()
        self.addCleanup(patcher.stop)

        # Alert timestamps are shown in local time.
        old_tz = os.environ.get('TZ')
        os.environ['TZ'] = 'UTC'
        time.tzset()

        def restore_tz():
            if old_tz is None:
                del os.environ['TZ']
            else:
                os.environ['TZ'] = old_tz
            time.tzset()
        self.addCleanup(restore_tz)

        self.fake = FakeZabbix()

    def zabdig(self, *args, **responses):
        "Run zabdig main(), return (exitcode, stdout, stderr)."
        self.fake.responses.update(responses)
        argv = ['-A', 'http://zabbix.invalid/api', '-u', 'me', '-p', 'pw']
        argv.extend(args)
        out, err = StringIO(), StringIO()
        with mock.patch.object(
                zabdig.ZInterface, '_zabbix_post',
                lambda zint, url, data: self.fake.post(zint, url, data)):
            with redirect_stdout(out), redirect_stderr(err):
                ret = zabdig.main(argv)
        return ret, out.getvalue(), err.getvalue()


class NeedleTest(TestCase):
    def test_exact_and_contains(self):
        needle = zabdig.Needle('pve1')
        self.assertTrue(needle.is_exactly('pve1'))
        self.assertFalse(needle.is_exactly('pve1.dr'))
        self.assertTrue(needle.is_found_in('pve1.dr'))
        self.assertTrue(needle.is_found_in('mypve1'))
        self.assertFalse(needle.is_found_in('pve2'))

    def test_wildcards(self):
        needle = zabdig.Needle('pve?.dr.*')
        self.assertTrue(needle.is_exactly('pve1.dr.example.com'))
        self.assertFalse(needle.is_exactly('pve12.dr.example.com'))
        self.assertTrue(needle.is_found_in('xpve1.dr.example.com'))

    def test_as_string_is_longest_static_part(self):
        self.assertEqual(zabdig.Needle('pve?.dr.osso.cloud').as_string(),
                         '.dr.osso.cloud')
        self.assertEqual(zabdig.Needle('walter').as_string(), 'walter')


class HostLookupTest(ZabdigTestCase):
    def test_single_exact_match_prints_only_the_address(self):
        # This is what scripts like zssh rely on.
        ret, out, err = self.zabdig('walter.internal.lan')
        self.assertEqual((ret, out, err), (0, '10.32.1.5\n', ''))

    def test_search_is_sent_to_the_server_as_longest_static_part(self):
        self.zabdig('pve?.dr')
        self.assertEqual(
            self.fake.params_of('host.get')[0]['search'], {'name': '.dr'})

    def test_multiple_matches_are_listed_sorted_with_proxy(self):
        ret, out, err = self.zabdig('walter')
        self.assertEqual(ret, 0)
        self.assertEqual(out, (
            '{:30}  10.32.1.5 (zabbix-proxy-lan)\n'
            '{:30}  192.0.2.9\n'
        ).format('walter.internal.lan', 'walterdev.example.com'))

    def test_all_flag_lists_matches_despite_exact_match(self):
        ret, out, err = self.zabdig('pve1')
        self.assertEqual(out, '10.0.0.1\n')
        ret, out, err = self.zabdig('-a', 'pve1')
        self.assertEqual(out, (
            '{:30}  10.0.0.1\n'
            '{:30}  10.0.1.1\n'
        ).format('pve1', 'pve1.dr'))

    def test_filter_by_ip(self):
        ret, out, err = self.zabdig('-x', '10.0.1.1', 'pve')
        self.assertEqual(out, '{:30}  10.0.1.1\n'.format('pve1.dr'))

    def test_no_search_lists_everything(self):
        ret, out, err = self.zabdig()
        self.assertEqual(ret, 0)
        self.assertEqual(len(out.splitlines()), len(HOSTS))
        self.assertNotIn('search', self.fake.params_of('host.get')[0])

    def test_down_and_disabled_hosts_are_marked(self):
        hosts = [
            make_host('1', 'up1', '10.0.0.1'),
            make_host('2', 'down1', '10.0.0.2', available='2'),
            make_host('3', 'off1', '10.0.0.3', status='1'),
        ]
        ret, out, err = self.zabdig(**{'host.get': hosts})
        self.assertEqual(out.splitlines(), [
            '{:30}  10.0.0.2'.format('down1--DOWN'),
            '{:30}  10.0.0.3'.format('off1--OFF'),
            '{:30}  10.0.0.1'.format('up1'),
        ])

    def test_nothing_found(self):
        ret, out, err = self.zabdig('nonexistent')
        self.assertEqual((ret, out), (1, ''))
        self.assertEqual(err, 'nothing found\n')

    def test_show_host(self):
        ret, out, err = self.zabdig('--show=host', 'walter.internal.lan')
        self.assertEqual(ret, 0)
        self.assertEqual(out, (
            '[walter.internal.lan]\n'
            'Status = ON\n'
            'Address = 10.32.1.5\n'
            'ExternalIP4 = None\n'
            'Proxy = zabbix-proxy-lan\n'
            '\n'))

    def test_api_errors_are_reported(self):
        def fail(params):
            raise zabdig.ZInterfaceError({'message': 'nope'})
        ret, out, err = self.zabdig(**{'host.get': fail})
        self.assertEqual(ret, 1)
        self.assertIn('fetch failed', err)


class AlertsTest(ZabdigTestCase):
    PROBLEM = {
        'eventid': '1', 'r_eventid': '0', 'objectid': '55',
        'clock': '1700000000', 'ns': '0', 'severity': '4',
        'suppressed': '0', 'name': 'Disk full', 'opdata': '',
    }
    TRIGGER = {
        'triggerid': '55', 'status': '0', 'error': '', 'suppressed': '0',
        'flags': '0', 'value': '1',
        'hosts': [{'hostid': '101', 'host': 'web1', 'status': '0'}],
        'items': [{'hostid': '101', 'status': '0'}],
    }

    def test_current_alerts(self):
        ret, out, err = self.zabdig(
            '--show=alerts', **{
                'problem.get': [dict(self.PROBLEM)],
                'trigger.get': [dict(self.TRIGGER)]})
        self.assertEqual(ret, 0)
        self.assertEqual(out, (
            'alert:HIGH 2023-11-14T22:13:20: Disk full (web1)\n'
            '1\n'))

    def test_default_severity_is_disaster_and_high(self):
        self.zabdig(
            '--show=alerts', **{'problem.get': [], 'trigger.get': []})
        self.assertEqual(
            self.fake.params_of('problem.get')[0]['severities'], [5, 4])

    def test_alerts_on_disabled_host_are_skipped(self):
        trigger = dict(self.TRIGGER)
        trigger['hosts'] = [
            {'hostid': '101', 'host': 'web1', 'status': '1'}]
        ret, out, err = self.zabdig(
            '--show=alerts', **{
                'problem.get': [dict(self.PROBLEM)],
                'trigger.get': [trigger]})
        self.assertEqual(out, '0\n')

    def test_alert_on_multiple_hosts_is_listed_per_host(self):
        trigger = dict(self.TRIGGER)
        trigger['hosts'] = [
            {'hostid': '101', 'host': 'web1', 'status': '0'},
            {'hostid': '102', 'host': 'web2', 'status': '0'}]
        trigger['items'] = [
            {'hostid': '101', 'status': '0'},
            {'hostid': '102', 'status': '0'}]
        ret, out, err = self.zabdig(
            '--show=alerts', **{
                'problem.get': [dict(self.PROBLEM)],
                'trigger.get': [trigger]})
        self.assertEqual(out.splitlines()[-3:], [
            'alert:HIGH 2023-11-14T22:13:20: Disk full (web1)',
            'alert:HIGH 2023-11-14T22:13:20: Disk full (web2)',
            '2'])


class DataTest(ZabdigTestCase):
    ITEM = {
        'itemid': '9', 'hostid': '1', 'name': 'Free space',
        'key_': 'vfs.fs.size[/,pfree]', 'units': '%', 'lastclock': '0',
        'lastvalue': '42', 'prevvalue': '41'}

    def test_items_imply_data_mode(self):
        ret, out, err = self.zabdig(
            '--items', 'vfs.fs.size[/,pfree]', 'web1', **{
                'host.get': [make_host('1', 'web1', '10.0.0.1')],
                'item.get': [self.ITEM]})
        self.assertEqual(ret, 0)
        self.assertEqual(out, 'web1  vfs.fs.size[/,pfree]  42 %\n')
        self.assertEqual(
            self.fake.params_of('item.get')[0]['search'],
            {'key_': 'vfs.fs.size[/,pfree]'})

    def test_items_conflict_with_other_show_modes(self):
        ret, out, err = self.zabdig('--show=alerts', '--items', 'x')
        self.assertEqual(ret, 1)
        self.assertIn('--items requires --show=data', err)
