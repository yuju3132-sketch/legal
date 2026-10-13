from datetime import date

WEIGHTS = {'A':25,'B':20,'C':15,'D':15,'E':15,'F':10}

def score(components=None, publication_date=None, today=None, evidence=None):
    """Human review supplies A–E; automatic classification never invents significance."""
    components = components or {}
    points = {}
    reasons = []
    for key,cap in WEIGHTS.items():
        if key == 'F':
            try:
                age = ((today or date.today())-date.fromisoformat(publication_date)).days
                value = 10 if 0 <= age <= 7 else 7 if 7 < age <= 30 else 3 if 30 < age <= 365 else 0
            except (TypeError,ValueError):
                value = 0
        else:
            value = components.get(key, 0)
            if not isinstance(value,(int,float)) or not 0 <= value <= cap:
                raise ValueError(f'{key} must be between 0 and {cap}')
            if value and not (evidence or {}).get(key):
                raise ValueError(f'{key}: 점수 근거가 필요합니다')
        points[key] = int(value)
        reasons.append(f'{key} {int(value)}/{cap}: '+((evidence or {}).get(key,'발행일 기준' if key=='F' else '평가 대기')))
    total = sum(points.values())
    priority = 'A' if total >= 85 else 'B' if total >=70 else 'C' if total >=50 else 'D'
    return total,priority,'; '.join(reasons),points
