# ADAS detection core — transfer package

Everything the capstone **system repo** needs to run, test and defend the accident detector.
Staged 2026-08-10 from the research repo `adas_detection`
(https://github.com/Enjey-Kashlee/adas_detection).

**Start with [`SPEC.md`](SPEC.md).** It is the real document — architecture, the code, the settings
that must not change, the measured numbers, and the questions already closed with evidence. This
file is only a map.

---

## What's here

```
SPEC.md          the transition spec — read this first
NOTICE.md        attribution and licences — must ship with the model
model/
  epoch50.pt     the adopted detector (20.8 MB)
code/
  accumulate.py      per-frame boxes -> alert events. Pure logic, no model.
  sources.py         frame input: video files and live RTSP
  run.py             the reference implementation and CLI
  test_accumulate.py 11 tests
  test_sources.py    7 tests
  requirements.txt   ⚠️ install CUDA torch FIRST, or ultralytics pulls a CPU-only build
eval/
  labels.csv     crash onset times and the pre-registered difficulty column
  run_clips.py   run every labelled clip
  score.py       recall and false alarms per minute
  sweep.py       rank every checkpoint — never trust the "best.pt" label
  probe_raw.py   why did a clip miss? detector vs accumulator
clips/           17 Lipa CCTV clips, 15.4 min — the ONLY measurement instrument
```

---

## 🚨 Three things to get right before anything else

**1. The clips are test-only, permanently, and must not be published.**
Never train on them, and never use their ordinary-traffic frames as negatives — doing so destroys
the ability to make any honest claim about performance. They also show identifiable people,
vehicles and locations, and several capture injuries. They carry no public licence. Keep them out
of any public repository. See NOTICE.md.

**2. Take `epoch50.pt`, never a file called `best.pt`.**
`best.pt` is selected by a validation score that is inflated by duplicate frames. It has been the
wrong choice in all three training runs.

**3. The model only ever sees grayscale.**
Feed it colour and it will barely fire. This is not cosmetic — it is the fix for a shortcut the
model would otherwise learn. `sources.py` and `run.py` already handle it; keep it that way.

---

## Order of work

1. Read `SPEC.md`. Sections 5 and 6 in particular — the closed levers, and the defects waiting in a
   live system. They will save more time than anything else here.
2. Copy `code/` into the system repo following its own conventions, and `model/epoch50.pt`
   wherever weights belong.
3. **Prove the port didn't change anything.** Run your ported code and this folder's `run.py` over
   the same clip and check the events match. Then compare against the per-clip table in SPEC.md §4
   — clip by clip, not just the 8/16 total, because the total can hide a change that gains one
   crash and loses another.
4. Fix the fired-region lifecycle (SPEC.md §6) **before** pointing it at a live camera. As it
   stands, every location that raises an alert goes permanently deaf.
5. Wire events into the alert lifecycle.

---

## What it actually does

| | |
|---|---|
| Standard crashes detected | **8 of 10 — 80%** |
| Hard crashes detected | 0 of 6 — 0% |
| False alarms | 3, over ~11 min of ordinary footage |
| **In operator terms** | **~16 false alerts per hour, per camera** |
| Delay after impact | ~3 seconds |
| On the crash-free clip | silent |

**That ~16/hour figure is a design input, not a footnote.** The review queue has to make rejecting
an alert cheap, and any design that assumes "an alert means go look" will overwhelm an operator on
the first shift.

⚠️ **Never quote the model's validation mAP of 0.956.** It is inflated by duplicate frames, and a
model already known to be broken scored 0.986 the same way. The only honest numbers are the ones
in the table above, measured on the clips.

---

## What stayed in the research repo

Training, the datasets, the checkpoint history and the full evidence — including the postmortem of
a previous design that scored 0/7, which is worth reading before proposing any change to the
detection approach. https://github.com/Enjey-Kashlee/adas_detection

⚠️ **Not verified:** the RTSP path has never run against a real camera. Its logic is tested against
a fake capture. Point it at one CDRRMO camera early.
