#!/usr/bin/env python3
"""Orosz kapcsolódású hajók elleni incidensek: Excel -> JSON.
Független a deep_strikes feldolgozótól; csak az új kimeneteket írja.
"""
import argparse
import hashlib
import json
import math
import re
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from openpyxl import load_workbook

DEFAULT_INPUT = 'data/manual/orosz_hajok_elleni_tamadasok.xlsx'

def val(x):
    return re.sub(r'\s+', ' ', str(x or '')).strip()

def dt(x):
    if isinstance(x, (date, datetime)):
        return x.strftime('%Y-%m-%d')
    s=val(x)
    for fmt in ('%Y-%m-%d','%Y.%m.%d','%Y.%m.%d.','%d.%m.%Y','%d.%m.%Y.'):
        try: return datetime.strptime(s,fmt).strftime('%Y-%m-%d')
        except ValueError: pass
    raise ValueError('Érvénytelen dátum: '+s)

def coord(x, limit):
    n=float(str(x).replace(',','.'))
    if not math.isfinite(n) or not -limit <= n <= limit:
        raise ValueError('Érvénytelen koordináta: '+str(x))
    return round(n,6)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',default=DEFAULT_INPUT)
    p.add_argument('--output',default='data/ship_attacks.json')
    p.add_argument('--summary',default='data/ship_attacks_summary.json')
    p.add_argument('--validation',default='data/ship_attacks_validation.json')
    a=p.parse_args()
    book=load_workbook(a.input,read_only=True,data_only=True)
    sheet=book['Események']
    rows=sheet.iter_rows(values_only=True)
    header=[val(v) for v in next(rows)]
    col={h:i for i,h in enumerate(header) if h}
    required=['Dátum','Hajó neve','Helyszín','Szélesség (WGS84)','Hosszúság (WGS84)']
    missing=[h for h in required if h not in col]
    if missing: raise ValueError('Hiányzó oszlopok: '+', '.join(missing))
    events=[]; issues=[]; seen=set()
    for number,row in enumerate(rows,2):
        if not any(v is not None and str(v).strip() for v in row):continue
        def get(h):
            i=col.get(h)
            return row[i] if i is not None and i<len(row) else None
        def s(h):return val(get(h))
        try:
            day=dt(get('Dátum'))
            lat=coord(get('Szélesség (WGS84)'),90)
            lon=coord(get('Hosszúság (WGS84)'),180)
            name=s('Hajó neve')
            if not name or not s('Helyszín'):raise ValueError('Hiányzó hajónév vagy helyszín')
            key=(day,name.casefold(),s('Helyszín').casefold())
            if key in seen:issues.append({'row':number,'warning':'Lehetséges duplikátum'})
            seen.add(key)
            event_id='SHIP-'+day.replace('-','')+'-'+hashlib.sha1('|'.join(map(str,key)).encode()).hexdigest()[:10].upper()
            event={
                'event_id':event_id,'date':day,'ship_name':name,
                'ship_type':s('Hajótípus'),'flag':s('Zászló'),'imo':s('IMO'),
                'russian_connection':s('Orosz kapcsolat'),
                'location':s('Helyszín'),'latitude':lat,'longitude':lon,
                'strike_type':s('Támadás módja'),'attribution':s('Elkövető / attribúció'),
                'outcome':s('Kimenetel'),'confidence':s('Bizonyosság'),
                'source_url':s('Forrás URL'),'notes':s('Megjegyzés'),
                'vessel_purpose':s('Hajó rendeltetése'),
                'fleet_classification':s('Orosz / árnyékflotta besorolás'),
                'coordinate_quality':s('Koordináta minősége'),
                'coordinate_type':s('Koordináta típusa'),
                'source_row':number
            }
            if not event['source_url'].startswith(('https://','http://')):
                issues.append({'row':number,'warning':'Hiányzó vagy nem URL-formátumú forrás'})
            if 'referenciapont' in event['coordinate_quality'].casefold() or 'térségi' in event['coordinate_type'].casefold():
                event['coordinate_is_approximate']=True
            else:event['coordinate_is_approximate']=bool(event['coordinate_quality'])
            events.append(event)
        except Exception as e:issues.append({'row':number,'error':str(e)})
    events.sort(key=lambda x:(x['date'],x['ship_name']))
    def counts(k):return dict(sorted(Counter(e[k] or 'Ismeretlen' for e in events).items()))
    summary={'event_count':len(events),'date_start':events[0]['date'] if events else None,
             'date_end':events[-1]['date'] if events else None,
             'by_year':dict(sorted(Counter(e['date'][:4] for e in events).items())),
             'by_purpose':counts('vessel_purpose'),'by_fleet':counts('fleet_classification'),
             'by_attack_type':counts('strike_type'),'by_confidence':counts('confidence'),
             'approximate_coordinates':sum(e['coordinate_is_approximate'] for e in events)}
    now=datetime.now(timezone.utc).isoformat()
    validation={'generated_at':now,'valid_event_count':len(events),
                'error_count':sum('error' in x for x in issues),
                'warning_count':sum('warning' in x for x in issues),'items':issues}
    def save(path,obj):
        dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save(a.output,{'generated_at':now,'dataset':'russian_linked_ship_attacks',
                   'source_file':Path(a.input).name,'schema_version':'1.0',
                   'summary':summary,'events':events})
    save(a.summary,{'generated_at':now,**summary})
    save(a.validation,validation)
    print(f"Hajós események: {len(events)}; hibák: {validation['error_count']}; figyelmeztetések: {validation['warning_count']}")
    return 2 if validation['error_count'] else 0

if __name__=='__main__':raise SystemExit(main())
