"""門の集計表を、その数のまま科学的な曲線図へ書き出す。"""
import argparse
import csv
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']=str(ROOT/'plot_cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

font=next(p for p in Path('/System/Library/Fonts').iterdir() if 'W3.ttc' in p.name)
font_manager.fontManager.addfont(str(font))
plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(font)).get_name(),
                     'font.size':10,'axes.unicode_minus':False,'svg.fonttype':'path'})
STRATA={'all':'全課題','switch_A':'切り替わる葉・変種A','switch_B':'切り替わる葉・変種B'}
LABELS={'v4spc_C_L50':'C λ=0.0187371','v4spc_C_L90':'C λ=0.0990004',
        'v4D_tau025':'D τ=0.25','v4D_tau040':'D τ=0.4','v4D_tau060':'D τ=0.6'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('curves',type=Path);ap.add_argument('destination',type=Path)
    a=ap.parse_args();a.destination.mkdir(exist_ok=True)
    with a.curves.open() as f:raw=list(csv.DictReader(f))
    arms=list(dict.fromkeys(r['arm'] for r in raw))
    series={(arm,s):sorted((r for r in raw if r['arm']==arm and r['stratum']==s),key=lambda r:float(r['gate']))
            for arm in arms for s in STRATA}
    fig,axes=plt.subplots(3,2,figsize=(12,12),layout='constrained')
    colors=plt.get_cmap('tab10')
    for i,(s,title) in enumerate(STRATA.items()):
        for j,(metric,rand,ylabel) in enumerate((('avoided_wrong','random_avoided_wrong','避けた誤答（件）'),
                                                 ('lost_correct','random_lost_correct','失った正解（件）'))):
            ax=axes[i,j]
            for k,arm in enumerate(arms):
                rows=series[arm,s];g=[float(r['gate']) for r in rows]
                ax.plot(g,[float(r[metric]) for r in rows],marker='o',color=colors(k),label=LABELS[arm])
                ax.plot(g,[float(r[rand]) for r in rows],linestyle='--',color=colors(k),alpha=.65)
            ax.set(title=title,xlabel='門 g',ylabel=ylabel,xlim=(.66,1.01),ylim=(0,None))
            ax.grid(alpha=.2);ax.set_xticks([.67,.75,.85,.95,1])
    axes[0,0].legend(fontsize=9)
    fig.suptitle('支持の割合で黙らせた件数と、同数を無作為に黙らせる期待値\n実線：支持の割合による門　破線：各層の回答から無作為に黙らせる期待値',fontsize=13)
    for ext in ('png','svg'):fig.savefig(a.destination/f'gate_curves.{ext}',dpi=170)
    plt.close(fig)
    fig,axes=plt.subplots(len(arms),3,figsize=(13,3*len(arms)),squeeze=False,layout='constrained')
    for i,arm in enumerate(arms):
        for j,(s,title) in enumerate(STRATA.items()):
            rows=series[arm,s];ax=axes[i,j];g=[float(r['gate']) for r in rows]
            ax.stackplot(g,*[[int(r['lost_correct_'+x]) for r in rows] for x in ('a','b','c')],
                         labels=['(a) 未経験の型','(b) 取り込み済みの別の型','(c) その他'],alpha=.8)
            ax.set(title=LABELS[arm]+'・'+title,xlabel='門 g',ylabel='失った正解（件）',xlim=(.67,1),ylim=(0,None))
            ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=8)
    for ext in ('png','svg'):fig.savefig(a.destination/f'lost_correct_types.{ext}',dpi=170)
    plt.close(fig)


if __name__=='__main__':main()
