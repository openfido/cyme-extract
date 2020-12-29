#!/bin/bash
set -x
export OPENFIDO_INPUT
export OPENFIDO_OUTPUT
for OPENFIDO_INPUT in $(find $PWD/autotest -name 'input_*' -type d -print -prune); do
	OPENFIDO_OUTPUT=$PWD/autotest/output_${OPENFIDO_INPUT##*_}
	rm -rf $OPENFIDO_OUTPUT
	mkdir $OPENFIDO_OUTPUT
	$PWD/openfido.sh </dev/null 1>$OPENFIDO_OUTPUT/stdout 2>$OPENFIDO_OUTPUT/stderr
done