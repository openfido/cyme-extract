#!/bin/bash
set -x 
export OPENFIDO_INPUT
export OPENFIDO_OUTPUT
for OPENFIDO_INPUT in $(find $PWD/autotest -name 'input_*' -type d -print -prune); do
	OPENFIDO_OUTPUT=$PWD/autotest/output_${OPENFIDO_INPUT##*_}
	rm -rf $OPENFIDO_OUTPUT
	mkdir $OPENFIDO_OUTPUT
	sh openfido.sh </dev/null 2>/dev/stdout 1>$OPENFIDO_OUTPUT/stdout | tee $OPENFIDO_OUTPUT/stderr
done