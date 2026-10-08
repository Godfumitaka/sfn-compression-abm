"""既存試験の集計CSVをReportLabの標準LinePlotで図にする。"""
import csv
import json
from pathlib import Path
import resource
from reportlab.graphics.shapes import Drawing, String, Line
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics import renderSVG, renderPDF
from reportlab.lib import colors

OUT=Path(__file__).resolve().parent/'output'
rows=list(csv.DictReader((OUT/'curves_by_seed.csv').open()))
means=list(csv.DictReader((OUT/'curves_three_seed_mean.csv').open()))
palette=[colors.HexColor(x) for x in ('#3076b5','#dd8130','#409762','#232323')]

def panel(d,x,y,w,h,title,data,labels,cols,ymax=1):
    d.add(String(x,y+h+20,title,fontName='Helvetica-Bold',fontSize=13))
    p=LinePlot(); p.x=x; p.y=y; p.width=w; p.height=h; p.data=data
    p.xValueAxis.valueMin=0; p.xValueAxis.valueMax=5000
    p.xValueAxis.valueSteps=list(range(0,5001,1000))
    p.yValueAxis.valueMin=0;p.yValueAxis.valueMax=ymax
    p.yValueAxis.valueSteps=[v*ymax/4 for v in range(5)]
    p.yValueAxis.labels.fontSize=9;p.xValueAxis.labels.fontSize=9
    p.lines.symbol=None
    for i,col in enumerate(cols):
        p.lines[i].strokeColor=col;p.lines[i].strokeWidth=2 if labels[i].startswith('Mean') else .8
    d.add(p)
    for i,(label,col) in enumerate(zip(labels,cols)):
        pos=x+i*(w/len(labels));d.add(Line(pos,y-28,pos+13,y-28,strokeColor=col,strokeWidth=2))
        d.add(String(pos+18,y-31,label,fontName='Helvetica',fontSize=8))

def series(metric,den):
    data=[]
    for seed in (1,2,3):
        data.append([(int(r['trial']),int(r[metric])/den) for r in rows if int(r['seed'])==seed])
    data.append([(int(r['trial']),float(r[metric+'_fraction'])) for r in means])
    return data

d=Drawing(1000,800)
d.add(String(40,766,'Verb world: completed old A, seeds 1-3 (100, 200, ... 5000)',fontName='Helvetica-Bold',fontSize=17))
d.add(String(40,744,'No new simulation. Correct = native predicate + argument oracle. No truth score for novel words.',fontName='Helvetica',fontSize=11))
panel(d,70,440,385,245,'Regular correct / 32 queries',series('regular_correct',32),['Seed 1','Seed 2','Seed 3','Mean'],palette)
panel(d,580,440,385,245,'Irregular correct / 8 queries',series('irregular_correct',8),['Seed 1','Seed 2','Seed 3','Mean'],palette)
panel(d,70,90,385,245,'Irregular REG / 8 queries (overregularization)',series('irregular_REG',8),['Seed 1','Seed 2','Seed 3','Mean'],palette)
novel=[[(int(r['trial']),float(r[k+'_fraction'])) for r in means] for k in ('novel_REG','novel_IRR','novel_abstain','novel_other')]
panel(d,580,90,385,245,'Novel response / 8 queries (mean of 3 seeds)',novel,['Mean REG','Mean IRR','Mean abstain','Mean other'],palette)
d.add(String(370,23,'Training trials; each point is a stored non-learning probe',fontName='Helvetica',fontSize=11))
renderSVG.drawToFile(d,str(OUT/'old_A_curves.svg'))
renderPDF.drawToFile(d,str(OUT/'old_A_curves.pdf'),pageCompression=0)

profile=list(csv.DictReader((OUT/'sme_100trial_timing.csv').open()))
t=Drawing(1000,425)
t.add(String(40,395,'SME 25-prime: instrumented first 1000 trials, seed 1',fontName='Helvetica-Bold',fontSize=17))
t.add(String(40,373,'Trace CPU removed from accounted CPU; cProfile overhead remains. Horizon = 5000.',fontName='Helvetica',fontSize=11))
p=LinePlot();p.x=75;p.y=80;p.width=870;p.height=255
p.data=[[(int(r['last_trial'])+1,float(r[k])) for r in profile] for k in ('sec_trial_sum','process_cpu_seconds','accounted_seconds')]
p.xValueAxis.valueMin=100;p.xValueAxis.valueMax=1000;p.xValueAxis.valueSteps=list(range(100,1001,100))
p.yValueAxis.valueMin=0;p.yValueAxis.valueMax=2000;p.yValueAxis.valueSteps=list(range(0,2001,500))
p.lines.symbol=None
for i in range(3):p.lines[i].strokeColor=palette[i];p.lines[i].strokeWidth=2
t.add(p)
for i,label in enumerate(('Wall seconds / block','CPU seconds / block','Accounted CPU / block')):
    x=90+i*280;t.add(Line(x,46,x+20,46,strokeColor=palette[i],strokeWidth=2));t.add(String(x+27,43,label,fontSize=11))
t.add(String(360,13,'Last completed trial in each 100-trial block',fontSize=11))
renderSVG.drawToFile(t,str(OUT/'sme_profile1000_timing.svg'))
renderPDF.drawToFile(t,str(OUT/'sme_profile1000_timing.pdf'),pageCompression=0)
(OUT/'plot_resources.json').write_text(json.dumps({'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'library':'ReportLab standard LinePlot; no model import'},indent=2)+'\n')
print('Saved 2 SVG and 2 PDF figures.',flush=True)
