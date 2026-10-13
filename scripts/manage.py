"""CLI entrypoint, usable on Windows and Linux."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.db import initialize,connect
from research.pipeline import collect
from research.reporting import daily,weekly
from research.paths import DATA,DB,now

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['init','daily','weekly','backup'])
    parser.add_argument('--offline',action='store_true',help='수집 없이 DB로 보고서 생성')
    parser.add_argument('--pdf',action='store_true',help='공개 PDF 다운로드 (robots 적용)')
    parser.add_argument('--limit',type=int,default=10)
    parser.add_argument('--date',type=date.fromisoformat,help='보고서 기준일 YYYY-MM-DD (수집 시각은 소급하지 않음)')
    args=parser.parse_args(); initialize()
    if args.command=='init': print('DB ready:',DB)
    elif args.command=='daily':
        result=None if args.offline else collect(max(1,min(args.limit,100)),download_pdfs=args.pdf)
        print(json.dumps(result,ensure_ascii=False)); daily(args.date.isoformat() if args.date else None); print('Daily 보고서 생성 완료')
        if result and result['status'] in ('PARTIAL','NO_SOURCES'): return 2
    elif args.command=='weekly': weekly(args.date.isoformat() if args.date else None); print('Weekly 보고서 생성 완료: 분석 미확인 사항은 보고서에서 확인하십시오')
    else:
        import sqlite3,zipfile
        target=DATA/'backups'/now().strftime('%Y%m%d_%H%M%S_%f'); target.mkdir(parents=True)
        with connect() as source:
            with sqlite3.connect(target/'research.db') as dest: source.backup(dest)
        with zipfile.ZipFile(target/'assets.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for directory in ('papers','reports','config'):
                base=(DATA if directory!='config' else Path(__file__).resolve().parents[1])/directory
                for file in base.rglob('*'):
                    if file.is_file(): archive.write(file,Path(directory)/file.relative_to(base))
        print('Backup:',target)
    return 0

if __name__=='__main__': sys.exit(main())
