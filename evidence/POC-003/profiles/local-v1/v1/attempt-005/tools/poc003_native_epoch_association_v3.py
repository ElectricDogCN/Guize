"""Associate used native metadata with the already authenticated closed epochs."""
def associate_native_processes(native,index,collection,sidecars,assembled=None):
 def need(ok,msg):
  if not ok:raise ValueError(msg)
 epochs={}
 for row in native['epochs']:
  pid=row['pid'];need(type(pid) is int and pid>0 and pid not in epochs,'foreign or ambiguous native epoch PID')
  need(type(row['startTicks']) is int and row['startTicks']>0,'actual native epoch birth required')
  token=int(row['token']);need(str(token)==row['token'] and 0<=token<26,'exact serialized native token required')
  role='start' if token%2 else 'verify_config' if token==0 else 'clear_cache'
  epochs[pid]=dict(pid=pid,token=row['token'],role=role,startTicks=row['startTicks'],journalSha256=row['rawSha256'])
 need(len(epochs)==26,'all26 authenticated epochs required')
 need(set(index.events)<=set(epochs),'foreign native observer directory outside actual owned26')
 used={pid for pid,events in index.events.items() if events}
 def inspect(value):
  if isinstance(value,dict):
   for key,item in value.items():
    if key=='atsPid' and item is not None:
     need(type(item) is int and item>0,'native observation PID must be positive');used.add(item)
    inspect(item)
  elif isinstance(value,(list,tuple)):
   for item in value:inspect(item)
 inspect(collection);inspect(sidecars)
 if assembled is not None:inspect(assembled['requestProvenance']);inspect(assembled['lifecycleProvenance'])
 need(used and used<=set(epochs),'foreign native observation PID outside actual owned26')
 need(all(epochs[pid]['role']=='start' for pid in used),'native observation PID belongs to helper rather than actual ATS start service')
 return dict(unusedObserverDirectories=[epochs[p] for p,events in sorted(index.events.items()) if not events],usedNativeEpochs=[epochs[p] for p in sorted(used)],observedNativePids=sorted(used),allUsedPidsBelongToActualClosedEpochs=True,scope='Exact actual own26 PID/token/birth; ambiguous reused PID is rejected rather than silently rebound')
