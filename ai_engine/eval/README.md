# Evaluation harness

The measurement instrument. Any claim about detector performance must be
re-measured with this.

## Setup

`clips/` is gitignored and empty in a fresh clone. Populate it from
`ai_engine/adas_transfer/clips/`:

    cp ai_engine/adas_transfer/clips/*.mp4 ai_engine/eval/clips/

**The clips are test-only, permanently.** They carry no public licence and
show identifiable people, vehicles and locations. Never publish them, never
train on them, and never use their ordinary-traffic frames as negatives.

## Running

    uv run python ai_engine/eval/run_clips.py --weights ai_engine/epoch50.pt
    uv run python ai_engine/eval/score.py

`labels.csv` decides which clips run. Only clips with a label row are
processed.

## Reading results

Report standard and hard recall SEPARATELY. A blended figure hides which
crashes were winnable. Never quote validation mAP — it is leaked, and a
model already known to be broken scored 0.986 by the same measure.
