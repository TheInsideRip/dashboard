import sqlite3, io
conn=sqlite3.connect(r'E:\mlb_model\mlb_model.db'); c=conn.cursor()
out=io.open('recon_2inrow_OUT.txt','w',encoding='utf-8')
def p(s=''):
    print(s); out.write(s+'\n')

# Build per-team game sequences with total-vs-line deviation, then count 2-in-a-row near-number.
# Need: each game's actual_total, book_line, per team, ordered by date within season.
rows=c.execute("""
  SELECT b.game_date, b.season, b.home_team, b.away_team, b.actual_total, b.book_line
  FROM game_totals_backtest_clean b
  WHERE b.actual_total IS NOT NULL AND b.book_line IS NOT NULL
""").fetchall()

# expand to team-level rows
from collections import defaultdict
teamgames=defaultdict(list)  # (team,season) -> list of (date, dev)
for gd,seas,hm,aw,at,line in rows:
    dev=at-line
    teamgames[(hm,seas)].append((gd,dev))
    teamgames[(aw,seas)].append((gd,dev))

NEAR=0.5  # |dev|<=0.5 = "near the number"
for near in [0.5, 1.0]:
    twos=0; total_eligible=0
    twos_by_season=defaultdict(int)
    for (team,seas),lst in teamgames.items():
        lst.sort()
        devs=[d for _,d in lst]
        for i in range(2,len(devs)):
            total_eligible+=1
            if abs(devs[i-1])<=near and abs(devs[i-2])<=near:
                twos+=1
                twos_by_season[seas]+=1
    p(f"NEAR=|dev|<={near}: games preceded by 2-in-a-row near = {twos} / {total_eligible} eligible ({100*twos/total_eligible:.1f}%)")
    for s in sorted(twos_by_season):
        p(f"    {s}: {twos_by_season[s]} such games")
    p("")
out.close(); conn.close()
print("--- recon_2inrow_OUT.txt ---")
