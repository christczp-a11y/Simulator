"""Compare the 45–55 ms time-step sensitivity run on its actual output timestamps."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re

import numpy as np

from ep02_balance import GLOBAL


def history(path):
    with path.open(newline="") as stream:
        reader=csv.reader(stream)
        headers=[" ".join(h.split()) for h in next(reader)]
        if headers[:len(GLOBAL)]!=GLOBAL:
            raise ValueError(f"Unrecognised channel map in {path}")
        data=np.asarray([[float(v) for v in row[:len(GLOBAL)]] for row in reader])
    if not np.isfinite(data).all() or np.any(np.diff(data[:,0])<=0) or np.max(np.diff(data[:,0]))>.00011:
        raise ValueError(f"Incomplete native history in {path}")
    return data


def compare(baseline,study,output):
    restart="combine_0003_0001.rst"
    def checksum(path):
        with path.open("rb") as f:
            return hashlib.file_digest(f,"sha256").hexdigest()
    parent_hash=checksum(baseline/restart)
    if not (baseline/restart).samefile(study/restart) and checksum(study/restart)!=parent_hash:
        raise ValueError("Runs must share the 45 ms restart")
    for folder in (baseline,study):
        if "NORMAL TERMINATION" not in (folder/"combine_0004.out").read_text():
            raise ValueError(f"Incomplete engine run in {folder}")
    ref_deck=(baseline/"combine_0004.rad").read_text()
    branch_deck=(study/"combine_0004.rad").read_text()
    expected=ref_deck.replace("/RUN/combine/4/\n0.070000","/RUN/combine/4/\n0.055000")
    if expected==ref_deck or branch_deck!=expected+"/DTIX\n0 4.98e-7\n":
        raise ValueError("Unexpected engine deck difference")
    original=history(baseline/"combineT04.csv")
    capped=history(study/"combineT04.csv")
    initial=history(baseline/"combineT01.csv")[0]
    t=capped[:,0]
    if t[0]<original[0,0] or t[-1]>original[-1,0] or abs(t[0]-.045)>1e-6 or not .05489<=t[-1]<=.055:
        raise ValueError("Sensitivity run does not cover the expected comparison window")
    ref=np.stack([np.interp(t,original[:,0],v) for v in original.T],axis=1)
    # The time-history exports are rounded to seven significant figures.
    for data in (ref,capped):
        total=data[:,1]+data[:,2]+data[:,8]+data[:,11]+data[:,12]-data[:,9]+data[:,21]+data[:,22]
        np.testing.assert_allclose(total,data[:,23],rtol=2e-6,atol=1.)
    np.testing.assert_allclose(ref[0,[1,2,8,11,23]],capped[0,[1,2,8,11,23]],rtol=1e-6)
    drifts=[100*(data[:,23]/initial[23]-1) for data in (ref,capped)]
    output.mkdir(parents=True,exist_ok=True)
    with (output/"56kmh-step-study.csv").open("w",newline="") as f:
        w=csv.writer(f,lineterminator="\n")
        w.writerow(["solver_ms","baseline_drift_pct","capped_drift_pct","baseline_contact_kJ","capped_contact_kJ",
                    "baseline_internal_kJ","capped_internal_kJ"])
        for values in zip(t*1000,*drifts,ref[:,11]*1e-6,capped[:,11]*1e-6,ref[:,1]*1e-6,capped[:,1]*1e-6):
            w.writerow([round(float(x),7) for x in values])
    report=dict(restart_sha256=parent_hash, paired_samples=len(t),first_solver_ms=t[0]*1000,last_solver_ms=t[-1]*1000,
                initial_total_kJ=initial[23]/1e6,start_drift_pct=drifts[0][0])
    for label,data,drift in zip(("baseline","capped"),(ref,capped),drifts):
        excess=np.flatnonzero(drift>=5)
        report[label]=dict(median_step_us=float(np.median(data[:,7])*1e6),end_drift_pct=drift[-1],
                          max_abs_drift_pct=max(abs(drift)),
                          first_sample_at_or_above_five_solver_ms=t[excess[0]]*1000 if len(excess) else None)
    report["end_difference_percentage_points"]=drifts[1][-1]-drifts[0][-1]
    report["end_difference_kJ"]={GLOBAL[i]:float((capped[-1,i]-ref[-1,i])/1e6) for i in (1,2,8,9,11,13,14,15,23)}
    log=(study/"combine_0004.out").read_text()
    report["study_cycles"]=int(re.search(r"TOTAL NUMBER OF CYCLES\s*:\s*(\d+)",log)[1])
    (output/"56kmh-step-study.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    os.environ.setdefault("MPLCONFIGDIR",str(study.resolve()/"mpl-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7.2,4.0),layout="constrained")
    for label,drift,color in zip(("Baseline (0.996 µs)","Capped (0.498 µs)"),drifts,("#284d61","#a65037")):
        ax.plot(t*1000,drift,color=color,lw=2,label=label)
    ax.axhline(5,color="#555",ls="--",lw=1,label="Acceptance limit")
    ax.set(title="56 km/h · restart from the same 45 ms state",xlabel="Time since solver start (ms)",
           ylabel="Native total-energy drift (%)")
    ax.grid(alpha=.18)
    ax.spines[["right","top"]].set_visible(False)
    ax.legend(frameon=False)
    fig.savefig(output/"56kmh-step-study.png",dpi=155)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("baseline",type=Path)
    p.add_argument("study",type=Path)
    p.add_argument("output",type=Path)
    a=p.parse_args()
    compare(a.baseline,a.study,a.output)
