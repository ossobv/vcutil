from datetime import datetime, time as dtime
from contextlib import redirect_stderr, redirect_stdout
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from io import StringIO
from pathlib import Path
from unittest import TestCase, mock
import argparse
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
GROUPS = [
    {'groupid': '1', 'name': 'Example'},
    {'groupid': '2', 'name': 'Example/DB'},
    {'groupid': '3', 'name': 'Linux'},
]


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
            # The server does a case insensitive contains-search.
            'hostgroup.get': lambda params: [
                group for group in GROUPS
                if params['search']['name'].lower() in
                group['name'].lower()],
        }
        self.responses.update(responses)
        self.calls = []

    def post(self, zinterface, url, data):
        self.calls.append((data['method'], data['params']))
        response = self.responses[data['method']]
        return response(data['params']) if callable(response) else response

    def params_of(self, method):
        return [params for meth, params in self.calls if meth == method]


class TimezoneTestCase(TestCase):
    "Times are shown and computed in local time: control what that is."
    def set_timezone(self, tz):
        old_tz = os.environ.get('TZ')
        os.environ['TZ'] = tz
        time.tzset()

        def restore_tz():
            if old_tz is None:
                del os.environ['TZ']
            else:
                os.environ['TZ'] = old_tz
            time.tzset()
        self.addCleanup(restore_tz)

    def setUp(self):
        self.set_timezone('UTC')


class ZabdigTestCase(TimezoneTestCase):
    def setUp(self):
        super().setUp()

        # Never read the real ~/.zabbixrc or the keyring.
        patcher = mock.patch.object(zabdig, 'CONF_FILE', '/nonexistent/rc')
        patcher.start()
        self.addCleanup(patcher.stop)

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

    def test_list_flag_lists_matches_despite_exact_match(self):
        ret, out, err = self.zabdig('pve1')
        self.assertEqual(out, '10.0.0.1\n')
        for flag in ('-l', '--list', '--li'):
            ret, out, err = self.zabdig(flag, 'pve1')
            self.assertEqual(out, (
                '{:30}  10.0.0.1\n'
                '{:30}  10.0.1.1\n'
            ).format('pve1', 'pve1.dr'), flag)

    def test_list_flag_lists_a_single_match_too(self):
        ret, out, err = self.zabdig('-l', 'walter.internal.lan')
        self.assertEqual(
            out, '{:30}  10.32.1.5 (zabbix-proxy-lan)\n'.format(
                'walter.internal.lan'))

    def test_wildcard_matching_one_host_prints_only_the_address(self):
        # This is how 'zssh hostx*' completes a hostname.
        ret, out, err = self.zabdig('walter.internal.la?')
        self.assertEqual((ret, out, err), (0, '10.32.1.5\n', ''))

    def test_old_all_flag_is_an_error(self):
        for flag in ('-a', '--all'):
            with self.assertRaises(SystemExit) as cm:
                self.zabdig(flag, 'pve1')
            self.assertEqual(cm.exception.code, 2, flag)

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

    def test_verbose_shows_host_details(self):
        ret, out, err = self.zabdig('-v', 'walter.internal.lan')
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
            '--alerts', **{
                'problem.get': [dict(self.PROBLEM)],
                'trigger.get': [dict(self.TRIGGER)]})
        self.assertEqual(ret, 0)
        self.assertEqual(out, (
            'alert:HIGH 2023-11-14T22:13:20: Disk full (web1)\n'
            '1\n'))

    def test_default_severity_is_disaster_and_high(self):
        self.zabdig(
            '--alerts', **{'problem.get': [], 'trigger.get': []})
        self.assertEqual(
            self.fake.params_of('problem.get')[0]['severities'], [5, 4])

    def test_alerts_on_disabled_host_are_skipped(self):
        trigger = dict(self.TRIGGER)
        trigger['hosts'] = [
            {'hostid': '101', 'host': 'web1', 'status': '1'}]
        ret, out, err = self.zabdig(
            '--alerts', **{
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
            '--alerts', **{
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

    def test_data_for_item(self):
        ret, out, err = self.zabdig(
            '--data', '-i', 'vfs.fs.size[/,pfree]', 'web1', **{
                'host.get': [make_host('1', 'web1', '10.0.0.1')],
                'item.get': [self.ITEM]})
        self.assertEqual(ret, 0)
        self.assertEqual(out, 'web1  vfs.fs.size[/,pfree]  42 %\n')
        self.assertEqual(
            self.fake.params_of('item.get')[0]['search'],
            {'key_': 'vfs.fs.size[/,pfree]'})

    def test_items_are_required(self):
        with self.assertRaises(SystemExit) as cm:
            self.zabdig('--data', 'web1')
        self.assertEqual(cm.exception.code, 2)

    def test_multiple_items_can_be_given(self):
        ret, out, err = self.zabdig(
            '--data', '-i', 'a', '--items', 'b', 'web1', **{
                'host.get': [make_host('1', 'web1', '10.0.0.1')],
                'item.get': []})
        self.assertEqual(ret, 0)
        self.assertEqual(
            [p['search'] for p in self.fake.params_of('item.get')],
            [{'key_': 'a'}, {'key_': 'b'}])


class SplitModeTest(TestCase):
    def test_no_mode_is_host_lookup(self):
        self.assertEqual(
            zabdig.split_mode(['-l', 'walter']), (None, ['-l', 'walter']))
        self.assertEqual(zabdig.split_mode([]), (None, []))

    def test_mode_is_removed_from_argv(self):
        self.assertEqual(
            zabdig.split_mode(['-g', 'x', '--alerts', '-S', '1']),
            ('alerts', ['-g', 'x', '-S', '1']))
        self.assertEqual(
            zabdig.split_mode(['-i', 'a', 'web1', '--data']),
            ('data', ['-i', 'a', 'web1']))

    def test_mode_can_be_abbreviated(self):
        for arg in ('--a', '--al', '--ale', '--alert', '--alerts'):
            self.assertEqual(zabdig.split_mode([arg]), ('alerts', []), arg)
        for arg in ('--d', '--da', '--data'):
            self.assertEqual(zabdig.split_mode([arg]), ('data', []), arg)
        for arg in ('--m', '--ma', '--main', '--maint'):
            self.assertEqual(zabdig.split_mode([arg]), ('maint', []), arg)

    def test_other_options_are_left_alone(self):
        # --all is not a prefix of --alerts; the others are ordinary options.
        for arg in ('--all', '--api', '--alert-severity', '--help', '-l',
                    '--list',
                    '--data=x', '--alerts=x', '--dat-a', '--mx', '--', '-'):
            self.assertEqual(zabdig.split_mode([arg]), (None, [arg]), arg)

    def test_hostnames_are_never_modes(self):
        # A host called "alerts" or "data" is found as any other host.
        self.assertEqual(
            zabdig.split_mode(['alerts']), (None, ['alerts']))
        self.assertEqual(
            zabdig.split_mode(['data']), (None, ['data']))

    def test_double_dash_ends_mode_detection(self):
        self.assertEqual(
            zabdig.split_mode(['--', '--alerts']), (None, ['--', '--alerts']))

    def test_only_one_mode(self):
        with self.assertRaises(zabdig.UsageError):
            zabdig.split_mode(['--alerts', '--data'])
        # The same mode, twice, is fine.
        self.assertEqual(
            zabdig.split_mode(['--al', '--alerts']), ('alerts', []))


class CliTest(ZabdigTestCase):
    def test_host_named_like_a_mode_is_looked_up(self):
        hosts = [make_host('1', 'data', '10.0.0.1'),
                 make_host('2', 'data2', '10.0.0.2')]
        ret, out, err = self.zabdig('data', **{'host.get': hosts})
        self.assertEqual((ret, out), (0, '10.0.0.1\n'))

    def test_contains_search_still_finds_hosts_named_host(self):
        hosts = [make_host('1', 'host1', '10.0.0.1'),
                 make_host('2', 'host2', '10.0.0.2')]
        ret, out, err = self.zabdig('host', **{'host.get': hosts})
        self.assertEqual(out, (
            '{:30}  10.0.0.1\n'
            '{:30}  10.0.0.2\n').format('host1', 'host2'))

    def test_options_are_scoped_to_their_mode(self):
        for args in (['--alerts', '-l'], ['--alerts', '-x', '1.2.3.4'],
                     ['-S', '1'], ['--data', '-i', 'x', '-S', '1'],
                     ['--data', '-i', 'x', '-l'], ['-i', 'x']):
            with self.assertRaises(SystemExit) as cm:
                self.zabdig(*args)
            self.assertEqual(cm.exception.code, 2, args)

    def test_two_modes_is_an_error(self):
        ret, out, err = self.zabdig('--alerts', '--data')
        self.assertEqual(ret, 2)
        self.assertIn('only one of', err)

    def test_abbreviated_mode_runs_the_mode(self):
        ret, out, err = self.zabdig(
            '--ale', **{'problem.get': [], 'trigger.get': []})
        self.assertEqual((ret, out), (0, '0\n'))


class DurationTest(TestCase):
    def test_valid(self):
        for text, seconds in (
                ('90m', 5400), ('2h', 7200), ('1h30m', 5400), ('1d', 86400),
                ('1w', 604800), ('1d12h', 129600), ('2H', 7200),
                ('61s', 120), ('1s', 60)):
            self.assertEqual(zabdig.parse_duration(text), seconds, text)

    def test_invalid(self):
        for text in ('', '5', '0m', '0s', '-1h', '2x', 'h', '1h30', ' 1h',
                     '1.5h', '1 h', 'abc'):
            with self.assertRaises(argparse.ArgumentTypeError, msg=text):
                zabdig.parse_duration(text)


class StartTest(TestCase):
    def test_valid(self):
        self.assertEqual(zabdig.parse_start('22:00'), dtime(22, 0))
        self.assertEqual(zabdig.parse_start('09:05'), dtime(9, 5))

    def test_invalid(self):
        for text in ('', '22', '24:00', '22:60', '10pm', '22:00:00'):
            with self.assertRaises(argparse.ArgumentTypeError, msg=text):
                zabdig.parse_start(text)


def ts(*args):
    "Timestamp of a UTC time: ts(2026, 9, 28, 14, 3)"
    return int(datetime(*args).timestamp())


class MaintenanceWindowTest(TimezoneTestCase):
    NOW = datetime(2026, 9, 28, 14, 3, 27)

    def plan(self, duration, start=None, now=None):
        return zabdig.MaintenanceWindow.plan(
            now or self.NOW, duration, start)

    def test_starts_now_at_the_whole_minute(self):
        window = self.plan(7200)
        self.assertEqual(window.start, ts(2026, 9, 28, 14, 3))
        self.assertEqual(window.duration, 7200)
        self.assertEqual(window.end, ts(2026, 9, 28, 16, 3))
        self.assertEqual(window.active_since, ts(2026, 9, 28))
        self.assertEqual(window.active_till, ts(2026, 9, 29))

    def test_start_time_is_today(self):
        window = self.plan(3600, dtime(22, 30))
        self.assertEqual(window.start, ts(2026, 9, 28, 22, 30))
        self.assertEqual(window.active_since, ts(2026, 9, 28))
        self.assertEqual(window.active_till, ts(2026, 9, 29))

    def test_window_crossing_midnight_extends_active_till(self):
        window = self.plan(4 * 3600, dtime(22, 0))
        self.assertEqual(window.end, ts(2026, 9, 29, 2, 0))
        self.assertEqual(window.active_till, ts(2026, 9, 30))

    def test_window_ending_at_midnight_is_still_covered(self):
        window = self.plan(2 * 3600, dtime(22, 0))
        self.assertEqual(window.end, ts(2026, 9, 29, 0, 0))
        self.assertGreater(window.active_till, window.end)

    def test_multi_day_window(self):
        window = self.plan(3 * 86400)
        self.assertEqual(window.active_till, ts(2026, 10, 2))

    def test_start_in_the_past_is_ok_if_still_running(self):
        window = self.plan(2 * 3600, dtime(13, 0))
        self.assertEqual(window.start, ts(2026, 9, 28, 13, 0))
        self.assertGreater(window.end, int(self.NOW.timestamp()))

    def test_window_that_is_over_is_refused(self):
        with self.assertRaises(zabdig.ZMaintError):
            self.plan(3600, dtime(9, 0))
        with self.assertRaises(zabdig.ZMaintError):
            self.plan(3600, dtime(13, 3))  # ends 14:03, and it is 14:03:27

    def test_active_range_follows_the_calendar_on_dst_change(self):
        # The Netherlands went from CET to CEST in the night of 2026-03-29,
        # so that day is 23 hours long.
        self.set_timezone('Europe/Amsterdam')
        now = datetime(2026, 3, 28, 20, 0)
        window = self.plan(4 * 3600, dtime(23, 0), now=now)
        self.assertEqual(
            datetime.fromtimestamp(window.active_since),
            datetime(2026, 3, 28, 0, 0))
        self.assertEqual(
            datetime.fromtimestamp(window.active_till),
            datetime(2026, 3, 30, 0, 0))
        self.assertEqual(window.active_till - window.active_since, 47 * 3600)
        # The window is measured in real seconds: 23:00 CET + 4h = 03:00 CEST
        self.assertEqual(
            datetime.fromtimestamp(window.end), datetime(2026, 3, 29, 4, 0))


class MaintenanceStateTest(TimezoneTestCase):
    NOW = ts(2026, 9, 28, 14, 3)

    def maintenance(self, since, till, *periods):
        return {
            'active_since': str(since), 'active_till': str(till),
            'timeperiods': [{
                'timeperiod_type': str(kind), 'start_date': str(start),
                'period': str(period)} for kind, start, period in periods]}

    def state(self, maintenance):
        return zabdig.maintenance_state(maintenance, self.NOW)

    def test_one_time_windows(self):
        day, next_day = ts(2026, 9, 28), ts(2026, 9, 29)

        def one_time(hour, hours):
            return self.maintenance(
                day, next_day, (0, ts(2026, 9, 28, hour), hours * 3600))

        self.assertEqual(
            self.state(one_time(13, 2)), ('ACTIVE', ts(2026, 9, 28, 15)))
        self.assertEqual(
            self.state(one_time(22, 1)), ('PENDING', ts(2026, 9, 28, 23)))
        self.assertEqual(
            self.state(one_time(10, 2)), ('EXPIRED', ts(2026, 9, 28, 12)))

    def test_outside_active_range(self):
        window = (0, ts(2026, 9, 28, 13), 7200)
        self.assertEqual(
            self.state(self.maintenance(
                ts(2026, 9, 27), ts(2026, 9, 28), window)),
            ('EXPIRED', ts(2026, 9, 28)))
        self.assertEqual(
            self.state(self.maintenance(
                ts(2026, 9, 29), ts(2026, 9, 30), window)),
            ('PENDING', ts(2026, 9, 30)))

    def test_recurring(self):
        self.assertEqual(
            self.state(self.maintenance(
                ts(2026, 9, 1), ts(2026, 12, 1), (2, 0, 3600))),
            ('RECURRING', ts(2026, 12, 1)))


class MaintCreateTest(ZabdigTestCase):
    NOW = datetime(2026, 9, 28, 14, 3, 27)

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(zabdig, 'get_now', lambda: self.NOW)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.fake.responses['maintenance.create'] = {'maintenanceids': ['7']}

    def create(self, *args, **responses):
        return self.zabdig('--maint', 'create', *args, **responses)

    def test_create_sends_one_window_in_one_call(self):
        ret, out, err = self.create('kernel upgrade', '2h', 'pve1', 'walter*')
        self.assertEqual(ret, 0)
        self.assertEqual(self.fake.params_of('maintenance.create'), [{
            'name': 'kernel upgrade',
            'active_since': ts(2026, 9, 28),
            'active_till': ts(2026, 9, 29),
            'hosts': [{'hostid': '103'}, {'hostid': '101'},
                      {'hostid': '102'}],
            'timeperiods': [{
                'timeperiod_type': 0,
                'start_date': ts(2026, 9, 28, 14, 3),
                'period': 7200}],
        }])

    def test_create_reports_what_it_did(self):
        ret, out, err = self.create('kernel upgrade', '2h', 'pve1')
        self.assertEqual(
            out, "created maintenance 7 'kernel upgrade' "
                 "until 2026-09-28 16:03\n")
        self.assertEqual(
            err, '1 host: pve1\n'
                 'from 2026-09-28 14:03 until 2026-09-28 16:03\n')

    def test_start_time(self):
        ret, out, err = self.create(
            'reboot', '90m', '--start', '22:00', 'pve1')
        self.assertEqual(ret, 0)
        params = self.fake.params_of('maintenance.create')[0]
        self.assertEqual(
            params['timeperiods'][0]['start_date'], ts(2026, 9, 28, 22, 0))
        self.assertEqual(params['timeperiods'][0]['period'], 5400)

    def test_window_that_is_over_creates_nothing(self):
        ret, out, err = self.create('reboot', '1h', '--start', '09:00', 'pve1')
        self.assertEqual(ret, 1)
        self.assertIn('already over', err)
        self.assertEqual(self.fake.params_of('maintenance.create'), [])

    def test_plain_name_is_matched_in_full(self):
        # There is also pve1.dr. Only a wildcard would select that too.
        self.create('t', '1h', 'pve1')
        hosts = self.fake.params_of('maintenance.create')[0]['hosts']
        self.assertEqual(hosts, [{'hostid': '103'}])

        self.fake.calls.clear()
        self.create('t', '1h', 'pve1*')
        hosts = self.fake.params_of('maintenance.create')[0]['hosts']
        self.assertEqual(hosts, [{'hostid': '103'}, {'hostid': '104'}])

    def test_host_group_target(self):
        ret, out, err = self.create('t', '1h', '@Example')
        self.assertEqual(ret, 0, err)
        params = self.fake.params_of('maintenance.create')[0]
        self.assertEqual(params['groups'], [{'groupid': '1'}])
        self.assertNotIn('hosts', params)  # no hosts, only a group
        self.assertEqual(
            err, '1 host group: Example\n'
                 'from 2026-09-28 14:03 until 2026-09-28 15:03\n')
        self.assertEqual(
            self.fake.params_of('hostgroup.get')[0]['search'],
            {'name': 'Example'})

    def test_hosts_and_host_groups_together(self):
        ret, out, err = self.create('t', '1h', 'pve1', '@Linux', 'pve1.dr')
        params = self.fake.params_of('maintenance.create')[0]
        self.assertEqual(
            params['hosts'], [{'hostid': '103'}, {'hostid': '104'}])
        self.assertEqual(params['groups'], [{'groupid': '3'}])
        self.assertEqual(
            err.splitlines()[:2],
            ['2 hosts: pve1, pve1.dr', '1 host group: Linux'])

    def test_host_group_name_is_matched_in_full(self):
        # There is also Example/DB. Only a wildcard would select that too.
        self.create('t', '1h', '@Example')
        groups = self.fake.params_of('maintenance.create')[0]['groups']
        self.assertEqual(groups, [{'groupid': '1'}])

        self.fake.calls.clear()
        self.create('t', '1h', '@Example*', '@Example')
        groups = self.fake.params_of('maintenance.create')[0]['groups']
        self.assertEqual(groups, [{'groupid': '1'}, {'groupid': '2'}])

    def test_unknown_host_group_creates_nothing(self):
        ret, out, err = self.create('t', '1h', 'pve1', '@Exam')
        self.assertEqual(ret, 1)
        self.assertIn("no host group matches 'Exam'", err)
        self.assertIn('did you mean: Example, Example/DB?', err)
        self.assertEqual(self.fake.params_of('maintenance.create'), [])

    def test_empty_host_group_name(self):
        ret, out, err = self.create('t', '1h', '@')
        self.assertEqual(ret, 1)
        self.assertIn('empty host group name', err)
        self.assertEqual(self.fake.params_of('maintenance.create'), [])

    def test_partial_name_matches_nothing(self):
        ret, out, err = self.create('t', '1h', 'walter')
        self.assertEqual(ret, 1)
        self.assertIn("no host matches 'walter'", err)
        self.assertIn('walter.internal.lan', err)  # did you mean
        self.assertEqual(self.fake.params_of('maintenance.create'), [])

    def test_one_unmatched_argument_aborts_everything(self):
        ret, out, err = self.create('t', '1h', 'pve1', 'nonexistent')
        self.assertEqual(ret, 1)
        self.assertIn("no host matches 'nonexistent'", err)
        self.assertEqual(self.fake.params_of('maintenance.create'), [])

    def test_duplicate_visible_names_are_ambiguous(self):
        hosts = [make_host('1', 'web', '10.0.0.1'),
                 make_host('2', 'web', '10.0.0.2')]
        ret, out, err = self.create('t', '1h', 'web', **{'host.get': hosts})
        self.assertEqual(ret, 1)
        self.assertIn('matches 2 hosts', err)
        self.assertEqual(self.fake.params_of('maintenance.create'), [])

    def test_hosts_are_not_added_twice(self):
        self.create('t', '1h', 'pve1', 'pve*', 'pve1')
        hosts = self.fake.params_of('maintenance.create')[0]['hosts']
        self.assertEqual(hosts, [{'hostid': '103'}, {'hostid': '104'}])

    def test_duplicate_title(self):
        def fail(params):
            raise zabdig.ZInterfaceError({
                'code': -32602, 'message': 'Invalid params.',
                'data': 'Maintenance "t" already exists.'})
        ret, out, err = self.create(
            't', '1h', 'pve1', **{'maintenance.create': fail})
        self.assertEqual(ret, 1)
        self.assertIn("a maintenance named 't' already exists", err)

    def test_bad_duration_or_start(self):
        for args in (['t', '5', 'pve1'], ['t', '0m', 'pve1'],
                     ['--start', '25:00', 't', '1h', 'pve1'],
                     ['t', '1h']):
            with self.assertRaises(SystemExit) as cm:
                self.create(*args)
            self.assertEqual(cm.exception.code, 2, args)
        self.assertEqual(self.fake.params_of('maintenance.create'), [])

    def test_connection_options_work_after_the_action_too(self):
        ret, out, err = self.create('t', '1h', 'pve1', '-u', 'other')
        self.assertEqual(ret, 0, err)  # still has the -A from the start
        self.assertEqual(
            self.fake.params_of('user.login')[0]['username'], 'other')


class MaintListRemoveTest(ZabdigTestCase):
    NOW = datetime(2026, 9, 28, 14, 3, 27)

    def maintenance(self, mid, name, since, till, periods, hosts=(),
                    groups=()):
        return {
            'maintenanceid': str(mid), 'name': name,
            'active_since': str(since), 'active_till': str(till),
            'hosts': [{'hostid': '1', 'name': h} for h in hosts],
            'hostgroups': [{'groupid': '1', 'name': g} for g in groups],
            'timeperiods': [{
                'timeperiod_type': str(kind), 'start_date': str(start),
                'period': str(period)} for kind, start, period in periods]}

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(zabdig, 'get_now', lambda: self.NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

        today, tomorrow = ts(2026, 9, 28), ts(2026, 9, 29)
        self.fake.responses['maintenance.get'] = [
            self.maintenance(
                1, 'active now', today, tomorrow,
                [(0, ts(2026, 9, 28, 13), 7200)],
                hosts=['web2', 'web1'], groups=['Linux']),
            self.maintenance(
                2, 'later', today, tomorrow,
                [(0, ts(2026, 9, 28, 22), 3600)], hosts=['db1']),
            self.maintenance(
                3, 'yesterday', ts(2026, 9, 27), today,
                [(0, ts(2026, 9, 27, 10), 3600)], hosts=['db1']),
            self.maintenance(
                4, 'over today', today, tomorrow,
                [(0, ts(2026, 9, 28, 10), 3600)], hosts=['db1']),
            self.maintenance(
                5, 'daily', ts(2026, 9, 1), ts(2026, 12, 1),
                [(2, 0, 3600)], groups=['Linux', 'DB']),
        ]
        self.fake.responses['maintenance.delete'] = {'maintenanceids': []}
        self.all_maintenances = list(self.fake.responses['maintenance.get'])

    def test_list_hides_expired(self):
        ret, out, err = self.zabdig('--maint', 'list')
        self.assertEqual(ret, 0)
        self.assertEqual(err, '')  # not a word about the hidden ones
        self.assertEqual(out.splitlines(), [
            '     1  ACTIVE     2026-09-28 15:00  active now: '
            'web1, web2, @Linux',
            '     2  PENDING    2026-09-28 23:00  later: db1',
            '     5  RECURRING  2026-12-01 00:00  daily: @DB, @Linux',
        ])

    def test_list_with_only_expired_windows_says_so(self):
        # As seen on a real server: a window from years ago.
        expired = {
            'maintenanceid': '103', 'name': 'maint-2020-02-03',
            'active_since': '1612380600', 'active_till': '1612384200',
            'hostgroups': [],
            'hosts': [
                {'hostid': '11057', 'name': 'galera.zl.acc.example.io'},
                {'hostid': '11058', 'name': 'galera.wp.acc.example.io'}],
            'timeperiods': [{
                'timeperiod_type': '0', 'start_date': '1612380600',
                'period': '3600'}]}
        responses = {'maintenance.get': [expired]}

        ret, out, err = self.zabdig('--maint', 'list', **responses)
        self.assertEqual(
            (ret, out, err),
            (0, '', 'no maintenance windows in state '
                    'active,pending,recurring\n'))

        ret, out, err = self.zabdig(
            '--maint', 'list', '--state=any', **responses)
        self.assertEqual(out, (
            '   103  EXPIRED    2021-02-03 20:30  maint-2020-02-03: '
            'galera.wp.acc.example.io, galera.zl.acc.example.io\n'))
        self.assertEqual(err, '')

    def test_list_without_any_windows_says_so(self):
        ret, out, err = self.zabdig(
            '--maint', 'list', **{'maintenance.get': []})
        self.assertEqual(
            (ret, out, err),
            (0, '', 'no maintenance windows in state '
                    'active,pending,recurring\n'))

    def maintenance_get(self, params):
        "Like the server: filters on the maintenanceids, if given."
        return [
            m for m in self.all_maintenances
            if 'maintenanceids' not in params or
            m['maintenanceid'] in params['maintenanceids']]

    def get_calls(self, *args):
        self.fake.calls.clear()
        self.zabdig(
            '--maint', *args, **{'maintenance.get': self.maintenance_get})
        return self.fake.params_of('maintenance.get')

    def test_list_skips_details_of_windows_that_are_over(self):
        # The first call is brief, the second has the details, only of
        # the windows that are not over. (3 is. 4 is over but its active
        # period is not: that is only known after fetching it.)
        calls = self.get_calls('list')
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            calls[0], {'output': ['maintenanceid', 'active_till']})
        self.assertEqual(calls[1]['maintenanceids'], ['1', '2', '4', '5'])
        self.assertIn('selectHosts', calls[1])

    def test_list_asks_only_once_if_all_windows_are_over(self):
        self.all_maintenances = [
            m for m in self.all_maintenances if m['maintenanceid'] == '3']
        calls = self.get_calls('list')
        self.assertEqual(len(calls), 1)
        self.assertNotIn('selectHosts', calls[0])

    def test_states_with_expired_get_the_details_in_one_call(self):
        for args in (['list', '--state=any'], ['list', '--state=expired'],
                     ['list', '--state=pending,expired'],
                     ['remove', '-n', '*'],
                     ['remove', '-n', '--state=expired', '*']):
            calls = self.get_calls(*args)
            self.assertEqual(len(calls), 1, args)
            self.assertNotIn('maintenanceids', calls[0], args)
            self.assertIn('selectHosts', calls[0], args)

    def test_remove_by_state_without_expired_skips_details_too(self):
        calls = self.get_calls('remove', '-n', '--state=pending', '*')
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]['maintenanceids'], ['1', '2', '4', '5'])

    def test_list_help_says_how_to_see_expired_windows(self):
        out = StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as cm:
            zabdig.main(['--maint', 'list', '--help'])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn('List unexpired maintenance windows.', out.getvalue())
        self.assertIn('--state=any', out.getvalue())

    def test_list_state_any(self):
        ret, out, err = self.zabdig('--maint', 'list', '--state=any')
        self.assertEqual(
            [line.split()[0] for line in out.splitlines()],
            ['3', '4', '1', '2', '5'])
        self.assertIn('EXPIRED', out)

    def test_list_by_state(self):
        def ids(*args):
            ret, out, err = self.zabdig('--maint', 'list', *args)
            self.assertEqual(ret, 0)
            return [line.split()[0] for line in out.splitlines()]

        self.assertEqual(ids('--state=expired'), ['3', '4'])
        self.assertEqual(ids('--state=active'), ['1'])
        self.assertEqual(ids('--state=active,pending'), ['1', '2'])
        self.assertEqual(ids('--state=RECURRING,Active'), ['1', '5'])
        self.assertEqual(ids('--state', 'pending'), ['2'])
        self.assertEqual(ids('--state=expired,any'), ['3', '4', '1', '2', '5'])

    def test_list_by_state_says_if_there_is_nothing(self):
        responses = {'maintenance.get': []}
        ret, out, err = self.zabdig(
            '--maint', 'list', '--state=pending,active', **responses)
        self.assertEqual(
            (ret, out, err),
            (0, '', 'no maintenance windows in state active,pending\n'))

    def test_invalid_state_is_an_error(self):
        for command in (['list'], ['remove', '*']):
            for state in ('--state=bogus', '--state=', '--state=active,',
                          '--state=expired,soon'):
                with self.assertRaises(SystemExit) as cm:
                    self.zabdig('--maint', *command, state)
                self.assertEqual(cm.exception.code, 2, (command, state))

    def test_old_all_option_is_an_error(self):
        with self.assertRaises(SystemExit) as cm:
            self.zabdig('--maint', 'list', '--all')
        self.assertEqual(cm.exception.code, 2)

    def test_remove_by_state(self):
        ret, out, err = self.zabdig(
            '--maint', 'remove', '--state=expired', '*')
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.fake.params_of('maintenance.delete'), [['3', '4']])
        self.assertEqual(out, (
            "removed maintenance 3 'yesterday'\n"
            "removed maintenance 4 'over today'\n"))

    def test_remove_by_state_with_dry_run(self):
        ret, out, err = self.zabdig(
            '--maint', 'remove', '-n', '--state=pending,recurring', '*')
        self.assertEqual(self.fake.params_of('maintenance.delete'), [])
        self.assertEqual(out, (
            "would remove maintenance 2 'later'\n"
            "would remove maintenance 5 'daily'\n"))

    def test_remove_state_applies_to_titles_and_ids(self):
        # Window 1 is active. Neither its id nor its title is expired.
        for target in ('1', 'active now', 'active*'):
            ret, out, err = self.zabdig(
                '--maint', 'remove', '--state=expired', target)
            self.assertEqual(ret, 1, target)
            self.assertIn(
                'no maintenance with title or id {!r} in state expired'
                .format(target), err)
        self.assertEqual(self.fake.params_of('maintenance.delete'), [])

    def test_remove_without_state_matches_any_state(self):
        ret, out, err = self.zabdig('--maint', 'remove', '-n', '*')
        self.assertEqual(
            [line.split()[3] for line in out.splitlines()],
            ['1', '2', '3', '4', '5'])

    def test_remove_by_title_and_id(self):
        ret, out, err = self.zabdig('--maint', 'remove', 'later', '1')
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.fake.params_of('maintenance.delete'), [['1', '2']])
        # It says what it removed, by title, also if given an id. In id
        # order, not in the order given.
        self.assertEqual(out, (
            "removed maintenance 1 'active now'\n"
            "removed maintenance 2 'later'\n"))

    def test_remove_is_sorted_by_numeric_id(self):
        def named(mid, name):
            return self.maintenance(mid, name, 0, 1, [(0, 0, 60)])
        # The server returns them in no particular order.
        responses = {'maintenance.get': [
            named(100, 'c'), named(9, 'a'), named(10, 'b')]}

        ret, out, err = self.zabdig(
            '--maint', 'remove', '-n', '*', **responses)
        self.assertEqual(out, (
            "would remove maintenance 9 'a'\n"
            "would remove maintenance 10 'b'\n"
            "would remove maintenance 100 'c'\n"))

        ret, out, err = self.zabdig('--maint', 'remove', '*', **responses)
        self.assertEqual(out, (
            "removed maintenance 9 'a'\n"
            "removed maintenance 10 'b'\n"
            "removed maintenance 100 'c'\n"))
        self.assertEqual(
            self.fake.params_of('maintenance.delete'), [['9', '10', '100']])

    def test_remove_by_title_pattern(self):
        ret, out, err = self.zabdig('--maint', 'remove', '*day')
        self.assertEqual(ret, 0)
        self.assertEqual(
            self.fake.params_of('maintenance.delete'), [['3', '4']])
        self.assertEqual(out, (
            "removed maintenance 3 'yesterday'\n"
            "removed maintenance 4 'over today'\n"))

    def test_remove_dry_run_removes_nothing(self):
        for flag in ('-n', '--dry-run'):
            ret, out, err = self.zabdig(
                '--maint', 'remove', flag, '*day', '1')
            self.assertEqual(ret, 0)
            self.assertEqual(self.fake.params_of('maintenance.delete'), [])
            self.assertEqual(out, (
                "would remove maintenance 1 'active now'\n"
                "would remove maintenance 3 'yesterday'\n"
                "would remove maintenance 4 'over today'\n"))

    def test_remove_matching_twice_removes_once(self):
        ret, out, err = self.zabdig('--maint', 'remove', 'later', 'l*')
        self.assertEqual(
            self.fake.params_of('maintenance.delete'), [['2']])

    def test_remove_pattern_matching_nothing_removes_nothing(self):
        ret, out, err = self.zabdig('--maint', 'remove', 'later', 'x*')
        self.assertEqual(ret, 1)
        self.assertIn("no maintenance with title or id 'x*'", err)
        self.assertEqual(self.fake.params_of('maintenance.delete'), [])

    def test_titles_with_brackets_are_not_character_classes(self):
        def named(mid, name):
            return self.maintenance(mid, name, 0, 1, [(0, 0, 60)])
        responses = {'maintenance.get': [
            named(1, 'db [prod]'), named(2, 'db [test]'), named(3, 'db p')]}

        self.zabdig('--maint', 'remove', 'db [prod]', **responses)
        self.zabdig('--maint', 'remove', 'db [*', **responses)
        self.zabdig('--maint', 'remove', 'db [p*', **responses)
        self.zabdig('--maint', 'remove', 'db ?p*', **responses)
        self.assertEqual(
            self.fake.params_of('maintenance.delete'),
            [['1'], ['1', '2'], ['1'], ['1']])

    def test_remove_unknown_removes_nothing(self):
        ret, out, err = self.zabdig('--maint', 'remove', 'later', 'nope')
        self.assertEqual(ret, 1)
        self.assertIn("no maintenance with title or id 'nope'", err)
        self.assertEqual(self.fake.params_of('maintenance.delete'), [])

    def test_remove_needs_exact_title(self):
        ret, out, err = self.zabdig('--maint', 'remove', 'lat')
        self.assertEqual(ret, 1)
        self.assertEqual(self.fake.params_of('maintenance.delete'), [])

    def test_action_is_required(self):
        with self.assertRaises(SystemExit) as cm:
            self.zabdig('--maint')
        self.assertEqual(cm.exception.code, 2)

    def test_abbreviated_mode(self):
        ret, out, err = self.zabdig('--m', 'list')
        self.assertEqual(ret, 0)
        self.assertEqual(len(out.splitlines()), 3)


class MaintAddTest(ZabdigTestCase):
    NOW = datetime(2026, 9, 28, 14, 3, 27)

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(zabdig, 'get_now', lambda: self.NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

        today, tomorrow = ts(2026, 9, 28), ts(2026, 9, 29)
        period = [{'timeperiod_type': '0',
                   'start_date': str(ts(2026, 9, 28, 13)), 'period': '7200'}]
        self.fake.responses['maintenance.get'] = [{
            'maintenanceid': '10', 'name': 'kernel',
            'active_since': str(today), 'active_till': str(tomorrow),
            'hosts': [{'hostid': '103', 'name': 'pve1'}],
            'hostgroups': [{'groupid': '3', 'name': 'Linux'}],
            'timeperiods': period,
        }, {
            'maintenanceid': '11', 'name': 'old',
            'active_since': str(ts(2026, 9, 1)),
            'active_till': str(ts(2026, 9, 2)),
            'hosts': [], 'hostgroups': [], 'timeperiods': period,
        }]
        self.fake.responses['maintenance.update'] = {'maintenanceids': ['10']}

    def add(self, *args):
        return self.zabdig('--maint', 'add', *args)

    def test_add_host_keeps_the_existing_hosts(self):
        ret, out, err = self.add('kernel', 'pve1.dr')
        self.assertEqual(ret, 0, err)
        # Only the hosts are sent: the groups stay as they are.
        self.assertEqual(self.fake.params_of('maintenance.update'), [{
            'maintenanceid': '10',
            'hosts': [{'hostid': '103'}, {'hostid': '104'}]}])
        self.assertEqual(out, "added to maintenance 10 'kernel': pve1.dr\n")

    def test_add_host_group_keeps_the_existing_groups(self):
        ret, out, err = self.add('10', '@Example')
        self.assertEqual(ret, 0, err)
        self.assertEqual(self.fake.params_of('maintenance.update'), [{
            'maintenanceid': '10',
            'groups': [{'groupid': '3'}, {'groupid': '1'}]}])
        self.assertEqual(
            out, "added to maintenance 10 'kernel': @Example\n")

    def test_add_hosts_and_groups_at_once(self):
        ret, out, err = self.add('kernel', 'walter*', '@Example/DB')
        self.assertEqual(self.fake.params_of('maintenance.update'), [{
            'maintenanceid': '10',
            'hosts': [{'hostid': '103'}, {'hostid': '101'},
                      {'hostid': '102'}],
            'groups': [{'groupid': '3'}, {'groupid': '2'}]}])

    def test_targets_already_in_it_are_skipped(self):
        ret, out, err = self.add('kernel', 'pve1', 'pve1.dr', '@Linux')
        self.assertEqual(self.fake.params_of('maintenance.update'), [{
            'maintenanceid': '10',
            'hosts': [{'hostid': '103'}, {'hostid': '104'}]}])
        self.assertEqual(err, '2 already in the maintenance, skipped\n')

    def test_nothing_new_does_not_update(self):
        ret, out, err = self.add('kernel', 'pve1', '@Linux')
        self.assertEqual(ret, 0)
        self.assertEqual(self.fake.params_of('maintenance.update'), [])
        self.assertEqual(out, "nothing to add to maintenance 10 'kernel'\n")

    def test_unknown_maintenance(self):
        for target in ('nope', 'ker*', 'ker', '99'):
            ret, out, err = self.add(target, 'pve1.dr')
            self.assertEqual(ret, 1, target)
            self.assertIn('no maintenance with title or id', err)
        self.assertEqual(self.fake.params_of('maintenance.update'), [])

    def test_expired_maintenance_is_refused(self):
        ret, out, err = self.add('old', 'pve1.dr')
        self.assertEqual(ret, 1)
        self.assertIn("maintenance 11 'old' has expired", err)
        self.assertEqual(self.fake.params_of('maintenance.update'), [])

    def test_unmatched_target_changes_nothing(self):
        ret, out, err = self.add('kernel', 'pve1.dr', 'nonexistent')
        self.assertEqual(ret, 1)
        self.assertIn("no host matches 'nonexistent'", err)
        self.assertEqual(self.fake.params_of('maintenance.update'), [])
