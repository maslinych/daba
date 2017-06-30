#! /bin/bash

set -vx

GIT_VERSION="$(git rev-parse HEAD)"
NOM=exp_accuracy_vs_segmentation_type_$(date +%d_%H_%M)_"$GIT_VERSION"

BASIC_OPTIONS="-v -t -l $NOM"
SUPP_OPTIONS="-e 1 --filtering --diacritic_only"

KEYWORD="Seconds required for this iteration: |Error norm|Iteration #"
KEYWORD2="[^_]diacritic_only|chunkmode|filtering|no_coding|no_decomposition|r_E|accuracy|done|eval|total"
FP_PAT="[-+]?[0-9]+\.?[0-9]*"

touch "$NOM.log"

for w in -1 1 2 3 4 5 6 0
do
VAR_OPTS="-c $w -s "$NOM"_w_"$w".csv"

if hash stdbuf 2>/dev/null; then
stdbuf -oL python disambiguation.py $VAR_OPTS $SUPP_OPTIONS $BASIC_OPTIONS \
| gawk "BEGIN{IGNORECASE=1} /.*($KEYWORD2).*/ {print \$0} match(\$0, /.*($KEYWORD)[^.0-9+-]*($FP_PAT)/, ary) {print ary[2]}" \
>> "$NOM.log"
else
gstdbuf -oL python disambiguation.py $VAR_OPTS $SUPP_OPTIONS $BASIC_OPTIONS \
| gawk "BEGIN{IGNORECASE=1} /.*($KEYWORD2).*/ {print \$0} match(\$0, /.*($KEYWORD)[^.0-9+-]*($FP_PAT)/, ary) {print ary[2]}" \
>> "$NOM.log"
fi
done
