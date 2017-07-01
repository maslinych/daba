#! /bin/sh

for f in *.sh
do
	bash $f &
done

wait 60

tail -f *.log
