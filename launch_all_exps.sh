#! /bin/sh

#set -vx

for f in exp*.sh ; do
	bash "$f" &
done

sleep 5
tail -f *.log
