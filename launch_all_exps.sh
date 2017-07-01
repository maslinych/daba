#! /bin/sh

#set -vx

for f in exp*.sh ; do
	bash "$f" &
done

tail -f *.log
