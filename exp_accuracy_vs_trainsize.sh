#! /bin/bash

set -vx

GIT_VERSION="$(git rev-parse HEAD)"
NOM=exp_accuracy_vs_trainsize_$(date +%d_%H_%M)_"$GIT_VERSION"

BASIC_OPTIONS="-v -t -l $NOM"
SUPP_OPTIONS="--filtering --diacritic_only"

KEYWORD="Seconds required for this iteration: |Error norm|Iteration #"
KEYWORD2="[^_]diacritic_only|chunkmode|filtering|no_coding|no_decomposition|r_E|accuracy|done|eval|total"
FP_PAT="[-+]?[0-9]+\.?[0-9]*"

touch "$NOM.log"

for trainsize in 1 10 20 30 40 50 60 70 80 90
do
VAR_OPTS="-e $trainsize -s "$NOM"_trainsize_"$trainsize".csv"
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
