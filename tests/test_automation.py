from datetime import datetime
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
import pytest
from scripts import automation as auto

def current(value):
    return datetime.fromisoformat(value).replace(tzinfo=ZoneInfo('Asia/Seoul'))

@pytest.mark.parametrize('instant,day,friday',[
    ('2026-10-13T08:00:00','2026-10-13','2026-10-09'),
    ('2026-10-13T06:00:00','2026-10-12','2026-10-09'),
    ('2026-10-16T17:59:00','2026-10-16','2026-10-09'),
    ('2026-10-16T18:00:00','2026-10-16','2026-10-16'),
    ('2026-10-17T09:00:00','2026-10-16','2026-10-16'),
    ('2026-10-19T06:00:00','2026-10-16','2026-10-16'),
])
def test_due_periods(instant,day,friday):
    assert auto.due_periods(current(instant))==(day,friday)

def test_schedule_time_zone():
    utc=datetime.fromisoformat('2026-10-16T09:00:00+00:00')
    assert auto.due_periods(utc)==('2026-10-16','2026-10-16')

@pytest.mark.parametrize('job,expected_days,hour',[
    ('daily',{'Monday','Tuesday','Wednesday','Thursday','Friday'},'T07:00:00+09:00'),
    ('weekly',{'Friday'},'T18:00:00+09:00'),
])
def test_scheduler_xml(tmp_path,job,expected_days,hour):
    manager=auto.Automation(root=tmp_path/'연구 폴더 & test',data_dir=tmp_path/'데이터')
    xml=manager.task_xml(job,'S-1-5-21-123',current('2026-10-13T10:00:00'))
    task=ET.fromstring(xml); ns={'t':auto.NAMESPACE}
    # Constraints verified against Microsoft's published Task Scheduler XSD.
    assert task.attrib['version']=='1.3'
    trigger=task.find('t:Triggers/t:CalendarTrigger',ns)
    assert [node.tag.split('}')[-1] for node in trigger][:2]==['Enabled','StartBoundary']
    days=task.find('t:Triggers/t:CalendarTrigger/t:ScheduleByWeek/t:DaysOfWeek',ns)
    assert {node.tag.split('}')[-1] for node in days}==expected_days
    assert task.findtext('t:Triggers/t:CalendarTrigger/t:StartBoundary',namespaces=ns).endswith(hour)
    assert task.findtext('t:Principals/t:Principal/t:LogonType',namespaces=ns)=='InteractiveToken'
    assert task.findtext('t:Principals/t:Principal/t:RunLevel',namespaces=ns)=='LeastPrivilege'
    assert task.findtext('t:Settings/t:StartWhenAvailable',namespaces=ns)=='true'
    assert task.findtext('t:Settings/t:MultipleInstancesPolicy',namespaces=ns)=='IgnoreNew'
    assert '연구 폴더 & test' in task.findtext('t:Actions/t:Exec/t:Arguments',namespaces=ns)
    assert manager.owns_task(xml)

def test_login_trigger(tmp_path):
    manager=auto.Automation(root=tmp_path)
    task=ET.fromstring(manager.task_xml('logon','S-1-5-21-123'))
    ns={'t':auto.NAMESPACE}
    assert task.findtext('t:Triggers/t:LogonTrigger/t:UserId',namespaces=ns)=='S-1-5-21-123'
    assert 'catch-up' in task.findtext('t:Actions/t:Exec/t:Arguments',namespaces=ns)

def test_auto_off_does_not_collect(tmp_path):
    manager=auto.Automation(root=tmp_path)
    assert manager.run('catch-up',runner=lambda args:pytest.fail('Disabled automation must not collect'))==0
    assert not manager.state.exists()

def test_daily_once_and_new_day(tmp_path):
    manager=auto.Automation(root=tmp_path); calls=[]
    def runner(args): calls.append(args); return subprocess.CompletedProcess(args,0)
    date=current('2026-10-13T08:00:00')
    assert manager.run('run-daily',date,runner)==0
    assert manager.run('run-daily',date,runner)==0
    assert len(calls)==1
    assert '--pdf' in calls[0]
    manager.run('run-daily',current('2026-10-14T08:00:00'),runner)
    assert len(calls)==2
    assert auto.read_json(manager.state)['daily']['status']=='COMPLETED'

def test_catch_up_missing_jobs_and_no_fake_backfill(tmp_path):
    manager=auto.Automation(root=tmp_path)
    auto.write_json(manager.config,{'enabled':True})
    calls=[]
    def runner(args): calls.append(args); return subprocess.CompletedProcess(args,0)
    date=current('2026-10-19T10:00:00')
    assert manager.run('catch-up',date,runner)==0
    assert len(calls)==2
    assert '--date' not in calls[0] # Daily observations must not be backdated.
    assert calls[1][-2:]==['--date','2026-10-16']
    manager.run('catch-up',date,runner)
    assert len(calls)==2

def test_partial_is_distinct_and_not_success(tmp_path):
    manager=auto.Automation(root=tmp_path)
    assert manager.run('run-daily',current('2026-10-13T08:00:00'),lambda a:subprocess.CompletedProcess(a,2))==2
    status=auto.read_json(manager.state)['daily']
    assert status['status']=='PARTIAL' and status['exit_code']==2

def test_crashed_worker_retried(tmp_path):
    manager=auto.Automation(root=tmp_path)
    auto.write_json(manager.state,{'daily':{'period':'2026-10-13','status':'RUNNING'}})
    assert manager.run('run-daily',current('2026-10-13T08:00:00'),lambda a:subprocess.CompletedProcess(a,0))==0
    assert auto.read_json(manager.state)['daily']['status']=='COMPLETED'

def test_failure_recorded(tmp_path):
    manager=auto.Automation(root=tmp_path)
    def fail(args): raise OSError('TEST_DATA process creation failed')
    assert manager.run('run-daily',current('2026-10-13T08:00:00'),fail)==1
    assert auto.read_json(manager.state)['daily']['status']=='FAILED'

def test_os_lock_blocks_concurrent_worker(tmp_path):
    manager=auto.Automation(root=tmp_path)
    with auto.worker_lock(tmp_path/'logs/automation.lock') as acquired:
        assert acquired
        assert manager.run('run-daily',runner=lambda a:pytest.fail('Concurrent worker must not run'))==3
    assert manager.run('run-daily',runner=lambda a:subprocess.CompletedProcess(a,0))==0

def windows_manager(tmp_path,monkeypatch,fail_second=False,unmanaged=False):
    monkeypatch.setattr(auto,'WINDOWS',True)
    manager=auto.Automation(root=tmp_path/'한글 사용자 & 법률 폴더')
    manager.python.parent.mkdir(parents=True); manager.python.touch()
    tasks={}; commands=[]
    if unmanaged: tasks[manager.names['daily']]='<Task><Description>TEST_DATA someone else</Description></Task>'
    def fake_command(args):
        commands.append(args)
        code=0; stdout=''; stderr=''
        if args[0]=='whoami.exe': stdout='"TEST_DATA\\user","S-1-5-21-123"'
        elif '/Query' in args:
            name=args[args.index('/TN')+1]; stdout=tasks.get(name,''); code=0 if stdout else 1
        elif '/Create' in args:
            name=args[args.index('/TN')+1]
            if fail_second and name==manager.names['weekly']: code=1; stderr='TEST_DATA access denied'
            else: tasks[name]=Path(args[args.index('/XML')+1]).read_bytes().decode('utf-16')
        elif '/Delete' in args: tasks.pop(args[args.index('/TN')+1],None)
        return subprocess.CompletedProcess(args,code,stdout,stderr)
    monkeypatch.setattr(manager,'command',fake_command)
    return manager,tasks,commands

def test_install_and_repeatability(tmp_path,monkeypatch):
    manager,tasks,commands=windows_manager(tmp_path,monkeypatch)
    assert manager.install()['enabled']
    assert len(tasks)==3 and manager.status()['enabled']
    manager.install()
    assert len(tasks)==3
    creates=[c for c in commands if '/Create' in c]
    assert all('/F' not in c for c in creates[:3])
    assert all('/F' in c for c in creates[3:])
    assert '/Run' in commands[-1]
    manager.remove()
    assert not tasks and not auto.read_json(manager.config)['enabled']

def test_registration_failure_never_claimed_enabled(tmp_path,monkeypatch):
    manager,tasks,commands=windows_manager(tmp_path,monkeypatch,fail_second=True)
    with pytest.raises(RuntimeError,match='access denied'): manager.install()
    saved=auto.read_json(manager.config)
    assert not saved['enabled']
    assert saved['registered']==[manager.names['daily']]

def test_unmanaged_task_preserved(tmp_path,monkeypatch):
    manager,tasks,commands=windows_manager(tmp_path,monkeypatch,unmanaged=True)
    with pytest.raises(RuntimeError,match='덮어쓰지'): manager.install()
    assert not any('/Create' in c for c in commands)
    assert len(tasks)==1

def test_missing_task_not_reported_ready(tmp_path,monkeypatch):
    manager,tasks,commands=windows_manager(tmp_path,monkeypatch)
    manager.install(); tasks.pop(manager.names['weekly'])
    assert not manager.status()['enabled']

def test_non_windows_no_registration(tmp_path):
    manager=auto.Automation(root=tmp_path)
    with pytest.raises(RuntimeError,match='Windows'): manager.install()
    assert not manager.config.exists()

def test_state_retries_windows_sharing_lock(tmp_path,monkeypatch):
    real_replace=auto.os.replace; calls=[]
    def replace(source,dest):
        calls.append(source)
        if len(calls)<=2: raise PermissionError('TEST_DATA sharing lock')
        return real_replace(source,dest)
    monkeypatch.setattr(auto.os,'replace',replace)
    auto.write_json(tmp_path/'state.json',{'status':'TEST_DATA'})
    assert auto.read_json(tmp_path/'state.json')['status']=='TEST_DATA'
    assert len(calls)==3

def test_atomic_state_roundtrip(tmp_path):
    file=tmp_path/'logs/state.json'
    auto.write_json(file,{'value':'한글 TEST_DATA'})
    assert auto.read_json(file)=={'value':'한글 TEST_DATA'}
    file.write_text('broken',encoding='utf-8')
    assert 'error' in auto.read_json(file)

def test_disabled_task_detected(tmp_path,monkeypatch):
    manager,tasks,commands=windows_manager(tmp_path,monkeypatch)
    manager.install()
    name=manager.names['daily']
    xml=tasks[name].replace('<Enabled>true</Enabled>','<Enabled>false</Enabled>')
    tasks[name]=xml
    assert not manager.status()['enabled']

def test_partial_retries_bounded(tmp_path):
    manager=auto.Automation(root=tmp_path); calls=[]
    def runner(args): calls.append(args); return subprocess.CompletedProcess(args,2)
    date=current('2026-10-13T08:00:00')
    for _ in range(6): manager.run('run-daily',date,runner)
    assert len(calls)==4
    assert auto.read_json(manager.state)['daily']['status']=='PARTIAL'

def test_weekend_login_does_not_repeat_friday(tmp_path):
    manager=auto.Automation(root=tmp_path); auto.write_json(manager.config,{'enabled':True})
    calls=[]
    def runner(args): calls.append(args); return subprocess.CompletedProcess(args,0)
    manager.run('catch-up',current('2026-10-16T18:00:00'),runner)
    manager.run('catch-up',current('2026-10-17T10:00:00'),runner)
    manager.run('catch-up',current('2026-10-18T10:00:00'),runner)
    assert len(calls)==2
