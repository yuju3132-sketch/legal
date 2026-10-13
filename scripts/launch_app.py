import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen
from automation import Automation

root=Path(__file__).resolve().parents[1]
try:
    if Automation().start_catch_up():
        print('Automatic collection is running in the background when due.')
except Exception as exc:
    print('Automatic collection could not start. Check the Dashboard:',type(exc).__name__)
port=8501
with socket.socket() as check:
    if check.connect_ex(('127.0.0.1',port))==0:
        print('8501 포트가 사용 중입니다. 기존 앱을 종료한 후 다시 실행하세요.'); sys.exit(1)
process=subprocess.Popen([sys.executable,'-m','streamlit','run',str(root/'app/Home.py'),'--server.address=127.0.0.1','--server.port=8501','--server.headless=true','--browser.gatherUsageStats=false'],cwd=root)
try:
    for _ in range(120):
        if process.poll() is not None: sys.exit(process.returncode)
        try:
            with urlopen('http://127.0.0.1:8501/_stcore/health',timeout=1) as response:
                if response.status==200:
                    webbrowser.open('http://127.0.0.1:8501'); break
        except OSError: pass
        time.sleep(.5)
    else:
        print('앱 시작 시간이 초과되었습니다.'); process.terminate(); sys.exit(1)
    print('종료: 이 창에서 Ctrl+C를 누르세요.')
    sys.exit(process.wait())
except KeyboardInterrupt:
    process.terminate(); process.wait()
