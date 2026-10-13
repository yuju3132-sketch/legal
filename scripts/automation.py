"""Per-user Windows Task Scheduler integration; no password/admin requirement.

Importing this module never registers tasks or starts collection.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, time, timedelta
import hashlib
import json
import locale
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time as clock
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = sys.platform == 'win32'
NAMESPACE = 'http://schemas.microsoft.com/windows/2004/02/mit/task'
JOBS = ('daily', 'weekly', 'logon')

def seoul_now():
    return datetime.now(ZoneInfo('Asia/Seoul'))

def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        return {'error': f'설정 파일을 읽지 못했습니다: {type(exc).__name__}'}

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique temp files also protect readers while a scheduler query completes.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as temp:
        json.dump(value, temp, ensure_ascii=False, indent=2)
        name = temp.name
    try:
        for attempt in range(5):
            try:
                os.replace(name, path)
                break
            except PermissionError:
                # A Windows reader can briefly hold a sharing lock.
                if attempt == 4: raise
                clock.sleep(.05)
    finally:
        Path(name).unlink(missing_ok=True)

def due_periods(current):
    """Return latest due business day / completed Friday, never fabricate backfill."""
    current = current.astimezone(ZoneInfo('Asia/Seoul'))
    daily = current.date()
    if current.time() < time(7):
        daily -= timedelta(days=1)
    while daily.weekday() >= 5:
        daily -= timedelta(days=1)
    friday = current.date() - timedelta(days=(current.weekday() - 4) % 7)
    if current.weekday() == 4 and current.time() < time(18):
        friday -= timedelta(days=7)
    return daily.isoformat(), friday.isoformat()

@contextmanager
def worker_lock(path):
    """An OS lock is released on process exit, including a crash/reboot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a+b')
    if handle.tell() == 0:
        handle.write(b'0'); handle.flush()
    handle.seek(0)
    acquired = False
    try:
        if WINDOWS:
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                acquired = True
            except OSError:
                pass
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                pass
        yield acquired
    finally:
        if acquired:
            if WINDOWS:
                import msvcrt
                handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()

class Automation:
    def __init__(self, root=None, data_dir=None):
        self.root = Path(root or ROOT).resolve()
        self.data = Path(data_dir or os.environ.get('LEGAL_DATA_DIR', self.root)).resolve()
        self.config = self.data / 'logs' / 'automation_config.json'
        self.state = self.data / 'logs' / 'automation_state.json'
        self.python = self.root / '.venv' / ('Scripts/python.exe' if WINDOWS else 'bin/python')
        windowless = self.root / '.venv/Scripts/pythonw.exe'
        self.task_python = windowless if WINDOWS and windowless.is_file() else self.python
        key = hashlib.sha256(str(self.root).casefold().encode()).hexdigest()[:12]
        self.names = {job: f'GlobalLegalResearch_{key}_{job.title()}' for job in JOBS}
        self.marker = f'GlobalLegalResearch managed task; project={self.root}; data={self.data}'

    @staticmethod
    def command(arguments):
        return subprocess.run(arguments, capture_output=True, text=True,
                              encoding=locale.getpreferredencoding(False), errors='replace',
                              timeout=60, creationflags=subprocess.CREATE_NO_WINDOW if WINDOWS else 0)

    def query_task(self, name):
        result = self.command(['schtasks.exe', '/Query', '/TN', name, '/XML'])
        return result.stdout if result.returncode == 0 else None

    def owns_task(self, xml):
        try:
            task = ET.fromstring(xml)
            ns = {'t': NAMESPACE}
            return (task.findtext('t:RegistrationInfo/t:Description', namespaces=ns) == self.marker
                    and task.findtext('t:Actions/t:Exec/t:Command', namespaces=ns) == str(self.task_python)
                    and task.findtext('t:Actions/t:Exec/t:WorkingDirectory', namespaces=ns) == str(self.root))
        except ET.ParseError:
            return False

    def active_task(self, xml):
        if not self.owns_task(xml): return False
        task=ET.fromstring(xml)
        ns={'t': NAMESPACE}
        if task.findtext('t:Settings/t:Enabled', namespaces=ns) == 'false': return False
        return all(t.findtext('t:Enabled', namespaces=ns) != 'false'
                   for t in task.findall('t:Triggers/*', ns))

    def task_xml(self, job, sid, current=None):
        current = current or seoul_now()
        task = ET.Element('Task', version='1.3', xmlns=NAMESPACE)
        def node(parent, name, value=None):
            child = ET.SubElement(parent, name)
            if value is not None: child.text = str(value)
            return child
        registration = node(task, 'RegistrationInfo')
        node(registration, 'Description', self.marker)
        triggers = node(task, 'Triggers')
        if job == 'logon':
            trigger = node(triggers, 'LogonTrigger')
            node(trigger, 'Enabled', 'true'); node(trigger, 'UserId', sid)
        else:
            trigger = node(triggers, 'CalendarTrigger')
            # Explicit +09:00 keeps the Seoul schedule independent of PC timezone.
            hour = 7 if job == 'daily' else 18
            boundary = current.astimezone(ZoneInfo('Asia/Seoul')).replace(hour=hour, minute=0, second=0, microsecond=0)
            node(trigger, 'Enabled', 'true')
            node(trigger, 'StartBoundary', boundary.isoformat())
            week = node(trigger, 'ScheduleByWeek'); node(week, 'WeeksInterval', '1')
            days = node(week, 'DaysOfWeek')
            for day in (('Monday','Tuesday','Wednesday','Thursday','Friday') if job == 'daily' else ('Friday',)):
                node(days, day)
        principals = node(task, 'Principals')
        principal = ET.SubElement(principals, 'Principal', id='ResearchUser')
        node(principal, 'UserId', sid); node(principal, 'LogonType', 'InteractiveToken')
        node(principal, 'RunLevel', 'LeastPrivilege')
        settings = node(task, 'Settings')
        node(settings, 'MultipleInstancesPolicy', 'IgnoreNew')
        node(settings, 'DisallowStartIfOnBatteries', 'false')
        node(settings, 'StopIfGoingOnBatteries', 'false')
        node(settings, 'StartWhenAvailable', 'true')
        node(settings, 'RunOnlyIfNetworkAvailable', 'false')
        node(settings, 'AllowStartOnDemand', 'true')
        node(settings, 'Enabled', 'true'); node(settings, 'Hidden', 'false')
        node(settings, 'WakeToRun', 'true'); node(settings, 'ExecutionTimeLimit', 'PT2H')
        restart = node(settings, 'RestartOnFailure')
        node(restart, 'Interval', 'PT10M'); node(restart, 'Count', '3')
        actions = ET.SubElement(task, 'Actions', Context='ResearchUser')
        action = node(actions, 'Exec'); node(action, 'Command', self.task_python)
        command = {'daily':'run-daily','weekly':'run-weekly','logon':'catch-up'}[job]
        args = [str(self.root / 'scripts/automation.py'), command, '--data-dir', str(self.data)]
        node(action, 'Arguments', subprocess.list2cmdline(args))
        node(action, 'WorkingDirectory', self.root)
        return ET.tostring(task, encoding='utf-16', xml_declaration=True)

    def install(self):
        if not WINDOWS:
            raise RuntimeError('Windows에서 enable_auto.bat를 실행하세요. 이 환경에는 예약을 등록하지 않았습니다.')
        if not self.python.is_file():
            raise RuntimeError('먼저 setup.bat 설치를 완료하세요.')
        check = self.command([str(self.python), '-c', 'import requests, streamlit, pandas, pypdf, tzdata'])
        if check.returncode:
            raise RuntimeError('필요한 프로그램 설치가 아직 완료되지 않았습니다. setup.bat 완료 후 다시 실행하세요.')
        identity = self.command(['whoami.exe', '/user', '/fo', 'csv', '/nh'])
        sid = re.search(r'S-1-\d+(?:-\d+)+', identity.stdout)
        if identity.returncode or not sid:
            raise RuntimeError('Windows 사용자 정보를 확인하지 못했습니다.')
        registered = []
        try:
            for job, name in self.names.items():
                previous = self.query_task(name)
                if previous and not self.owns_task(previous):
                    raise RuntimeError(f'같은 이름의 다른 예약을 덮어쓰지 않습니다: {name}')
                with tempfile.TemporaryDirectory() as folder:
                    file = Path(folder) / 'task.xml'; file.write_bytes(self.task_xml(job, sid.group()))
                    command = ['schtasks.exe', '/Create', '/TN', name, '/XML', str(file)]
                    if previous: command.append('/F')
                    result = self.command(command)
                    if result.returncode: raise RuntimeError(result.stderr or result.stdout or '예약 등록 실패')
                installed = self.query_task(name)
                if not installed or not self.active_task(installed):
                    raise RuntimeError(f'예약 등록을 확인하지 못했습니다: {name}')
                registered.append(name)
        except Exception as exc:
            write_json(self.config, dict(enabled=False, registered=registered, names=self.names,
                       timezone='Asia/Seoul', error=str(exc), updated_at=seoul_now().isoformat()))
            raise
        write_json(self.config, dict(enabled=True, registered=registered, names=self.names,
                   timezone='Asia/Seoul', updated_at=seoul_now().isoformat()))
        # Ask Windows to start initial collection; this is not a success claim for collection.
        result = self.command(['schtasks.exe', '/Run', '/TN', self.names['daily']])
        return dict(enabled=True, initial_run_requested=result.returncode == 0,
                    initial_run_error='' if result.returncode == 0 else result.stderr or result.stdout)

    def status(self, verify=True):
        config = read_json(self.config)
        result = dict(config, supported=WINDOWS, enabled=bool(config.get('enabled')),
                      state=read_json(self.state), timezone='Asia/Seoul')
        if verify and WINDOWS and result['enabled']:
            try:
                valid = all(self.active_task(self.query_task(name) or '') for name in self.names.values())
                result['enabled'] = valid
                if not valid: result['error'] = 'Windows 예약을 확인하지 못했습니다. enable_auto.bat를 다시 실행하세요.'
            except (OSError, subprocess.SubprocessError) as exc:
                result.update(enabled=False, error=f'예약 상태 확인 실패: {type(exc).__name__}')
        return result

    def remove(self):
        if not WINDOWS: raise RuntimeError('Windows에서만 예약을 해제할 수 있습니다.')
        for name in self.names.values():
            existing = self.query_task(name)
            if existing:
                if not self.owns_task(existing): raise RuntimeError('다른 프로그램의 예약은 삭제하지 않습니다.')
                result = self.command(['schtasks.exe','/Delete','/TN',name,'/F'])
                if result.returncode: raise RuntimeError(result.stderr or result.stdout)
            elif name in read_json(self.config).get('registered', []):
                # A query failure can mean access denied, not just absence.
                raise RuntimeError(f'예약 존재/권한 확인 실패: {name}. Windows 작업 스케줄러에서 확인하세요.')
        write_json(self.config, dict(enabled=False, names=self.names, registered=[],
                                    updated_at=seoul_now().isoformat()))

    def run(self, mode, current=None, runner=None):
        current = current or seoul_now()
        if mode == 'catch-up' and not read_json(self.config).get('enabled'):
            return 0
        with worker_lock(self.data / 'logs' / 'automation.lock') as acquired:
            if not acquired: return 3
            state = read_json(self.state)
            day, friday = due_periods(current)
            # 'period' identifies the due task. The daily CLI archives/reports
            # today's observations; it never backdates late discoveries.
            selected = [('daily',day),('weekly',friday)] if mode == 'catch-up' else [(mode.removeprefix('run-'), day if mode=='run-daily' else friday)]
            outcome = 0
            for job, period in selected:
                previous = state.get(job,{})
                same_period = previous.get('period') == period
                if same_period and (previous.get('status') == 'COMPLETED'
                                    or previous.get('status') in ('PARTIAL','FAILED') and previous.get('attempts',1)>=4):
                    continue
                state[job] = dict(period=period, status='RUNNING', started_at=seoul_now().isoformat(),
                                  attempts=previous.get('attempts',0)+1 if same_period else 1)
                write_json(self.state, state)
                command = [str(self.python), str(self.root / 'scripts/manage.py'), job]
                if job=='daily': command += ['--pdf']
                else: command += ['--date', period]
                try:
                    if runner is not None:
                        result = runner(command)
                    else:
                        self.data.joinpath('logs').mkdir(parents=True,exist_ok=True)
                        with (self.data/'logs/automation.log').open('a',encoding='utf-8') as log:
                            log.write(f'\n{seoul_now().isoformat()} {job} {period}\n'); log.flush()
                            result = subprocess.run(command, cwd=self.root, env=dict(os.environ, LEGAL_DATA_DIR=str(self.data)),
                                                    stdout=log, stderr=subprocess.STDOUT,
                                                    creationflags=subprocess.CREATE_NO_WINDOW if WINDOWS else 0)
                    code = result.returncode
                    status = 'COMPLETED' if code==0 else 'PARTIAL' if code==2 else 'FAILED'
                except (OSError, subprocess.SubprocessError) as exc:
                    code = 1; status = 'FAILED'
                    state[job]['error'] = f'{type(exc).__name__}: {exc}'
                state[job].update(status=status, exit_code=code, finished_at=seoul_now().isoformat())
                write_json(self.state, state)
                outcome = max(outcome, code)
            return outcome

    def start_catch_up(self):
        if not self.status().get('enabled'): return False
        self.data.joinpath('logs').mkdir(parents=True,exist_ok=True)
        with (self.data/'logs/automation.log').open('a',encoding='utf-8') as log:
            subprocess.Popen([str(self.python), str(self.root/'scripts/automation.py'), 'catch-up', '--data-dir', str(self.data)],
                             cwd=self.root, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW if WINDOWS else 0)
        return True

def main():
    parser = argparse.ArgumentParser(description='Legal Research automatic collection')
    parser.add_argument('command', choices=['install','remove','status','run-daily','run-weekly','catch-up'])
    parser.add_argument('--data-dir')
    args = parser.parse_args(); automation = Automation(data_dir=args.data_dir)
    try:
        if args.command=='install':
            result = automation.install()
            print('Automatic collection enabled: weekdays 07:00 / weekly Friday 18:00 (Asia/Seoul).')
            print('Keep the PC on and stay logged in. The browser/app may be closed.')
            if not result['initial_run_requested']: print('Initial run could not start:', result['initial_run_error'])
        elif args.command=='remove': automation.remove(); print('Automatic collection disabled.')
        elif args.command=='status': print(json.dumps(automation.status(), ensure_ascii=False, indent=2))
        else: return automation.run(args.command)
    except Exception as exc:
        print('Automation failed:', str(exc)); return 1
    return 0

if __name__=='__main__': sys.exit(main())
