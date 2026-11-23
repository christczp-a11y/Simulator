import json
S = [('s01',150),('s02',120),('s03',300),('s04',105),('s05',90),('s05a',90),('s06',195),('s07',210),('s08',195),('s09',120),('s10',90),('s11',90),('s11a',45),('s12',120),('s13',60),('s14',60),('black',30),('s16',180),('s17',150),('s18',150),('s19',210),('history',270),('end',180)]
st = {}; a = 0
for s, n in S: st[s] = (a, a + n); a += n
cues = [('V1','s01',8),('V2','s02',6),('V3','s03',2),('V4','s04',0),('V5','s05',12),('Q1','s06',10),('Q2','s07',10),('Q3','s08',8),('V6','s16',20),('Q4','s17',10),('V7','s18',20),('V8','s19',10),('V9','s19',134),('V10','history',12)]
d = json.load(open('remotion/src/durations.json'))
for i, (c, s, at) in enumerate(cues):
    f0 = st[s][0] + at
    nxt = st[cues[i+1][1]][0] + cues[i+1][2] if i + 1 < len(cues) else 10**9
    win = min(st[s][1], nxt) - f0
    need = d[c] * 30
    tag = 'OVER %.2fs' % ((need - win) / 30) if need > win else 'ok (spare %.2fs)' % ((win - need) / 30)
    print(f'{c:4} {s:8} vo {d[c]:6.2f}s  window {win/30:5.2f}s  {tag}')

