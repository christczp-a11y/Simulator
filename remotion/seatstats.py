import numpy as np, json
G=np.load('/mnt/project-files/particle-sim/data/fp/nose.npz'); eye=G['eye']; print('eye',eye)
X=np.load('sim_f1/x.npy',mmap_mode='r'); T,N,_=X.shape; fps=15000.0; t0=-0.001
part=G['vpart']; names=[str(n) for n in G['part_names']]; V=G['verts']; a=G['varea']
seat=(part==names.index('seat'))&(np.sign(V[:,1])==np.sign(eye[1]))
print('seat verts',seat.sum(), V[seat].min(0), V[seat].max(0))
idx=np.flatnonzero(seat); w=a[idx]/a[idx].sum()
com=np.zeros((T,3))
for f in range(T): com[f]=(np.asarray(X[f][idx],np.float64)*w[:,None]).sum(0)
vel=np.gradient(com,1/fps,axis=0); spd=np.linalg.norm(vel,axis=1)
def smooth(y,k):
    ker=np.ones(k)/k; pad=k//2; yp=np.pad(y,((pad,pad),(0,0)),mode='edge'); return np.stack([np.convolve(yp[:,i],ker,mode='valid') for i in range(y.shape[1])],1)[:len(y)]
for k in (15,31):
    vs=smooth(vel,k); acc=np.gradient(vs,1/fps,axis=0); acc=smooth(acc,k); felt=acc+np.array([0,0,9.81]); g=np.linalg.norm(felt,axis=1)/9.81
    t=(t0+np.arange(T)/fps)*1e3
    print('window',k,'peak g',g.max(),'at ms',t[g.argmax()])
    for ms in (-1,0,4,8,10,12,14,16,18,20,22,24,26,28,30,32,34,38): 
        i=int(round((ms/1e3-t0)*fps)); print(ms, 'spd %.1f m/s %.0f km/h g %.0f'%(np.linalg.norm(vs[i]),np.linalg.norm(vs[i])*3.6,g[i]))
    if k==15: np.savez('seatstats.npz',t=t,speed=np.linalg.norm(vs,axis=1),g=g,com=com)
