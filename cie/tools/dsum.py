import json,sys
ds=json.load(open(sys.argv[1]))
for d in ds:
  xa=d.get('x_axis') or {};ya=d.get('y_axis') or {}
  print(' p%s'%d['page'],d['kind'],[round(v) for v in d['bbox']],'x',xa.get('min'),xa.get('max'),'y',ya.get('min'),ya.get('max'),'xl',d.get('x_label','')[:25],'| yl',d.get('y_label','')[:25],'| series',len(d.get('series') or []),'shapes',d.get('curved_shapes',0),'| labels',(d.get('labels') or [])[:10])
